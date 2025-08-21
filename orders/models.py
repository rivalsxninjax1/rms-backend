from django.db import models
from django.conf import settings

class Order(models.Model):
    SERVICE_TYPES = [("DINE_IN", "Dine In"), ("DELIVERY", "Delivery"), ("TAKEAWAY", "Takeaway")]

    # Keep these nullable to support guest checkout / optional scoping
    organization = models.ForeignKey(
        "core.Organization", on_delete=models.SET_NULL, null=True, blank=True, related_name="orders"
    )
    location = models.ForeignKey(
        "core.Location", on_delete=models.SET_NULL, null=True, blank=True, related_name="orders"
    )

    service_type = models.CharField(max_length=16, choices=SERVICE_TYPES, default="DINE_IN")
    status = models.CharField(max_length=16, default="PENDING")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Order #{self.pk} ({self.status})"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")

    # TEMPORARY: allow null/blank so we can migrate safely first
    menu_item = models.ForeignKey(
        "menu.MenuItem",
        on_delete=models.PROTECT,
        related_name="order_items",
        null=False, blank=False,     # <-- TEMP for first migration
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self) -> str:
        return f"{self.menu_item} × {self.quantity}" if self.menu_item_id else f"<no item> × {self.quantity}"
