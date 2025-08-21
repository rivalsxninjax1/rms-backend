from django.urls import path
from . import views

app_name = "promotions"

urlpatterns = [
    path("validate/", views.validate_coupon, name="validate-coupon"),
]
