from rest_framework import serializers
from django.utils import timezone
from .models import Enquiry, EnquiryImage


# ── IMAGE ──────────────────────────────────────────────────────────────

class EnquiryImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model  = EnquiryImage
        fields = ['id', 'image_url', 'file_name', 'file_size_bytes', 'mime_type', 'uploaded_at']
        read_only_fields = fields

    def get_image_url(self, obj):
        request = self.context.get("request")
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return obj.image.url if obj.image else None


# ── PUBLIC: CREATE ENQUIRY ─────────────────────────────────────────────

class EnquiryCreateSerializer(serializers.ModelSerializer):
    """
    Fields matching the Contact Us screen:
      Required : order_type, full_name, brand_name, email, phone, message
      Optional : for_category, source_page, wl_prototype, fabric,
                 company_age_years, total_pieces_required, annual_revenue
    """

    class Meta:
        model  = Enquiry
        fields = [
            # ── Required (shown on screen) ──────────────────────────── #
            'order_type',
            'full_name',
            'brand_name',
            'email',
            'phone',
            'message',
            # ── Optional (shown on screen) ──────────────────────────── #
            'for_category',
            # ── Optional (internal / context-driven) ────────────────── #
            'source_page',
            'wl_prototype',
            'fabric',
            'company_age_years',
            'total_pieces_required',
            'annual_revenue',
        ]
        extra_kwargs = {
            'for_category':          {'required': False, 'allow_null': True},
            'source_page':           {'required': False, 'allow_null': True},
            'wl_prototype':          {'required': False, 'allow_null': True},
            'fabric':                {'required': False, 'allow_null': True},
            'company_age_years':     {'required': False, 'allow_null': True},
            'total_pieces_required': {'required': False, 'allow_null': True},
            'annual_revenue':        {'required': False, 'allow_null': True},
        }

    def create(self, validated_data):
        images_data = self.context.get('images', [])
        enquiry     = Enquiry.objects.create(**validated_data)

        for image_file in images_data:
            EnquiryImage.objects.create(
                enquiry         = enquiry,
                image           = image_file,
                file_name       = image_file.name,
                file_size_bytes = image_file.size,
                mime_type       = image_file.content_type,
            )
        return enquiry


# ── PUBLIC: RESPONSE ───────────────────────────────────────────────────

class EnquiryResponseSerializer(serializers.ModelSerializer):
    images       = EnquiryImageSerializer(many=True, read_only=True)
    wl_prototype = serializers.SerializerMethodField()
    fabric       = serializers.SerializerMethodField()

    class Meta:
        model  = Enquiry
        fields = [
            'id', 'enquiry_number', 'order_type',
            'full_name', 'phone', 'email', 'brand_name',
            'for_category', 'message', 'status',
            'source_page', 'wl_prototype', 'fabric',
            'images', 'created_at',
        ]
        read_only_fields = fields

    def get_wl_prototype(self, obj):
        if obj.wl_prototype:
            return {"id": str(obj.wl_prototype.id), "prototype_code": obj.wl_prototype.prototype_code}
        return None

    def get_fabric(self, obj):
        if obj.fabric:
            return {"id": str(obj.fabric.id), "fabric_name": obj.fabric.fabric_name}
        return None


# ── ADMIN: LIST ────────────────────────────────────────────────────────

class EnquiryListSerializer(serializers.ModelSerializer):
    assigned_to = serializers.SerializerMethodField()

    class Meta:
        model  = Enquiry
        fields = [
            'id', 'enquiry_number', 'order_type', 'full_name',
            'phone', 'email', 'brand_name', 'for_category',
            'total_pieces_required', 'status', 'is_viewed',
            'assigned_to', 'source_page', 'created_at',
        ]

    def get_assigned_to(self, obj):
        if obj.assigned_to_user:
            return {"id": str(obj.assigned_to_user.id), "email": obj.assigned_to_user.email}
        return None


# ── ADMIN: DETAIL ──────────────────────────────────────────────────────

class EnquiryDetailSerializer(serializers.ModelSerializer):
    images       = EnquiryImageSerializer(many=True, read_only=True)
    assigned_to  = serializers.SerializerMethodField()
    wl_prototype = serializers.SerializerMethodField()
    fabric       = serializers.SerializerMethodField()
    customer     = serializers.SerializerMethodField()

    class Meta:
        model  = Enquiry
        fields = [
            'id', 'enquiry_number', 'order_type',
            'full_name', 'phone', 'email', 'brand_name', 'for_category',
            'company_age_years', 'total_pieces_required', 'annual_revenue',
            'message', 'status', 'is_viewed', 'viewed_at',
            'admin_notes', 'assigned_to',
            'wl_prototype', 'fabric', 'customer',
            'source_page', 'images',
            'created_at', 'updated_at',
        ]

    def get_assigned_to(self, obj):
        if obj.assigned_to_user:
            return {"id": str(obj.assigned_to_user.id), "email": obj.assigned_to_user.email}
        return None

    def get_wl_prototype(self, obj):
        if obj.wl_prototype:
            return {"id": str(obj.wl_prototype.id), "prototype_code": obj.wl_prototype.prototype_code}
        return None

    def get_fabric(self, obj):
        if obj.fabric:
            return {"id": str(obj.fabric.id), "fabric_name": obj.fabric.fabric_name}
        return None

    def get_customer(self, obj):
        if obj.customer:
            return {"id": str(obj.customer.id), "brand_name": obj.customer.brand_name}
        return None


# ── ADMIN: UPDATE STATUS / ASSIGN ─────────────────────────────────────

class EnquiryUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Enquiry
        fields = ['status', 'assigned_to_user', 'admin_notes']

    def update(self, instance, validated_data):
        # Auto-mark as viewed when admin updates
        if not instance.is_viewed:
            from django.utils import timezone
            instance.is_viewed = True
            instance.viewed_at = timezone.now()
        return super().update(instance, validated_data)