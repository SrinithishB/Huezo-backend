# notifications/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from .models import FCMDevice, Notification


class RegisterFCMTokenView(APIView):
    """
    POST /api/notifications/register-token/
    Registers or updates a device FCM token for the logged-in user.

    Input:  { "fcm_token": "xxx", "device_id": "optional-device-id" }
    Output: { "status": "ok" }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        fcm_token = request.data.get("fcm_token", "").strip()
        device_id = request.data.get("device_id", "").strip()

        if not fcm_token:
            return Response(
                {"error": "fcm_token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Remove this token from any other user (token reassigned by Firebase)
        FCMDevice.objects.filter(fcm_token=fcm_token).exclude(user=request.user).delete()

        # Register for current user, keyed by device_id when provided
        if device_id:
            FCMDevice.objects.update_or_create(
                user      = request.user,
                device_id = device_id,
                defaults  = {"fcm_token": fcm_token, "is_active": True},
            )
        else:
            FCMDevice.objects.update_or_create(
                user      = request.user,
                fcm_token = fcm_token,
                defaults  = {"device_id": "", "is_active": True},
            )
        return Response({"status": "ok"})


class NotificationListView(APIView):
    """
    GET /api/notifications/
    Returns the last 50 in-app notifications for the logged-in user.

    Query params:
      ?unread_only=true   — only return unread notifications
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Notification.objects.filter(user=request.user)

        if request.query_params.get("unread_only") == "true":
            qs = qs.filter(is_read=False)

        notifications = qs[:50]
        data = [
            {
                "id":         str(n.id),
                "title":      n.title,
                "body":       n.body,
                "data":       n.data,
                "is_read":    n.is_read,
                "created_at": n.created_at,
            }
            for n in notifications
        ]
        return Response(data)


class MarkNotificationsReadView(APIView):
    """
    POST /api/notifications/mark-read/
    Marks all (or specific) notifications as read.

    Input:  { "ids": ["uuid1", "uuid2"] }  — mark specific
            {}                              — mark all
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ids = request.data.get("ids")
        qs  = Notification.objects.filter(user=request.user, is_read=False)
        if ids:
            qs = qs.filter(id__in=ids)
        updated = qs.update(is_read=True)
        return Response({"marked_read": updated})


class UnreadCountView(APIView):
    """
    GET /api/notifications/unread-count/
    Returns the count of unread notifications.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = Notification.objects.filter(
            user=request.user, is_read=False
        ).count()
        return Response({"unread_count": count})


class DeleteAllNotificationsView(APIView):
    """
    DELETE /api/notifications/
    Deletes all notifications for the logged-in user.

    Optional body: { "ids": ["uuid1", "uuid2"] } — delete specific ones
                   {}                             — delete all
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        ids = request.data.get("ids")
        qs  = Notification.objects.filter(user=request.user)
        if ids:
            qs = qs.filter(id__in=ids)
        deleted, _ = qs.delete()
        return Response({"deleted": deleted})


class NotificationDetailView(APIView):
    """
    GET /api/notifications/<id>/
    Returns a single notification for the logged-in user and marks it as read.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            notification = Notification.objects.get(id=pk, user=request.user)
        except Notification.DoesNotExist:
            return Response(
                {"error": "Notification not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=["is_read"])

        return Response({
            "id":         str(notification.id),
            "title":      notification.title,
            "body":       notification.body,
            "data":       notification.data,
            "is_read":    notification.is_read,
            "created_at": notification.created_at,
        })

    def delete(self, request, pk):
        try:
            notification = Notification.objects.get(id=pk, user=request.user)
        except Notification.DoesNotExist:
            return Response(
                {"error": "Notification not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        notification.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)