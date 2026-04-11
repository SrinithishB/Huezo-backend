# orders/serializers.py

from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Order, OrderStageHistory, OrderImage, OrderNote, OrderType


# ── IMAGE ──────────────────────────────────────────────────────────────

class OrderImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model  = OrderImage
        fields = ["id", "image_url", "file_name", "uploaded_at"]

    def get_image_url(self, obj):
        request = self.context.get("request")
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return obj.image.url if obj.image else None


# ── STAGE HISTORY ──────────────────────────────────────────────────────

class OrderStageHistorySerializer(serializers.ModelSerializer):
    changed_by = serializers.SerializerMethodField()

    class Meta:
        model  = OrderStageHistory
        fields = ["id", "stage", "changed_by", "notes", "changed_at"]

    def get_changed_by(self, obj):
        if obj.changed_by:
            return {"id": str(obj.changed_by.id), "email": obj.changed_by.email}
        return None


# ── CUSTOMER: CREATE WL ORDER ──────────────────────────────────────────

class WLOrderCreateSerializer(serializers.Serializer):
    """
    White Label order — customer fills only:
    - white_label_catalogue (which prototype)
    - size_breakdown        (JSON string)
    - customization_notes   (optional)
    """
    white_label_catalogue = serializers.UUIDField()
    size_breakdown        = serializers.CharField(
        help_text='JSON string: [{"size":"S","quantity":60},{"size":"M","quantity":60}]',
    )
    customization_notes   = serializers.CharField(required=False, allow_blank=True)
    images                = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=False,
    )

    def validate_white_label_catalogue(self, value):
        from catalogue.models import WLPrototype
        try:
            return WLPrototype.objects.get(id=value, is_active=True)
        except WLPrototype.DoesNotExist:
            raise serializers.ValidationError("Prototype not found or inactive.")

    def validate_size_breakdown(self, value):
        import json
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                raise serializers.ValidationError(
                    'Invalid JSON. Expected: [{"size":"S","quantity":60}]'
                )
        for item in value:
            if "size" not in item or "quantity" not in item:
                raise serializers.ValidationError(
                    'Each item must have "size" and "quantity".'
                )
            if int(item["quantity"]) <= 0:
                raise serializers.ValidationError("Quantity must be greater than 0.")
        return value

    def validate(self, attrs):
        prototype      = attrs.get("white_label_catalogue")
        size_breakdown = attrs.get("size_breakdown", [])
        if prototype and size_breakdown:
            total = sum(int(i["quantity"]) for i in size_breakdown)
            if total < prototype.moq:
                raise serializers.ValidationError(
                    {"size_breakdown": f"Total quantity ({total}) is below the MOQ ({prototype.moq}) for this prototype."}
                )
        return attrs

    def create(self, validated_data):
        from .models import OrderStageHistory
        images_data    = validated_data.pop("images", [])
        prototype      = validated_data["white_label_catalogue"]
        size_breakdown = validated_data["size_breakdown"]
        request        = self.context["request"]

        total_quantity = sum(int(i["quantity"]) for i in size_breakdown)

        order = Order.objects.create(
            order_type            = OrderType.WHITE_LABEL,
            customer_user         = request.user,
            created_by_user       = request.user,
            white_label_catalogue = prototype,
            for_category          = prototype.for_gender,
            garment_type          = prototype.garment_type,
            fit_sizes             = ",".join(i["size"] for i in size_breakdown),
            size_breakdown        = size_breakdown,
            total_quantity        = total_quantity,
            moq                   = prototype.moq,
            customization_notes   = validated_data.get("customization_notes", ""),
        )

        for image_file in images_data:
            OrderImage.objects.create(
                order     = order,
                image     = image_file,
                file_name = image_file.name,
            )

        OrderStageHistory.objects.create(
            order      = order,
            stage      = "order_placed",
            changed_by = request.user,
            notes      = "Order placed by customer.",
        )
        return order


# ── CUSTOMER: CREATE PL ORDER ──────────────────────────────────────────

