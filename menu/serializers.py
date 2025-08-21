from rest_framework import serializers
from .models import MenuCategory, MenuItem, ModifierGroup, Modifier

class ModifierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Modifier
        fields = '__all__'

class ModifierGroupSerializer(serializers.ModelSerializer):
    modifiers = ModifierSerializer(many=True, read_only=True)
    
    class Meta:
        model = ModifierGroup
        fields = '__all__'

class MenuItemSerializer(serializers.ModelSerializer):
    modifier_groups = ModifierGroupSerializer(many=True, read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = MenuItem
        fields = '__all__'

class MenuCategorySerializer(serializers.ModelSerializer):
    items = MenuItemSerializer(many=True, read_only=True)
    items_count = serializers.IntegerField(source='items.count', read_only=True)
    
    class Meta:
        model = MenuCategory
        fields = '__all__'