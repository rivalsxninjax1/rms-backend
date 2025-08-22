from django.urls import path
from .views import mock_pay

app_name = "payments"

urlpatterns = [
    path("payments/mock/pay/", mock_pay, name="mock-pay"),
]
