from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend
from .models import MenuCategory, MenuItem, ModifierGroup, Modifier
from .serializers import MenuCategorySerializer, MenuItemSerializer, ModifierGroupSerializer, ModifierSerializer

class MenuCategoryViewSet(viewsets.ModelViewSet):
    queryset = MenuCategory.objects.prefetch_related('items').all()
    serializer_class = MenuCategorySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['organization', 'is_active']

class MenuItemViewSet(viewsets.ModelViewSet):
    queryset = MenuItem.objects.select_related('category').prefetch_related('modifier_groups__modifiers').all()
    serializer_class = MenuItemSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['category', 'is_available', 'is_vegetarian']

class ModifierGroupViewSet(viewsets.ModelViewSet):
    queryset = ModifierGroup.objects.prefetch_related('modifiers', 'menu_items').all()
    serializer_class = ModifierGroupSerializer

class ModifierViewSet(viewsets.ModelViewSet):
    queryset = Modifier.objects.select_related('modifier_group').all()
    serializer_class = ModifierSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['modifier_group', 'is_available']