from rest_framework.routers import DefaultRouter
from .views import MenuCategoryViewSet, MenuItemViewSet, ModifierGroupViewSet, ModifierViewSet
app_name = "menu"

router = DefaultRouter()
router.register('menu/categories', MenuCategoryViewSet)
router.register('menu/items', MenuItemViewSet)
router.register('menu/modifier-groups', ModifierGroupViewSet)
router.register('menu/modifiers', ModifierViewSet)

urlpatterns = router.urls