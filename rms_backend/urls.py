from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),

    # API
    path("api/", include(("accounts.urls", "accounts"), namespace="accounts")),
    path("api/", include(("menu.urls", "menu"), namespace="menu")),
    path("api/", include(("orders.urls", "orders"), namespace="orders")),
    path("api/", include(("payments.urls", "payments"), namespace="payments")),
    path("api/", include(("promotions.urls", "promotions"), namespace="promotions")),

    # Storefront (simple UI)
    path("", include(("storefront.urls", "storefront"), namespace="storefront")),
]
