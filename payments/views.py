from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated

from .models import PaymentTransaction, PaymentStatus
from .serializers import PaymentTransactionSerializer
from . import gateway
from accounts.permissions import IsAdminOrStaff


# ── ADMIN: CREATE PAYMENT FOR ORDER ───────────────────────────────────

class OrderPaymentCreateView(APIView):
    """
    POST /api/payments/orders/<uuid>/create/
    Admin sets amount and creates a Razorpay payment for an order.
    Only for WL and Fabrics orders at payment_pending stage.

    Input:  { "amount": 5000.00, "notes": "optional" }
    Output: { "transaction_id", "razorpay_order_id", "amount_paise",
              "amount_inr", "currency", "key_id" }
    """
    permission_classes = [IsAuthenticated, IsAdminOrStaff]

    def post(self, request, order_id):
        from orders.models import Order

        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

        # Must be at payment_pending
        if order.status != "payment_pending":
            return Response(
                {"error": f"Order must be at payment_pending stage. Current: {order.status}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        amount = request.data.get("amount")
        if not amount:
            return Response({"error": "amount is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Check if payment already exists
        if PaymentTransaction.objects.filter(
            object_id=order.id,
            status=PaymentStatus.PENDING,
        ).exists():
            return Response(
                {"error": "A pending payment already exists for this order."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = gateway.create_payment(
                content_object = order,
                amount         = amount,
                payment_type   = "order",
                paid_by        = order.customer_user,
                notes          = request.data.get("notes", ""),
            )
            return Response(result, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response(
                {"error": f"Failed to create payment: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ── RAZORPAY WEBHOOK ───────────────────────────────────────────────────

class PaymentWebhookView(APIView):
    """
    POST /api/payments/webhook/
    Public — called by Razorpay after payment.
    Handles all payment types (orders, ebooks etc.)
    """
    permission_classes = [AllowAny]

    def post(self, request):
        # Verify signature
        webhook_body      = request.body
        webhook_signature = request.headers.get("X-Razorpay-Signature", "")

        if not gateway.verify_webhook_signature(webhook_body, webhook_signature):
            return Response({"error": "Invalid signature."}, status=status.HTTP_400_BAD_REQUEST)

        event        = request.data.get("event")
        payload      = request.data.get("payload", {})
        payment_data = payload.get("payment", {}).get("entity", {})
        refund_data  = payload.get("refund",  {}).get("entity", {})
        order_data   = payload.get("order",   {}).get("entity", {})

        if event == "payment.captured":
            success, message = gateway.handle_payment_captured(payment_data)

        elif event == "payment.failed":
            success, message = gateway.handle_payment_failed(payment_data)

        elif event == "order.paid":
            # Double confirmation — order fully paid
            # payment.captured already handled it, so just acknowledge
            success, message = True, "Order paid acknowledged."

        elif event == "refund.created":
            success, message = gateway.handle_refund_created(refund_data)

        elif event == "refund.processed":
            success, message = gateway.handle_refund_processed(refund_data)

        else:
            # Unhandled event — acknowledge so Razorpay doesn't retry
            return Response({"status": "event ignored", "event": event})

        if success:
            return Response({"status": "ok", "message": message})
        return Response({"error": message}, status=status.HTTP_400_BAD_REQUEST)


# ── CUSTOMER: CHECK PAYMENT STATUS ────────────────────────────────────

class PaymentStatusView(APIView):
    """
    GET /api/payments/orders/<uuid>/status/
    Customer checks payment status for their order.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        from orders.models import Order

        try:
            if request.user.role == "customer":
                order = Order.objects.get(id=order_id, customer_user=request.user)
            else:
                order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

        # Get latest transaction for this order
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(order)
        transaction = PaymentTransaction.objects.filter(
            content_type=ct,
            object_id=order.id,
        ).order_by("-created_at").first()

        if not transaction:
            return Response({
                "order_number":   order.order_number,
                "order_status":   order.status,
                "payment_status": "not_initiated",
            })

        serializer = PaymentTransactionSerializer(transaction)
        return Response({
            "order_number": order.order_number,
            "order_status": order.status,
            **serializer.data,
        })


# ── ADMIN: LIST ALL TRANSACTIONS ──────────────────────────────────────

class PaymentTransactionListView(APIView):
    """
    GET /api/payments/transactions/
    Admin only — list all payment transactions.
    """
    permission_classes = [IsAuthenticated, IsAdminOrStaff]

    def get(self, request):
        transactions = PaymentTransaction.objects.select_related(
            "paid_by", "content_type"
        ).all()
        serializer = PaymentTransactionSerializer(
            transactions, many=True, context={"request": request}
        )
        return Response(serializer.data)