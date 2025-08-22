from io import BytesIO
from decimal import Decimal
from django.http import HttpResponse
from django.db import transaction
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from .models import Order, Cart, CartItem
from .serializers import OrderCreateSerializer

class IsOwnerOrStaff(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if getattr(request.user, "is_staff", False):
            return True
        return getattr(obj, "created_by_id", None) == getattr(request.user, "id", None)

class OrderViewSet(viewsets.ModelViewSet):
    """
    POST /api/orders/                -> create (guest OK)
    GET  /api/orders/                -> list (auth required)
    POST /api/orders/{id}/place/     -> finalize
    GET  /api/orders/{id}/invoice/   -> PDF invoice
    GET  /api/orders/report/sales/   -> JSON sales report (staff)
    """
    queryset = Order.objects.all().order_by("-created_at")
    serializer_class = OrderCreateSerializer

    def get_permissions(self):
        if self.action in ["create", "place", "invoice"]:
            return [permissions.AllowAny()]
        if self.action in ["list", "retrieve"]:
            return [permissions.IsAuthenticated()]
        if self.action in ["report"]:
            return [permissions.IsAdminUser()]
        return [permissions.IsAdminUser()]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action in ["list", "retrieve"] and self.request.user.is_authenticated and not self.request.user.is_staff:
            qs = qs.filter(created_by=self.request.user)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        order = serializer.save()
        return Response({"id": order.id, "status": order.status}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], permission_classes=[permissions.AllowAny])
    def place(self, request, pk=None):
        order = self.get_object()
        if order.status == "PENDING":
            order.status = "PLACED"
            order.save(update_fields=["status"])
        return Response({"id": order.id, "status": order.status})

    @action(detail=True, methods=["get"], permission_classes=[permissions.AllowAny])
    def invoice(self, request, pk=None):
        order = self.get_object()
        # Build a tiny PDF invoice
        buf = BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        w, h = A4
        y = h - 20*mm
        c.setFont("Helvetica-Bold", 14)
        c.drawString(20*mm, y, f"Invoice for Order #{order.id}")
        y -= 10*mm
        c.setFont("Helvetica", 11)
        c.drawString(20*mm, y, f"Status: {order.status}")
        y -= 8*mm
        c.drawString(20*mm, y, f"Created: {order.created_at.strftime('%Y-%m-%d %H:%M')}")
        y -= 12*mm
        c.setFont("Helvetica-Bold", 12)
        c.drawString(20*mm, y, "Items")
        y -= 8*mm
        c.setFont("Helvetica", 11)

        total = Decimal("0.00")
        for it in order.items.select_related("menu_item").all():
            line_total = Decimal(it.unit_price) * it.quantity
            total += line_total
            c.drawString(20*mm, y, f"{it.menu_item.name} x {it.quantity} @ {it.unit_price} = {line_total}")
            y -= 6*mm
            if y < 30*mm:
                c.showPage(); y = h - 20*mm; c.setFont("Helvetica", 11)

        y -= 6*mm
        c.setFont("Helvetica-Bold", 12)
        c.drawString(20*mm, y, f"Total: NPR {total}")
        c.showPage()
        c.save()

        pdf = buf.getvalue()
        buf.close()
        resp = HttpResponse(pdf, content_type="application/pdf")
        resp["Content-Disposition"] = f'inline; filename="invoice_{order.id}.pdf"'
        return resp

    @action(detail=False, methods=["get"], permission_classes=[permissions.IsAdminUser], url_path="report/sales")
    def report(self, request):
        # Very simple sales report for last 30 days
        from django.utils import timezone
        from datetime import timedelta
        since = timezone.now() - timedelta(days=30)
        qs = Order.objects.filter(created_at__gte=since, status__in=["PLACED", "PAID"])
        count = qs.count()
        total = Decimal("0.00")
        for o in qs:
            for it in o.items.all():
                total += Decimal(it.unit_price) * it.quantity
        return Response({"orders": count, "sales_npr": str(total)})