class PLOrderCreateSerializer(serializers.Serializer):
    style_name     = serializers.CharField(max_length=200)
    for_category   = serializers.ChoiceField(choices=["women", "men", "kids"])
    garment_type   = serializers.CharField(max_length=100)
    size_breakdown = serializers.CharField(
        help_text='JSON string: [{"size":"S","quantity":60},{"size":"M","quantity":60}]',
    )
    pl_fabric_1 = serializers.UUIDField(required=False, allow_null=True)
    pl_fabric_2 = serializers.UUIDField(required=False, allow_null=True)
    pl_fabric_3 = serializers.UUIDField(required=False, allow_null=True)
    notes  = serializers.CharField(required=False, allow_blank=True)
    images = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=False,
    )

    def _get_fabric(self, fabric_id):
        if not fabric_id:
            return None
        from catalogue.models import FabricsCatalogue
        try:
            return FabricsCatalogue.objects.get(id=fabric_id, is_active=True)
        except FabricsCatalogue.DoesNotExist:
            raise serializers.ValidationError(f"Fabric {fabric_id} not found or inactive.")

    def validate(self, attrs):
        attrs["pl_fabric_1"] = self._get_fabric(attrs.get("pl_fabric_1"))
        attrs["pl_fabric_2"] = self._get_fabric(attrs.get("pl_fabric_2"))
        attrs["pl_fabric_3"] = self._get_fabric(attrs.get("pl_fabric_3"))
        return attrs

    def validate_size_breakdown(self, value):
        import json
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                raise serializers.ValidationError(
                    'Invalid JSON. Expected: [{"size":"S","quantity":60}]'
                )
        for item in value:
            if "size" not in item or "quantity" not in item:
                raise serializers.ValidationError(
                    'Each item must have "size" and "quantity".'
                )
            if int(item["quantity"]) <= 0:
                raise serializers.ValidationError("Quantity must be greater than 0.")
        return value

    def create(self, validated_data):
        from .models import OrderStageHistory
        images_data    = validated_data.pop("images", [])
        size_breakdown = validated_data["size_breakdown"]
        request        = self.context["request"]

        total_quantity = sum(int(i["quantity"]) for i in size_breakdown)

        order = Order.objects.create(
            order_type      = OrderType.PRIVATE_LABEL,
            customer_user   = request.user,
            created_by_user = request.user,
            style_name      = validated_data["style_name"],
            for_category    = validated_data["for_category"],
            garment_type    = validated_data["garment_type"],
            fit_sizes       = ",".join(i["size"] for i in size_breakdown),
            size_breakdown  = size_breakdown,
            total_quantity  = total_quantity,
            moq             = 60,
            pl_fabric_1     = validated_data.get("pl_fabric_1"),
            pl_fabric_2     = validated_data.get("pl_fabric_2"),
            pl_fabric_3     = validated_data.get("pl_fabric_3"),
            notes           = validated_data.get("notes", ""),
        )

        for image_file in images_data:
            OrderImage.objects.create(
                order     = order,
                image     = image_file,
                file_name = image_file.name,
            )

        OrderStageHistory.objects.create(
            order      = order,
            stage      = "order_placed",
            changed_by = request.user,
            notes      = "Order placed by customer.",
        )
        return order


# ── CUSTOMER: CREATE FABRICS ORDER ────────────────────────────────────

class FabricsOrderCreateSerializer(serializers.Serializer):
    """
    Fabrics order — customer fills:
    - fabric_catalogue   (which fabric)
    - total_quantity     (meters required)
    - message            (mandatory)
    - swatch_required    (bool — does customer want a swatch first?)
    - images             (optional)
    """
    fabric_catalogue = serializers.UUIDField()
    total_quantity   = serializers.IntegerField(min_value=1)
    message          = serializers.CharField()
    swatch_required  = serializers.BooleanField(default=False)   # ← NEW
    images           = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=False,
    )

    def validate_fabric_catalogue(self, value):
        from catalogue.models import FabricsCatalogue
        try:
            return FabricsCatalogue.objects.get(id=value, is_active=True)
        except FabricsCatalogue.DoesNotExist:
            raise serializers.ValidationError("Fabric not found or inactive.")

    def validate(self, attrs):
        fabric         = attrs.get("fabric_catalogue")
        total_quantity = attrs.get("total_quantity")
        if fabric and total_quantity is not None:
            moq = fabric.effective_moq
            if moq and total_quantity < moq:
                raise serializers.ValidationError(
                    {"total_quantity": f"Total quantity ({total_quantity}) is below the MOQ ({moq}) for this fabric."}
                )
        return attrs

    def create(self, validated_data):
        from .models import OrderStageHistory
        images_data     = validated_data.pop("images", [])
        fabric          = validated_data["fabric_catalogue"]
        swatch_required = validated_data.get("swatch_required", False)
        request         = self.context["request"]

        order = Order.objects.create(
            order_type       = OrderType.FABRICS,
            customer_user    = request.user,
            created_by_user  = request.user,
            fabric_catalogue = fabric,
            fabric_type      = fabric.fabric_type,
            total_quantity   = validated_data["total_quantity"],
            moq              = fabric.effective_moq,
            message          = validated_data["message"],
            swatch_required  = swatch_required,   # ← NEW
        )

        for image_file in images_data:
            OrderImage.objects.create(
                order     = order,
                image     = image_file,
                file_name = image_file.name,
            )

        OrderStageHistory.objects.create(
            order      = order,
            stage      = "order_placed",
            changed_by = request.user,
            notes      = "Order placed by customer.",
        )
        return order


