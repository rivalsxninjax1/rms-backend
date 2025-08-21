from django.contrib import admin
from .models import Payment

@admin.register(Payment)
class GatewayPaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "provider", "amount", "currency", "status", "created_at")
    list_filter = ("provider", "status", "currency")
    search_fields = ("provider_order_id", "provider_payment_id")
    autocomplete_fields = ("order",)
