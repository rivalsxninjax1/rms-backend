from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db import transaction
from django.contrib.sessions.middleware import SessionMiddleware
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from .models import Order, Cart, CartItem
from .serializers import OrderCreateSerializer, CartSerializer


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
    """
    queryset = Order.objects.all().order_by("-created_at")
    serializer_class = OrderCreateSerializer

    def get_permissions(self):
        if self.action in ["create", "place"]:
            return [permissions.AllowAny()]
        if self.action in ["list", "retrieve"]:
            return [permissions.IsAuthenticated()]
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


# --- User-specific Cart API ---
@method_decorator(csrf_exempt, name="dispatch")
class CartViewSet(viewsets.ViewSet):
    """
    GET  /api/cart/          -> current cart (user or session)
    POST /api/cart/sync/     -> replace cart items [{menu_item, quantity}]
    """
    permission_classes = [permissions.AllowAny]

    def _ensure_session(self, request):
        if request.session.session_key is None:
            request.session.save()

    def _get_cart(self, request) -> Cart:
        self._ensure_session(request)
        user = request.user if request.user.is_authenticated else None
        if user:
            cart, _ = Cart.objects.get_or_create(user=user)
            return cart
        cart, _ = Cart.objects.get_or_create(session_key=request.session.session_key)
        return cart

    def list(self, request):
        cart = self._get_cart(request)
        data = {"id": cart.id, "items": [{"menu_item": ci.menu_item_id, "quantity": ci.quantity} for ci in cart.items.all()]}
        return Response(data)

    @action(detail=False, methods=["post"], url_path="sync")
    @transaction.atomic
    def sync(self, request):
        cart = self._get_cart(request)
        items = request.data if isinstance(request.data, list) else request.data.get("items", [])
        # normalize
        def as_int(v):
            try:
                return int(str(v))
            except Exception:
                return None
        norm = []
        for it in items or []:
            mid = it.get("menu_item") or it.get("id") or it.get("item") or it.get("menuitem") or (it.get("menu_item", {}) or {}).get("id")
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
