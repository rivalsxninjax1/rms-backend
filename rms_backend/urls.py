from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
urlpatterns = [
    path("admin/", admin.site.urls),

    # API
    path("api/", include(("accounts.urls", "accounts"), namespace="accounts")),
    path("api/", include(("menu.urls", "menu"), namespace="menu")),
    path("api/", include(("orders.urls", "orders"), namespace="orders")),
    path("api/", include(("payments.urls", "payments"), namespace="payments")),
    path("api/", include(("promotions.urls", "promotions"), namespace="promotions")),
    path("", include(("payments.urls", "payments"), namespace="payments")),

    # Storefront (simple UI)
    path("", include(("storefront.urls", "storefront"), namespace="storefront")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)