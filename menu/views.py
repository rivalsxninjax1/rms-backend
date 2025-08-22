from rest_framework import viewsets, permissions
from .models import MenuItem, MenuCategory
from .serializers import MenuItemSerializer, MenuCategorySerializer

class MenuCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MenuCategory.objects.all().order_by("name")
    serializer_class = MenuCategorySerializer
    permission_classes = [permissions.AllowAny]

class MenuItemViewSet(viewsets.ReadOnlyModelViewSet):
    # FIX: the model uses `is_available`, not `is_active`
    queryset = MenuItem.objects.filter(is_available=True).order_by("sort_order", "name")
    serializer_class = MenuItemSerializer
    permission_classes = [permissions.AllowAny]
