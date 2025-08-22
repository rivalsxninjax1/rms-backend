import stripe
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from orders.models import Order
from payments.services import create_checkout_session, generate_order_invoice_pdf

@csrf_exempt
def create_checkout_session_view(request, order_id):
    """Create Stripe checkout session and redirect user to payment page (optional route)."""
    try:
        order = Order.objects.get(id=order_id)
        session = create_checkout_session(order)
        return HttpResponseRedirect(session.url)
    except Order.DoesNotExist:
        return HttpResponse("Order not found", status=404)


@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except Exception:
        return HttpResponse(status=400)

    if event.get("type") == "checkout.session.completed":
        session = event["data"]["object"]
        order_id = session.get("metadata", {}).get("order_id")
        if order_id:
            try:
                order = Order.objects.get(id=order_id)
                order.is_paid = True
                order.stripe_session_id = session.get("id", "") or order.stripe_session_id
                order.stripe_payment_intent_id = session.get("payment_intent", "") or order.stripe_payment_intent_id
                order.status = "PAID"
                order.save(update_fields=["is_paid", "stripe_session_id", "stripe_payment_intent_id", "status"])
                # Generate invoice now
                generate_order_invoice_pdf(order)
            except Order.DoesNotExist:
                pass

    return HttpResponse(status=200)


def checkout_success(request):
    """Payment success page. Clears session cart; template clears localStorage cart."""
    order_id = request.GET.get("order_id")
    order = None
    if order_id:
        try:
            order = Order.objects.get(pk=order_id)
        except Order.DoesNotExist:
            pass

    # Clear server-side session cart
    try:
        request.session["cart"] = []
        request.session.modified = True
    except Exception:
        pass

    return render(request, "payments/checkout_success.html", {"order": order})


def checkout_cancel(request):
    return render(request, "payments/checkout_cancel.html")
