from rest_framework import serializers
from django.db import transaction
from menu.models import MenuItem
from .models import Order, OrderItem


class OrderItemCreateSerializer(serializers.ModelSerializer):
    menu_item = serializers.PrimaryKeyRelatedField(queryset=MenuItem.objects.all())
    quantity = serializers.IntegerField(min_value=1)

    class Meta:
        model = OrderItem
        fields = ("menu_item", "quantity")


class OrderCreateSerializer(serializers.ModelSerializer):
    """
    'items' may be omitted; the view will fallback to the session cart and
    pass normalized items to this serializer.
    """
    items = OrderItemCreateSerializer(many=True, required=False)

    class Meta:
        model = Order
        fields = ("id", "service_type", "items")

    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        created_by = user if (getattr(user, "is_authenticated", False)) else None

        items_data = validated_data.pop("items", [])
        order = Order.objects.create(created_by=created_by, **validated_data)

        for item in items_data:
            mi: MenuItem = item["menu_item"]
            qty = item["quantity"]
            OrderItem.objects.create(
                order=order,
                menu_item=mi,
                quantity=qty,
                unit_price=getattr(mi, "price", 0) or 0,
            )

        return order


# ---------- Read serializers ("My Orders") ----------
class OrderItemReadSerializer(serializers.ModelSerializer):
    menu_item_name = serializers.CharField(source="menu_item.name", read_only=True)
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ("menu_item", "menu_item_name", "quantity", "unit_price", "line_total")

    def get_line_total(self, obj):
        return obj.quantity * obj.unit_price


class OrderReadSerializer(serializers.ModelSerializer):
    items = OrderItemReadSerializer(many=True, read_only=True)
    total = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ("id", "status", "service_type", "created_at", "items", "total")

    def get_total(self, obj):
        return sum((it.quantity * it.unit_price) for it in obj.items.all())
