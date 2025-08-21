from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),

    # API
    path("api/", include("accounts.urls")),
    path("api/", include("core.urls")),
    path("api/", include("menu.urls")),
    path("api/", include("orders.urls")),
    path("api/", include("billing.urls")),
    path("api/", include("reservations.urls")),
    path("api/", include("reports.urls")),
    path("api/promotions/", include("promotions.urls")),
    path("api/payments/", include("payments.urls")),

    # Schema/docs
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),

    # Storefront
    path("", include("storefront.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
