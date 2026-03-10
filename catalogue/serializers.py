from rest_framework import serializers
from .models import WLPrototype, WLPrototypeImage


class WLPrototypeImageSerializer(serializers.ModelSerializer):
    class Meta:
        model  = WLPrototypeImage
        fields = ["id", "storage_path", "sort_order", "uploaded_at"]


class WLPrototypeListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for catalogue listing.
    Returns thumbnail + key fields only — fast for grid/card views.
    """
    fit_sizes = serializers.ListField(
        child=serializers.CharField(),
        read_only=True,
    )

    class Meta:
        model  = WLPrototype
        fields = ["id","prototype_code","collection_name","for_gender","garment_type","thumbnail_storage_path","moq","fit_sizes","is_prebooking",
            "prebooking_close_date","is_active",]


class WLPrototypeDetailSerializer(serializers.ModelSerializer):
    """
    Full detail serializer — includes all fields + nested gallery images.
    """
    images    = WLPrototypeImageSerializer(many=True, read_only=True)
    fit_sizes = serializers.ListField(
        child=serializers.CharField(),
        read_only=True,
    )
    created_by_admin = serializers.SerializerMethodField()

    class Meta:
        model  = WLPrototype
        fields = [
            "id","prototype_code","collection_name","for_gender","garment_type","thumbnail_storage_path",
            "moq","fit_sizes","customization_available","is_prebooking","prebooking_close_date",
            "is_active","images","created_by_admin","created_at","updated_at",
        ]

    def get_created_by_admin(self, obj):
        if obj.created_by_admin:
            return {
                "id":    str(obj.created_by_admin.id),
                "email": obj.created_by_admin.email,
            }
        return None