# ── LIST ORDER ─────────────────────────────────────────────────────────

class OrderListSerializer(serializers.ModelSerializer):
    customer     = serializers.SerializerMethodField()
    wl_prototype = serializers.SerializerMethodField()
    fabric       = serializers.SerializerMethodField()
    assigned_to  = serializers.SerializerMethodField()

    class Meta:
        model  = Order
        fields = [
            "id", "order_number", "order_type",
            "customer", "assigned_to", "wl_prototype", "fabric",
            "style_name", "for_category", "garment_type",
            "total_quantity", "status", "created_at",
        ]

    def get_customer(self, obj):
        return {"id": str(obj.customer_user.id), "email": obj.customer_user.email}

    def get_assigned_to(self, obj):
        if obj.assigned_to:
            return {
                "id":    str(obj.assigned_to.id),
                "email": obj.assigned_to.email,
                "role":  obj.assigned_to.role,
            }
        return None

    def get_wl_prototype(self, obj):
        if obj.white_label_catalogue:
            return {
                "id":             str(obj.white_label_catalogue.id),
                "prototype_code": obj.white_label_catalogue.prototype_code,
            }
        return None

    def get_fabric(self, obj):
        if obj.fabric_catalogue:
            return {
                "id":          str(obj.fabric_catalogue.id),
                "fabric_name": obj.fabric_catalogue.fabric_name,
            }
        return None


# ── DETAIL ORDER ───────────────────────────────────────────────────────

class OrderDetailSerializer(serializers.ModelSerializer):
    customer      = serializers.SerializerMethodField()
    created_by    = serializers.SerializerMethodField()
    wl_prototype  = serializers.SerializerMethodField()
    fabric        = serializers.SerializerMethodField()
    pl_fabrics    = serializers.SerializerMethodField()
    enquiry       = serializers.SerializerMethodField()
    images        = OrderImageSerializer(many=True, read_only=True)
    stage_history = OrderStageHistorySerializer(many=True, read_only=True)
    valid_stages  = serializers.SerializerMethodField()
    payment       = serializers.SerializerMethodField()

    class Meta:
        model  = Order
        fields = [
            "id", "order_number", "order_type",
            "customer", "created_by", "enquiry",
            "wl_prototype", "fabric", "pl_fabrics",
            "style_name", "for_category", "garment_type",
            "fit_sizes", "size_breakdown",
            "total_quantity", "moq",
            "customization_notes", "message", "fabric_type",
            "swatch_required",                              # ← NEW
            "status", "valid_stages",
            "payment_amount", "payment",
            "notes", "images", "stage_history",
            "created_at", "updated_at",
        ]

    def get_customer(self, obj):
        return {"id": str(obj.customer_user.id), "email": obj.customer_user.email}

    def get_created_by(self, obj):
        return {"id": str(obj.created_by_user.id), "email": obj.created_by_user.email}

    def get_enquiry(self, obj):
        if obj.enquiry:
            return {"id": str(obj.enquiry.id), "enquiry_number": obj.enquiry.enquiry_number}
        return None

    def get_wl_prototype(self, obj):
        if obj.white_label_catalogue:
            return {
                "id":             str(obj.white_label_catalogue.id),
                "prototype_code": obj.white_label_catalogue.prototype_code,
                "garment_type":   obj.white_label_catalogue.garment_type,
                "for_gender":     obj.white_label_catalogue.for_gender,
                "moq":            obj.white_label_catalogue.moq,
            }
        return None

    def get_fabric(self, obj):
        if obj.fabric_catalogue:
            return {
                "id":            str(obj.fabric_catalogue.id),
                "fabric_name":   obj.fabric_catalogue.fabric_name,
                "fabric_type":   obj.fabric_catalogue.fabric_type,
                "effective_moq": obj.fabric_catalogue.effective_moq,
            }
        return None

    def get_pl_fabrics(self, obj):
        fabrics = []
        for i, fabric in enumerate([obj.pl_fabric_1, obj.pl_fabric_2, obj.pl_fabric_3], start=1):
            if fabric:
                fabrics.append({
                    "choice":      i,
                    "id":          str(fabric.id),
                    "fabric_name": fabric.fabric_name,
                    "fabric_type": fabric.fabric_type,
                    "composition": fabric.composition,
                    "width_cm":    str(fabric.width_cm) if fabric.width_cm else None,
                })
        return fabrics

    def get_valid_stages(self, obj):
        return [{"value": s[0], "label": s[1]} for s in obj.valid_stages]

    def get_payment(self, obj):
        from payments.models import PaymentTransaction
        from django.contrib.contenttypes.models import ContentType
        from django.conf import settings
        ct = ContentType.objects.get_for_model(obj)
        tx = PaymentTransaction.objects.filter(
            content_type=ct, object_id=obj.id
        ).order_by("-created_at").first()
        if not tx:
            return None
        return {
            "transaction_id":    str(tx.id),
            "razorpay_order_id": tx.razorpay_order_id,
            "amount":            str(tx.amount),
            "currency":          tx.currency,
            "status":            tx.status,
            "payment_reference": tx.payment_reference,
            "paid_at":           tx.paid_at,
            "key_id":            settings.RAZORPAY_KEY_ID,
        }