# --- Cart endpoints (identity-strict) ---
@method_decorator(csrf_exempt, name="dispatch")
class CartViewSet(viewsets.ViewSet):
    """
    GET  /api/cart/                   -> current cart (user if auth; else session)
    POST /api/cart/sync/              -> replace items
    POST /api/cart/claim/             -> merge session cart into user cart (auth)
    POST /api/cart/reset_session/     -> delete session cart & cycle key
    """
    permission_classes = [permissions.AllowAny]

    def _ensure_session(self, request):
        if request.session.session_key is None:
            request.session.save()

    def _get_cart_user(self, request):
        user = request.user if request.user.is_authenticated else None
        if not user:
            return None
        cart, _ = Cart.objects.get_or_create(user=user, defaults={"session_key": ""})
        return cart

    def _get_cart_session(self, request):
        self._ensure_session(request)
        skey = request.session.session_key or ""
        cart, _ = Cart.objects.get_or_create(session_key=skey, defaults={"user": None})
        return cart

    def _get_current_cart(self, request):
        if request.user.is_authenticated:
            return self._get_cart_user(request)
        return self._get_cart_session(request)

    def list(self, request):
        cart = self._get_current_cart(request)
        data = {"id": cart.id, "items": [{"menu_item": ci.menu_item_id, "quantity": ci.quantity} for ci in cart.items.all()]}
        return Response(data)

    @action(detail=False, methods=["post"], url_path="sync")
    @transaction.atomic
    def sync(self, request):
        cart = self._get_current_cart(request)
        items = request.data if isinstance(request.data, list) else request.data.get("items", [])

        def as_int(v):
            try:
                return int(str(v))
            except Exception:
                return None

        norm = []
        for it in items or []:
            mid = (
                it.get("menu_item")
                or it.get("id")
                or it.get("item")
                or it.get("menuitem")
                or (isinstance(it.get("menu_item"), dict) and it["menu_item"].get("id"))
            )
            qty = it.get("quantity") or it.get("qty") or 1
            mid = as_int(mid)
            try:
                qty = max(int(qty), 1)
            except Exception:
                qty = 1
            if mid:
                norm.append((mid, qty))

        cart.items.all().delete()
        from menu.models import MenuItem
        for mid, qty in norm:
            try:
                mi = MenuItem.objects.get(pk=mid)
                CartItem.objects.create(cart=cart, menu_item=mi, quantity=qty)
            except MenuItem.DoesNotExist:
                continue

        return Response({"ok": True})

    @action(detail=False, methods=["post"], url_path="claim", permission_classes=[permissions.IsAuthenticated])
    @transaction.atomic
    def claim(self, request):
        user_cart = self._get_cart_user(request)
        session_cart = self._get_cart_session(request)
        if session_cart and session_cart.id != user_cart.id:
            existing = {ci.menu_item_id: ci for ci in user_cart.items.select_related("menu_item")}
            for sci in session_cart.items.select_related("menu_item"):
                if sci.menu_item_id in existing:
                    existing[sci.menu_item_id].quantity += sci.quantity
                    existing[sci.menu_item_id].save(update_fields=["quantity"])
                else:
                    CartItem.objects.create(cart=user_cart, menu_item=sci.menu_item, quantity=sci.quantity)
            session_cart.delete()
        data = {"id": user_cart.id, "items": [{"menu_item": ci.menu_item_id, "quantity": ci.quantity} for ci in user_cart.items.all()]}
        return Response(data)

    @action(detail=False, methods=["post"], url_path="reset_session")
    @transaction.atomic
    def reset_session(self, request):
        session_cart = self._get_cart_session(request)
        if session_cart:
            session_cart.delete()
        try:
            request.session.cycle_key()
        except Exception:
            pass
        return Response({"ok": True})
