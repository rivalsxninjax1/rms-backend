from django.contrib import admin
from django.apps import apps
from .models import Order

def _get_model(app_label: str, model_name: str):
    """
    Safe get_model that won't crash during system checks or before migrations.
    Returns None if the model isn't ready yet.
    """
    try:
        return apps.get_model(app_label, model_name)
    except (LookupError, ValueError):
        return None

def _field_exists(model, name: str) -> bool:
    if not model:
        return False
    try:
        for f in model._meta.get_fields():
            if getattr(f, "name", None) == name:
                return True
    except Exception:
        pass
    return False

# Try to fetch OrderItem model safely
OrderItem = _get_model("orders", "OrderItem")

# Pick a sensible raw_id field if it exists. Common names in repos: menu_item, item, product, menuitem
_raw_id_candidates = ("menu_item", "item", "product", "menuitem")
_raw_ids = tuple(n for n in _raw_id_candidates if _field_exists(OrderItem, n))

# Define Inline only if model exists; otherwise, skip inlines to avoid admin checks blowing up
if OrderItem:
    class OrderItemInline(admin.TabularInline):
        model = OrderItem
        extra = 0
        # Set raw_id_fields ONLY if the matching field(s) exist
        raw_id_fields = _raw_ids
        can_delete = True
else:
    OrderItemInline = None

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "created_at", "updated_at")
    list_filter = ("status",)
    date_hierarchy = "created_at"
    # Important: define search_fields so other admins can reference Order in autocomplete_fields
    search_fields = ("id",)

    # Attach inline if available
    inlines = [OrderItemInline] if OrderItemInline else []
