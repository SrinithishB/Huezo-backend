from rest_framework import serializers
from .models import Enquiry, EnquiryImage


class EnquiryImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = EnquiryImage
        fields = ['id', 'file_name', 'storage_path', 'file_size_bytes', 'mime_type', 'uploaded_at']
        read_only_fields = fields


class EnquiryCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Enquiry
        fields = [
            'order_type',
            'full_name',
            'phone',
            'email',
            'brand_name',
            'company_age_years',
            'total_pieces_required',
            'annual_revenue',
            'message',
            'source_page',
        ]

    def validate_order_type(self, value):
        valid = [choice[0] for choice in Enquiry.ORDER_TYPE_CHOICES]
        if value not in valid:
            raise serializers.ValidationError(f"order_type must be one of: {valid}")
        return value

    def create(self, validated_data):
        return Enquiry.objects.create(**validated_data)


class EnquiryResponseSerializer(serializers.ModelSerializer):
    images = EnquiryImageSerializer(many=True, read_only=True)

    class Meta:
        model = Enquiry
        fields = [
            'id',
            'enquiry_number',
            'order_type',
            'full_name',
            'phone',
            'email',
            'brand_name',
            'company_age_years',
            'total_pieces_required',
            'annual_revenue',
            'message',
            'status',
            'source_page',
            'images',
            'created_at',
        ]
        read_only_fields = fields