# orders/admin.py
from django.contrib import admin
from .models import Product, Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    raw_id_fields = ("product",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "price", "prep_minutes")
    search_fields = ("name",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "customer_name", "customer_email", "is_paid", "created_at", "invoice_pdf")
    list_filter = ("is_paid", "created_at")
    date_hierarchy = "created_at"
    inlines = [OrderItemInline]

    # REQUIRED for other admins' autocomplete_fields -> order
    # '=id' enables exact ID search; others allow name/email lookups
    search_fields = ("=id", "customer_name", "customer_email", "user__username", "user__email")
    raw_id_fields = ("user",)

    # Optional: speed up queries when listing orders
    list_select_related = ("user",)
    ordering = ("-created_at",)
