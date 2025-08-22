from rest_framework import serializers
from .models import MenuItem, MenuCategory

class MenuCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuCategory
        fields = ("id", "name", "description")

class MenuItemSerializer(serializers.ModelSerializer):
    category = MenuCategorySerializer(read_only=True)

    class Meta:
        model = MenuItem
        # FIX: expose `is_available` (the actual field on the model)
        fields = (
            "id",
            "name",
            "description",
            "price",
            "image",
            "category",
            "is_available",
            "is_vegetarian",
            "preparation_time",
            "sort_order",
            "created_at",
        )
