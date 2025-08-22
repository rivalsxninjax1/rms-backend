from django.db import models
from django.conf import settings


class Order(models.Model):
    SERVICE_TYPES = [
        ("DINE_IN", "Dine In"),
        ("DELIVERY", "Delivery"),
        ("TAKEAWAY", "Takeaway"),
    ]

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
    menu_item = models.ForeignKey("menu.MenuItem", on_delete=models.PROTECT, related_name="order_items")
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self) -> str:
        return f"{self.menu_item} × {self.quantity}"


# --- User-specific Cart (server-side) ---
class Cart(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name="carts")
    session_key = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user"], condition=models.Q(user__isnull=False), name="uniq_cart_per_user"),
            models.UniqueConstraint(fields=["session_key"], name="uniq_cart_per_session"),
        ]

    def __str__(self) -> str:
        owner = self.user or f"session:{self.session_key[:8]}"
        return f"Cart({owner})"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    menu_item = models.ForeignKey("menu.MenuItem", on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ("cart", "menu_item")

    def __str__(self) -> str:
        return f"{self.menu_item} × {self.quantity}"
