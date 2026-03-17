from django.contrib import admin
from .models import PaymentTransaction


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ["id","payment_type","paid_by","amount","currency","status","razorpay_order_id","payment_reference","created_at","paid_at"]
    list_filter = ["payment_type","status","currency"]
    search_fields = ["razorpay_order_id","payment_reference","paid_by__email"]

    readonly_fields = [
        "id","content_type","object_id","payment_type","paid_by",
        "amount","currency","razorpay_order_id","payment_reference",
        "razorpay_signature","failure_reason","created_at","paid_at","updated_at",
    ]

    ordering = ["-created_at"]

    fieldsets = (
        ("Transaction Info", {"fields":("id","payment_type","paid_by")}),
        ("Linked Object", {"fields":("content_type","object_id"),"description":"The order or e-book this payment is for."}),
        ("Amount", {"fields":("amount","currency")}),
        ("Status", {"fields":("status","failure_reason")}),
        ("Razorpay", {"fields":("razorpay_order_id","payment_reference","razorpay_signature")}),
        ("Notes", {"fields":("notes",)}),
        ("Timestamps", {"fields":("created_at","paid_at","updated_at")}),
    )

    def has_add_permission(self,request): return False
    def has_change_permission(self,request,obj=None): return False