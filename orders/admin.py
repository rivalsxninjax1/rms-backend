from django.contrib import admin
from django.apps import apps
from .models import Order, Cart, CartItem

def _get_model(app_label: str, model_name: str):
    try:
        return apps.get_model(app_label, model_name)
    except Exception:
        return None

def _field_exists(model, name: str) -> bool:
    if not model:
        return False
    try:
        return any(getattr(f, "name", None) == name for f in model._meta.get_fields())
    except Exception:
        return False

OrderItem = _get_model("orders", "OrderItem")
_raw_ids = tuple(n for n in ("menu_item", "item", "product", "menuitem") if _field_exists(OrderItem, n))

if OrderItem:
    class OrderItemInline(admin.TabularInline):
        model = OrderItem
        extra = 0
        raw_id_fields = _raw_ids
else:
    OrderItemInline = None

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "service_type", "created_by", "created_at")
    list_filter = ("status", "service_type")
    date_hierarchy = "created_at"
    search_fields = ("id", "created_by__username")
    inlines = [OrderItemInline] if OrderItemInline else []

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "session_key", "created_at")
    search_fields = ("user__username", "session_key")

@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("id", "cart", "menu_item", "quantity")
    raw_id_fields = ("cart", "menu_item")
