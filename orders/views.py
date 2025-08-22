from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Order, Product
from .serializers import OrderCreateSerializer, OrderReadSerializer
from payments.services import generate_order_invoice_pdf


# -------------------------
# Session-based Cart (no DB)
# -------------------------
class SessionCartViewSet(viewsets.ViewSet):
    """
    Provides the same endpoints your frontend already calls, but stores cart
    in the user session instead of database models:
      GET    /api/cart/            -> { "items": [{ "product": <id>, "quantity": <int> }, ...] }
      POST   /api/cart/sync/       -> body { "items": [...] }  (replaces the whole cart)
      POST   /api/cart/reset_session/ -> resets the session + clears cart
    """
    permission_classes = [permissions.AllowAny]

    def _ensure_session(self, request):
        if not request.session.session_key:
            try:
                request.session.create()
            except Exception:
                pass

    def _get_cart(self, request):
        return request.session.get("cart", [])

    def _set_cart(self, request, items):
        request.session["cart"] = items
        request.session.modified = True

    def list(self, request):
        self._ensure_session(request)
        items = self._get_cart(request)
        # normalize output
        safe = []
        for it in items:
            try:
                pid = int(it.get("product"))
                qty = int(it.get("quantity") or 1)
            except Exception:
                continue
            if pid > 0 and qty > 0:
                safe.append({"product": pid, "quantity": qty})
        self._set_cart(request, safe)
        return Response({"items": safe})

    @action(detail=False, methods=["post"], url_path="sync")
    def sync(self, request):
        self._ensure_session(request)
        incoming = (request.data or {}).get("items") or []
        normalized = []

        for it in incoming:
            try:
                pid = int(it.get("product"))
                qty = int(it.get("quantity") or 1)
            except Exception:
                continue
            if pid <= 0 or qty <= 0:
                continue
            # optional: validate product exists (quietly skip unknown ids)
            if not Product.objects.filter(pk=pid).exists():
                continue
            normalized.append({"product": pid, "quantity": qty})

        self._set_cart(request, normalized)
        return Response({"items": normalized})

    @action(detail=False, methods=["post"], url_path="reset_session")
    def reset_session(self, request):
        # Clear cart + give a fresh session
        try:
            request.session.flush()
        except Exception:
            pass
        return Response({"ok": True})


# -------------------------
# Orders API (unchanged endpoints)
# -------------------------
class OrderViewSet(viewsets.ModelViewSet):
    """
    POST /api/orders/ payload (as your frontend sends):
      {
        "service_type": "DINE_IN",
        "customer_name": "Alice",
        "customer_email": "alice@example.com",
        "items": [{"product": 1, "quantity": 2}, ...]   # optional; if empty, backend will use session cart
      }
    """
    queryset = Order.objects.all().select_related("user").prefetch_related("items__product")

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return OrderReadSerializer
        return OrderCreateSerializer

    def get_permissions(self):
        if self.action in ["create"]:
            return [permissions.AllowAny()]
        if self.action in ["list", "retrieve", "invoice"]:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAdminUser()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if self.action in ["list", "retrieve"] and user.is_authenticated and not user.is_staff:
            qs = qs.filter(user=user)
        return qs

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        items = data.get("items") or []

        # If client didn’t pass items, fall back to session cart (keeps old behavior)
        if not items:
            sess_items = request.session.get("cart", [])
            # normalize to serializer format
            items = []
            for it in sess_items:
                try:
                    pid = int(it.get("product"))
                    qty = int(it.get("quantity") or 1)
                except Exception:
                    continue
                if pid > 0 and qty > 0:
                    items.append({"product": pid, "quantity": qty})
            data["items"] = items

        serializer = self.get_serializer(data=data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        return Response({"id": order.id, "is_paid": order.is_paid}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def invoice(self, request, pk=None):
        """
        Ensure an invoice exists and respond with its URL if available.
        """
        order = self.get_object()
        if order.is_paid and not order.invoice_pdf:
            try:
                generate_order_invoice_pdf(order)
            except Exception:
                pass
        data = {
            "id": order.id,
            "is_paid": order.is_paid,
            "invoice": order.invoice_pdf.url if order.invoice_pdf else None,
        }
        return Response(data)
