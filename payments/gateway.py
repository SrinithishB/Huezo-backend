"""
payments/gateway.py
All Razorpay logic lives here.
Orders, E-Books, and any future payment type all use this single module.
Swap Razorpay for Stripe later by only changing this file.
"""
import hmac
import hashlib
import razorpay
from django.conf import settings
from django.utils import timezone

from .models import PaymentTransaction, PaymentStatus


def get_client():
    """Return authenticated Razorpay client."""
    return razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )


def create_payment(content_object, amount, payment_type, paid_by=None, notes=""):
    """
    Create a Razorpay order and a PaymentTransaction record.

    Args:
        content_object : The model instance being paid for (Order, EBook etc.)
        amount         : Amount in INR (e.g. 5000.00)
        payment_type   : "order" or "ebook"
        paid_by        : User who is paying
        notes          : Optional notes

    Returns:
        dict with razorpay_order_id, amount_paise, key_id, transaction_id
    """
    amount_paise = int(float(amount) * 100)  # Razorpay uses paise

    client = get_client()
    rz_order = client.order.create({
        "amount":   amount_paise,
        "currency": "INR",
        "receipt":  str(content_object.id)[:40],
        "notes":    {"payment_type": payment_type, "notes": notes},
    })

    # Create transaction record
    transaction = PaymentTransaction.objects.create(
        content_object    = content_object,
        payment_type      = payment_type,
        paid_by           = paid_by,
        amount            = amount,
        currency          = "INR",
        status            = PaymentStatus.PENDING,
        razorpay_order_id = rz_order["id"],
        notes             = notes,
    )

    return {
        "transaction_id":    str(transaction.id),
        "razorpay_order_id": rz_order["id"],
        "amount_paise":      amount_paise,
        "amount_inr":        float(amount),
        "currency":          "INR",
        "key_id":            settings.RAZORPAY_KEY_ID,
    }


def verify_webhook_signature(payload_body, signature):
    """
    Verify Razorpay webhook signature.
    Returns True if valid, False if invalid.
    """
    try:
        expected = hmac.new(
            settings.RAZORPAY_WEBHOOK_SECRET.encode(),
            payload_body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
    except Exception:
        return False


def handle_payment_captured(payment_entity):
    """
    Called when Razorpay fires 'payment.captured' webhook event.
    Updates transaction + triggers post-payment action on the linked object.
    """
    razorpay_order_id = payment_entity.get("order_id")
    payment_id        = payment_entity.get("id")
    signature         = payment_entity.get("signature", "")

    try:
        transaction = PaymentTransaction.objects.get(
            razorpay_order_id=razorpay_order_id
        )
    except PaymentTransaction.DoesNotExist:
        return False, "Transaction not found."

    # Update transaction
    transaction.status            = PaymentStatus.PAID
    transaction.payment_reference = payment_id
    transaction.razorpay_signature = signature
    transaction.paid_at           = timezone.now()
    transaction.save()

    # Trigger post-payment action on the linked object
    _on_payment_success(transaction)

    return True, "Payment captured."


def handle_payment_failed(payment_entity):
    """
    Called when Razorpay fires 'payment.failed' webhook event.
    """
    razorpay_order_id = payment_entity.get("order_id")
    error_description = payment_entity.get("error_description", "Payment failed.")

    try:
        transaction = PaymentTransaction.objects.get(
            razorpay_order_id=razorpay_order_id
        )
    except PaymentTransaction.DoesNotExist:
        return False, "Transaction not found."

    transaction.status         = PaymentStatus.FAILED
    transaction.failure_reason = error_description
    transaction.save()

    # Trigger post-failure action on the linked object
    _on_payment_failed(transaction)

    return True, "Payment failure recorded."


def _on_payment_success(transaction):
    """
    Post-payment success handler.
    Updates the linked object based on payment_type.
    """
    from django.utils import timezone

    if transaction.payment_type == "order":
        _handle_order_payment_success(transaction)

    elif transaction.payment_type == "ebook":
        _handle_ebook_payment_success(transaction)


def _on_payment_failed(transaction):
    """
    Post-payment failure handler.
    """
    if transaction.payment_type == "order":
        _handle_order_payment_failed(transaction)


def _handle_order_payment_success(transaction):
    """Update Order status to payment_done."""
    from orders.models import Order, OrderStageHistory

    try:
        order = Order.objects.get(id=transaction.object_id)
        order.status = "payment_done"
        order.save(update_fields=["status", "updated_at"])

        OrderStageHistory.objects.create(
            order = order,
            stage = "payment_done",
            notes = f"Payment received. Ref: {transaction.payment_reference}",
        )
    except Order.DoesNotExist:
        pass


def _handle_order_payment_failed(transaction):
    """Keep order at payment_pending on failure."""
    from orders.models import Order, OrderStageHistory

    try:
        order = Order.objects.get(id=transaction.object_id)
        OrderStageHistory.objects.create(
            order = order,
            stage = "payment_pending",
            notes = f"Payment failed: {transaction.failure_reason}",
        )
    except Order.DoesNotExist:
        pass


def _handle_ebook_payment_success(transaction):
    # TODO: implement when ebook app is built
    pass


# ── REFUND HANDLERS ────────────────────────────────────────────────────

def handle_refund_created(refund_entity):
    """Called when Razorpay fires refund.created event."""
    payment_id = refund_entity.get("payment_id")
    refund_id  = refund_entity.get("id")

    try:
        transaction = PaymentTransaction.objects.get(payment_reference=payment_id)
        transaction.status = PaymentStatus.REFUNDED
        transaction.notes  = f"{transaction.notes or ''} | Refund created: {refund_id}".strip(" |")
        transaction.save(update_fields=["status", "notes", "updated_at"])
        return True, "Refund created."
    except PaymentTransaction.DoesNotExist:
        return False, "Transaction not found."


def handle_refund_processed(refund_entity):
    """Called when Razorpay fires refund.processed event."""
    payment_id = refund_entity.get("payment_id")
    refund_id  = refund_entity.get("id")

    try:
        transaction = PaymentTransaction.objects.get(payment_reference=payment_id)

        if transaction.payment_type == "order":
            from orders.models import Order, OrderStageHistory
            try:
                order = Order.objects.get(id=transaction.object_id)
                OrderStageHistory.objects.create(
                    order = order,
                    stage = order.status,
                    notes = f"Refund processed. Razorpay Refund ID: {refund_id}",
                )
            except Order.DoesNotExist:
                pass

        return True, "Refund processed."
    except PaymentTransaction.DoesNotExist:
        return False, "Transaction not found."
    
# ── ADD THIS FUNCTION TO payments/gateway.py ──────────────────────────
#
# Place after the verify_webhook_signature function

def verify_payment_signature(razorpay_order_id, razorpay_payment_id, signature):
    """
    Verify Razorpay payment signature from client-side callback.
    Used to confirm payment after razorpay_flutter SDK returns success.

    The signature is HMAC-SHA256 of:
        razorpay_order_id + "|" + razorpay_payment_id
    using RAZORPAY_KEY_SECRET as the key.

    Returns True if valid, False if invalid.
    """
    try:
        message  = f"{razorpay_order_id}|{razorpay_payment_id}"
        expected = hmac.new(
            settings.RAZORPAY_KEY_SECRET.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
    except Exception:
        return False