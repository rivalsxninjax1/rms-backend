from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Order
from .serializers import OrderCreateSerializer

class IsOwnerOrStaff(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user and request.user.is_staff:
            return True
        return obj.created_by_id == getattr(request.user, "id", None)

class OrderViewSet(viewsets.ModelViewSet):
    """
    POST /api/orders/                -> create order (guest OK)
    GET  /api/orders/                -> list user's orders (auth required)
    POST /api/orders/{id}/place/     -> optional finalize step
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
            # Return readable errors to the frontend
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
