from decimal import Decimal
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from orders.models import Order

@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def mock_pay(request):
    data = request.data or {}
    try:
        order_id = int(data.get("order_id"))
        amount = Decimal(str(data.get("amount", "0")))
    except Exception:
        return Response({"detail": "Invalid payload"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        order = Order.objects.get(pk=order_id)
    except Order.DoesNotExist:
        return Response({"detail": "Order not found"}, status=status.HTTP_404_NOT_FOUND)

    if order.status in ("PENDING", "PLACED"):
        order.status = "PAID"
        order.save(update_fields=["status"])
        return Response({"status": "captured", "order_id": order.id})
    return Response({"status": "noop", "order_id": order.id})