# ── ADMIN: UPDATE ORDER STATUS ─────────────────────────────────────────

class OrderStatusUpdateSerializer(serializers.Serializer):
    status         = serializers.CharField()
    notes          = serializers.CharField(required=False, allow_blank=True)
    payment_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2,
        required=False, allow_null=True,
        min_value=0,
    )

    def validate_status(self, value):
        order = self.context["order"]
        valid = [s[0] for s in order.valid_stages]
        if value not in valid:
            raise serializers.ValidationError(
                f"Invalid status for {order.order_type}. Valid: {valid}"
            )
        return value


# ── ORDER NOTES ────────────────────────────────────────────────────────

class OrderNoteSerializer(serializers.ModelSerializer):
    added_by = serializers.SerializerMethodField()

    class Meta:
        model  = OrderNote
        fields = ["id", "note", "added_by", "created_at"]
        read_only_fields = ["id", "added_by", "created_at"]

    def get_added_by(self, obj):
        if obj.added_by:
            return {
                "id":    str(obj.added_by.id),
                "email": obj.added_by.email,
                "role":  obj.added_by.role,
            }
        return None


class OrderNoteCreateSerializer(serializers.Serializer):
    note = serializers.CharField(min_length=1)


# ── STAFF: PLACE ORDER ON BEHALF OF CUSTOMER ──────────────────────────

class StaffWLOrderCreateSerializer(serializers.Serializer):
    """
    Staff / Admin places a White Label order on behalf of a customer.
    Same as WLOrderCreateSerializer but requires customer_id.
    """
    customer_id           = serializers.UUIDField(help_text="UUID of the customer account")
    white_label_catalogue = serializers.UUIDField()
    size_breakdown        = serializers.CharField(
        help_text='JSON string: [{"size":"S","quantity":60},{"size":"M","quantity":60}]',
    )
    customization_notes   = serializers.CharField(required=False, allow_blank=True)
    images                = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=False,
    )

    def validate_customer_id(self, value):
        User = get_user_model()
        try:
            user = User.objects.get(id=value, is_active=True)
        except User.DoesNotExist:
            raise serializers.ValidationError("Customer not found.")
        if user.role != "customer":
            raise serializers.ValidationError("Selected user is not a customer.")
        return user

    def validate_white_label_catalogue(self, value):
        from catalogue.models import WLPrototype
        try:
            return WLPrototype.objects.get(id=value, is_active=True)
        except WLPrototype.DoesNotExist:
            raise serializers.ValidationError("Prototype not found or inactive.")

    def validate_size_breakdown(self, value):
        import json
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                raise serializers.ValidationError(
                    'Invalid JSON. Expected: [{"size":"S","quantity":60}]'
                )
        for item in value:
            if "size" not in item or "quantity" not in item:
                raise serializers.ValidationError('Each item must have "size" and "quantity".')
            if int(item["quantity"]) <= 0:
                raise serializers.ValidationError("Quantity must be greater than 0.")
        return value

    def validate(self, attrs):
        prototype      = attrs.get("white_label_catalogue")
        size_breakdown = attrs.get("size_breakdown", [])
        if prototype and size_breakdown:
            total = sum(int(i["quantity"]) for i in size_breakdown)
            if total < prototype.moq:
                raise serializers.ValidationError(
                    {"size_breakdown": f"Total quantity ({total}) is below the MOQ ({prototype.moq}) for this prototype."}
                )
        return attrs

    def create(self, validated_data):
        from .models import OrderStageHistory
        images_data    = validated_data.pop("images", [])
        customer       = validated_data["customer_id"]
        prototype      = validated_data["white_label_catalogue"]
        size_breakdown = validated_data["size_breakdown"]
        request        = self.context["request"]

        total_quantity = sum(int(i["quantity"]) for i in size_breakdown)

        order = Order.objects.create(
            order_type            = OrderType.WHITE_LABEL,
            customer_user         = customer,
            created_by_user       = request.user,
            white_label_catalogue = prototype,
            for_category          = prototype.for_gender,
            garment_type          = prototype.garment_type,
            fit_sizes             = ",".join(i["size"] for i in size_breakdown),
            size_breakdown        = size_breakdown,
            total_quantity        = total_quantity,
            moq                   = prototype.moq,
            customization_notes   = validated_data.get("customization_notes", ""),
        )

        for image_file in images_data:
            OrderImage.objects.create(
                order=order, image=image_file, file_name=image_file.name,
            )

        OrderStageHistory.objects.create(
            order      = order,
            stage      = "order_placed",
            changed_by = request.user,
            notes      = f"Order placed by staff ({request.user.email}) on behalf of customer.",
        )
        return order


