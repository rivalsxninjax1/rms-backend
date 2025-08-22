from rest_framework.routers import DefaultRouter
from .views import OrderViewSet, SessionCartViewSet

router = DefaultRouter()
router.register(r'orders', OrderViewSet, basename='orders')
router.register(r'cart', SessionCartViewSet, basename='cart')

urlpatterns = router.urls
