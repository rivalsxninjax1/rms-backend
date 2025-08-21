from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from .models import Coupon

@api_view(["POST"])
@permission_classes([AllowAny])
def validate_coupon(request):
    code = (request.data.get("code") or "").strip().upper()
    try:
        c = Coupon.objects.get(code=code)
        return Response({"valid": c.is_valid_now(), "discount_percent": c.discount_percent if c.is_valid_now() else 0})
    except Coupon.DoesNotExist:
        return Response({"valid": False, "discount_percent": 0})
