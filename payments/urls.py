# payments/urls.py
from django.urls import path
from . import views

app_name = "payments"

urlpatterns = [
    path("create-checkout-session/<int:order_id>/", views.create_checkout_session, name="create_checkout_session"),
    path("checkout/success/", views.checkout_success, name="checkout_success"),
    path("checkout/cancel/", views.checkout_cancel, name="checkout_cancel"),
    path("stripe/webhook/", views.stripe_webhook, name="stripe_webhook"),
]
