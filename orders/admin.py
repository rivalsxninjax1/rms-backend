from django.contrib import admin
from .models import Order, OrderItem, Cart, CartItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    raw_id_fields = ("menu_item",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "service_type", "created_by", "organization", "location", "created_at")
    list_filter = ("status", "service_type", "created_at")
    date_hierarchy = "created_at"
    search_fields = ("id", "created_by__username")
    raw_id_fields = ("created_by", "organization", "location")
    inlines = [OrderItemInline]


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "session_key", "created_at")
    search_fields = ("user__username", "session_key")
    raw_id_fields = ("user",)


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("id", "cart", "menu_item", "quantity")
    raw_id_fields = ("cart", "menu_item")
