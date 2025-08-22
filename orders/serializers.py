from typing import Iterable, Set, Any, Dict
from django.db import transaction
from rest_framework import serializers
from .models import Order, OrderItem

def _as_int(val) -> int | None:
    if val in (None, "", "null"):
        return None
    try:
        return int(str(val).strip())
    except Exception:
        return None

def _extract_menu_item_id(item: Dict[str, Any]) -> int | None:
    if "menu_item" in item:
        mi = item["menu_item"]
        if isinstance(mi, dict):
            return _as_int(mi.get("id"))
        return _as_int(mi)
    for k in ("id", "item", "product", "menuitem"):
        if k in item:
            return _as_int(item.get(k))
    return None

class OrderItemCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ("menu_item", "quantity")

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be at least 1.")
        return value

class OrderCreateSerializer(serializers.ModelSerializer):
    # Only keep what we actually need for a simple checkout
    items = OrderItemCreateSerializer(many=True)

    class Meta:
        model = Order
        fields = ("id", "service_type", "items")

    def _normalize_items(self, items: Iterable[dict]) -> list[dict]:
        norm: list[dict] = []
        for raw in items or []:
            mid = _extract_menu_item_id(raw)
            qty = raw.get("quantity") or raw.get("qty") or 1
            try:
                qty = int(qty)
            except Exception:
                qty = 1
            if mid:
                norm.append({"menu_item": mid, "quantity": max(qty, 1)})
        return norm

    def _validate_menu_items_exist(self, items: Iterable[dict]):
        from menu.models import MenuItem
        ids: Set[int] = {mi for mi in (_extract_menu_item_id(i) for i in items) if mi}
        if not ids:
            raise serializers.ValidationError({"items": ["No valid menu_item ids provided."]})
        found_ids = set(MenuItem.objects.filter(id__in=ids).values_list("id", flat=True))
        missing = ids - found_ids
        if missing:
            raise serializers.ValidationError({"items": [f"Invalid menu_item id(s): {sorted(missing)}"]})

    def validate(self, attrs):
        items = attrs.get("items") or []
        if not items:
            raise serializers.ValidationError({"items": ["At least one item is required."]})
        norm = self._normalize_items(items)
        if not norm:
            raise serializers.ValidationError({"items": ["No valid menu_item ids provided."]})
        attrs["items"] = norm
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        created_by = user if (getattr(user, "is_authenticated", False)) else None

        items_data = validated_data.pop("items", [])
        self._validate_menu_items_exist(items_data)

        order = Order.objects.create(
            created_by=created_by,
            **validated_data,
        )

        # Persist unit_price from current MenuItem price so reports/invoices work
        from menu.models import MenuItem
        for item in items_data:
            mi = MenuItem.objects.get(pk=item["menu_item"])
            OrderItem.objects.create(
                order=order,
                menu_item=mi,
                quantity=item["quantity"],
                unit_price=mi.price or 0,
            )

        return order
