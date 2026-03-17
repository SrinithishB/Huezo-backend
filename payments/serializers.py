from rest_framework import serializers
from .models import PaymentTransaction


class PaymentTransactionSerializer(serializers.ModelSerializer):
    paid_by = serializers.SerializerMethodField()

    class Meta:
        model = PaymentTransaction
        fields = ["id","payment_type","paid_by","amount","currency","status","razorpay_order_id","payment_reference","failure_reason","notes","created_at","paid_at"]
        read_only_fields = fields

    def get_paid_by(self,obj):
        if obj.paid_by: return {"id":str(obj.paid_by.id),"email":obj.paid_by.email}
        return None