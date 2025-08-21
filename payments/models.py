from django.db import models
from django.conf import settings

class Payment(models.Model):
    PROVIDERS = [("mock", "Mock"), ("stripe", "Stripe"), ("razorpay", "Razorpay"), ("cod", "Cash on Delivery")]
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="gateway_payments",
        related_query_name="gateway_payment",
    )
    provider = models.CharField(max_length=16, choices=PROVIDERS, default="mock")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=8, default=getattr(settings, "DEFAULT_CURRENCY", "NPR"))
    status = models.CharField(max_length=16, default="created")  # created|authorized|captured|failed
    provider_order_id = models.CharField(max_length=64, blank=True, default="")
    provider_payment_id = models.CharField(max_length=64, blank=True, default="")
    provider_signature = models.CharField(max_length=128, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        verbose_name = "Gateway Payment"
        verbose_name_plural = "Gateway Payments"
    def __str__(self): return f"{self.provider} {self.amount} {self.currency} for Order {self.order_id}"
