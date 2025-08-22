# menu/admin.py
from django.contrib import admin
from .models import MenuItem, MenuCategory

@admin.register(MenuCategory)
class MenuCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)

@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    # FIX: use is_available (not is_active)
    list_display = ("id", "name", "price", "is_available", "category", "sort_order", "is_vegetarian", "created_at")
    list_filter = ("is_available", "category", "is_vegetarian")
    search_fields = ("name", "description")
    ordering = ("sort_order", "name")
    readonly_fields = ("created_at",)
