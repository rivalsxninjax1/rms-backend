from decimal import Decimal
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from .models import Payment

@api_view(["POST"])
@permission_classes([AllowAny])  # guest checkout can pay mock
def mock_pay(request):
    """Mock payment: captures immediately."""
    try:
        order_id = int(request.data.get("order_id"))
        amount = Decimal(str(request.data.get("amount", "0")))
        currency = (request.data.get("currency") or "NPR").upper()
    except Exception:
        return Response({"detail": "order_id (int), amount (decimal), currency required"}, status=400)
    if amount <= 0:
        return Response({"detail": "amount must be > 0"}, status=400)
    p = Payment.objects.create(order_id=order_id, amount=amount, currency=currency, provider="mock", status="captured")
    return Response({"status": "captured", "payment_id": p.pk}, status=status.HTTP_201_CREATED)
