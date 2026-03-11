from rest_framework import serializers
from .models import WLPrototype, WLPrototypeImage


class WLPrototypeImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model  = WLPrototypeImage
        fields = ["id", "image_url", "sort_order", "uploaded_at"]

    def get_image_url(self, obj):
        request = self.context.get("request")
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return obj.image.url if obj.image else None


class WLPrototypeListSerializer(serializers.ModelSerializer):
    fit_sizes     = serializers.ListField(child=serializers.CharField(), read_only=True)
    thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model  = WLPrototype
        fields = [
            "id", "prototype_code", "collection_name",
            "for_gender", "garment_type",
            "thumbnail_url", "moq", "fit_sizes",
            "is_prebooking", "prebooking_close_date", "is_active",
        ]

    def get_thumbnail_url(self, obj):
        request = self.context.get("request")
        if obj.thumbnail and request:
            return request.build_absolute_uri(obj.thumbnail.url)
        return obj.thumbnail.url if obj.thumbnail else None


class WLPrototypeDetailSerializer(serializers.ModelSerializer):
    fit_sizes        = serializers.ListField(child=serializers.CharField(), read_only=True)
    thumbnail_url    = serializers.SerializerMethodField()
    images           = WLPrototypeImageSerializer(many=True, read_only=True)
    created_by_admin = serializers.SerializerMethodField()

    class Meta:
        model  = WLPrototype
        fields = [
            "id", "prototype_code", "collection_name",
            "for_gender", "garment_type",
            "thumbnail_url", "moq", "fit_sizes",
            "customization_available",
            "is_prebooking", "prebooking_close_date", "is_active",
            "images", "created_by_admin",
            "created_at", "updated_at",
        ]

    def get_thumbnail_url(self, obj):
        request = self.context.get("request")
        if obj.thumbnail and request:
            return request.build_absolute_uri(obj.thumbnail.url)
        return obj.thumbnail.url if obj.thumbnail else None

    def get_created_by_admin(self, obj):
        if obj.created_by_admin:
            return {"id": str(obj.created_by_admin.id), "email": obj.created_by_admin.email}
        return None