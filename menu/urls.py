from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MenuItemViewSet, MenuCategoryViewSet

app_name = "menu"

router = DefaultRouter()
router.register(r"menu/categories", MenuCategoryViewSet, basename="menu-categories")
router.register(r"menu/items", MenuItemViewSet, basename="menu-items")

urlpatterns = [
    path("", include(router.urls)),
]
