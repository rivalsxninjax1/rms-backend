from io import BytesIO
from decimal import Decimal

from django.db import transaction
from django.http import HttpResponse

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from .models import Order, Cart, CartItem
from .serializers import OrderCreateSerializer, OrderReadSerializer


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all().select_related("created_by")

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return OrderReadSerializer
        return OrderCreateSerializer

    def get_permissions(self):
        if self.action in ["create", "place"]:
            return [permissions.AllowAny()]
        if self.action in ["list", "retrieve"]:
            return [permissions.IsAuthenticated()]
        if self.action in ["report", "invoice"]:
            return [permissions.IsAdminUser()]
        return [permissions.IsAdminUser()]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action in ["list", "retrieve"] and self.request.user.is_authenticated and not self.request.user.is_staff:
            qs = qs.filter(created_by=self.request.user)
        return qs

    def _get_session_key(self, request) -> str:
        if not request.session.session_key:
            try:
                request.session.create()
            except Exception:
                return ""
        return request.session.session_key or ""

    def _cart_for_request(self, request) -> Cart | None:
        if getattr(request.user, "is_authenticated", False):
            cart = Cart.objects.filter(user=request.user).first()
            if cart:
                return cart
        sk = self._get_session_key(request)
        if not sk:
            return None
        return Cart.objects.filter(session_key=sk).first()

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        data = request.data or {}
        items = data.get("items") or []

        # If no items present, try server-side cart (user or session)
        if not items:
            cart = self._cart_for_request(request)
            if cart:
                items = [{"menu_item": ci.menu_item_id, "quantity": ci.quantity} for ci in cart.items.all()]
                data = {**data, "items": items}

        serializer = self.get_serializer(data=data, context={"request": request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        order = serializer.save()
        return Response({"id": order.id, "status": order.status}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], permission_classes=[permissions.AllowAny])
    @transaction.atomic
    def place(self, request, pk=None):
        order = self.get_object()
        if order.status == "PENDING":
            order.status = "PLACED"
            order.save(update_fields=["status"])
        return Response({"id": order.id, "status": order.status})

    # Optional: invoice PDF example
    @action(detail=True, methods=["get"], permission_classes=[permissions.IsAuthenticated])
    def invoice(self, request, pk=None):
        order = self.get_object()
        buf = BytesIO()
        p = canvas.Canvas(buf, pagesize=A4)
        width, height = A4
        y = height - 20 * mm
        p.setFont("Helvetica-Bold", 14)
        p.drawString(20 * mm, y, f"Invoice for Order #{order.id}")
        y -= 10 * mm
        p.setFont("Helvetica", 10)
        p.drawString(20 * mm, y, f"Status: {order.status}")
        y -= 8 * mm
        total = Decimal("0.00")
        for oi in order.items.select_related("menu_item").all():
            line = f"{oi.menu_item.name} x {oi.quantity} @ {oi.unit_price} = {oi.quantity * oi.unit_price}"
            p.drawString(20 * mm, y, line)
            y -= 6 * mm
            total += oi.quantity * oi.unit_price
        y -= 6 * mm
        p.setFont("Helvetica-Bold", 11)
        p.drawString(20 * mm, y, f"Total: {total}")
        p.showPage()
        p.save()
        pdf = buf.getvalue()
        buf.close()
        resp = HttpResponse(content_type="application/pdf")
        resp["Content-Disposition"] = f'inline; filename="invoice-{order.id}.pdf"'
        resp.write(pdf)
        return resp


class CartViewSet(viewsets.ViewSet):
    permission_classes = [permissions.AllowAny]

    def _get_or_create_cart_user(self, request) -> Cart | None:
        if getattr(request.user, "is_authenticated", False):
            cart, _ = Cart.objects.get_or_create(user=request.user)
            return cart
        return None

    def _get_or_create_cart_session(self, request) -> Cart:
        if not request.session.session_key:
            try:
                request.session.create()
            except Exception:
                pass
        sk = request.session.session_key or ""
        cart, _ = Cart.objects.get_or_create(session_key=sk)
        return cart

    def _get_cart(self, request) -> Cart:
        cart = self._get_or_create_cart_user(request)
        if cart:
            return cart
        return self._get_or_create_cart_session(request)

    def list(self, request):
        cart = self._get_cart(request)
        data = {
            "id": cart.id,
            "items": [
                {"menu_item": ci.menu_item_id, "quantity": ci.quantity}
                for ci in cart.items.select_related("menu_item").all()
            ],
        }
        return Response(data)

    @action(detail=False, methods=["post"], url_path="sync")
    @transaction.atomic
    def sync(self, request):
        items = (request.data or {}).get("items") or []
        cart = self._get_cart(request)
        cart.items.all().delete()
        from menu.models import MenuItem
        for it in items:
            try:
                mid = int(it.get("menu_item"))
                qty = int(it.get("quantity") or 1)
            except Exception:
                continue
            if qty <= 0:
                continue
            try:
                mi = MenuItem.objects.get(pk=mid)
            except MenuItem.DoesNotExist:
                continue
            CartItem.objects.create(cart=cart, menu_item=mi, quantity=qty)
        data = {
            "id": cart.id,
            "items": [
                {"menu_item": ci.menu_item_id, "quantity": ci.quantity}
                for ci in cart.items.all()
            ],
        }
        return Response(data)

    @action(detail=False, methods=["post"], url_path="reset_session")
    @transaction.atomic
    def reset_session(self, request):
        # Delete existing session cart
        if request.session.session_key:
            sk = request.session.session_key
            Cart.objects.filter(session_key=sk).delete()
        # Flush session to ensure a fresh guest session
        try:
            request.session.flush()
        except Exception:
            pass
        return Response({"ok": True})