class StaffFabricsOrderCreateSerializer(serializers.Serializer):
    """
    Staff / Admin places a Fabrics order on behalf of a customer.
    Same as FabricsOrderCreateSerializer but requires customer_id.
    """
    customer_id      = serializers.UUIDField(help_text="UUID of the customer account")
    fabric_catalogue = serializers.UUIDField()
    total_quantity   = serializers.IntegerField(min_value=1)
    message          = serializers.CharField()
    swatch_required  = serializers.BooleanField(default=False)
    images           = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=False,
    )

    def validate_customer_id(self, value):
        User = get_user_model()
        try:
            user = User.objects.get(id=value, is_active=True)
        except User.DoesNotExist:
            raise serializers.ValidationError("Customer not found.")
        if user.role != "customer":
            raise serializers.ValidationError("Selected user is not a customer.")
        return user

    def validate_fabric_catalogue(self, value):
        from catalogue.models import FabricsCatalogue
        try:
            return FabricsCatalogue.objects.get(id=value, is_active=True)
        except FabricsCatalogue.DoesNotExist:
            raise serializers.ValidationError("Fabric not found or inactive.")

    def validate(self, attrs):
        fabric         = attrs.get("fabric_catalogue")
        total_quantity = attrs.get("total_quantity")
        if fabric and total_quantity is not None:
            moq = fabric.effective_moq
            if moq and total_quantity < moq:
                raise serializers.ValidationError(
                    {"total_quantity": f"Total quantity ({total_quantity}) is below the MOQ ({moq}) for this fabric."}
                )
        return attrs

    def create(self, validated_data):
        from .models import OrderStageHistory
        images_data     = validated_data.pop("images", [])
        customer        = validated_data["customer_id"]
        fabric          = validated_data["fabric_catalogue"]
        swatch_required = validated_data.get("swatch_required", False)
        request         = self.context["request"]

        order = Order.objects.create(
            order_type       = OrderType.FABRICS,
            customer_user    = customer,
            created_by_user  = request.user,
            fabric_catalogue = fabric,
            fabric_type      = fabric.fabric_type,
            total_quantity   = validated_data["total_quantity"],
            moq              = fabric.effective_moq,
            message          = validated_data["message"],
            swatch_required  = swatch_required,
        )

        for image_file in images_data:
            OrderImage.objects.create(
                order=order, image=image_file, file_name=image_file.name,
            )

        OrderStageHistory.objects.create(
            order      = order,
            stage      = "order_placed",
            changed_by = request.user,
            notes      = f"Order placed by staff ({request.user.email}) on behalf of customer.",
        )
        return order


# ── ASSIGN STAFF ───────────────────────────────────────────────────────

class OrderAssignSerializer(serializers.Serializer):
    assigned_to = serializers.UUIDField(
        allow_null=True,
        required=True,
        help_text="UUID of a staff/admin user. Pass null to unassign.",
    )

    def validate_assigned_to(self, value):
        if value is None:
            return None
        User = get_user_model()
        try:
            user = User.objects.get(id=value, is_active=True)
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found.")
        if user.role not in ("admin", "staff"):
            raise serializers.ValidationError("Only admin or staff users can be assigned to orders.")
        return user