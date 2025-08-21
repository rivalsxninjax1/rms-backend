from typing import Iterable, Set, Any, Dict
from django.db import transaction
from rest_framework import serializers
from .models import Order, OrderItem

# Optional: only if your project really has these models; otherwise we coerce to None.
try:
    from core.models import Organization, Location
except Exception:
    Organization = None
    Location = None


def _as_int(val) -> int | None:
    if val in (None, "", "null"):
        return None
    try:
        return int(str(val).strip())
    except Exception:
        return None


def _extract_menu_item_id(item: Dict[str, Any]) -> int | None:
    """
    Accept many shapes:
      - {"menu_item": 12}
      - {"menu_item": "12"}
      - {"menu_item": {"id": 12}}
      - {"id": 12} or {"item": 12} or {"product": 12} or {"menuitem": 12}
    """
    # direct
    if "menu_item" in item:
        mi = item["menu_item"]
        if isinstance(mi, dict):
            return _as_int(mi.get("id"))
        return _as_int(mi)
    # fallbacks / legacy keys
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
    # Accept org/location as loose strings (or omitted) and resolve them in create()
    organization = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    location = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    items = OrderItemCreateSerializer(many=True)

    class Meta:
        model = Order
        # DO NOT include created_by here (we set it in create()).
        fields = ("id", "service_type", "organization", "location", "items")

    def _resolve_org_loc(self, attrs):
        org_in = attrs.pop("organization", None)
        loc_in = attrs.pop("location", None)
        org_obj = None
        loc_obj = None
        org_pk = _as_int(org_in)
        loc_pk = _as_int(loc_in)

        if Organization and org_pk:
            try:
                org_obj = Organization.objects.get(pk=org_pk)
            except Organization.DoesNotExist:
                org_obj = None

        if Location and loc_pk:
            try:
                loc_obj = Location.objects.get(pk=loc_pk)
            except Location.DoesNotExist:
                loc_obj = None

        return org_obj, loc_obj

    def _normalize_items(self, items: Iterable[dict]) -> list[dict]:
        """
        Normalize item dicts to {"menu_item": <int>, "quantity": <int>}
        Drop any that cannot be normalized.
        """
        norm: list[dict] = []
        for raw in items or []:
            mid = _extract_menu_item_id(raw)
            qty = raw.get("quantity") or raw.get("qty") or 1
            qty = int(qty) if str(qty).isdigit() else 1
            if mid:
                norm.append({"menu_item": mid, "quantity": qty})
        return norm

    def _validate_menu_items_exist(self, items: Iterable[dict]):
        """
        Ensure all menu_item ids exist. If any missing, raise a clean error with the bad ids.
        """
        from menu.models import MenuItem  # late import to avoid app-loading issues

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
        # Normalize & reassign so .create() receives canonical items
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
        # Validate menu items exist after normalization
        self._validate_menu_items_exist(items_data)

        org_obj, loc_obj = self._resolve_org_loc(validated_data)

        order = Order.objects.create(
            created_by=created_by,
            organization=org_obj,
            location=loc_obj,
            **validated_data,
        )

        for item in items_data:
            OrderItem.objects.create(order=order, **item)

        return order
