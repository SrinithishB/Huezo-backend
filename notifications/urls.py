# notifications/urls.py

from django.urls import path
from .views import (
    RegisterFCMTokenView,
    NotificationListView,
    MarkNotificationsReadView,
    UnreadCountView,
    DeleteAllNotificationsView,
    NotificationDetailView,
)

urlpatterns = [
    # Register device token (call on app start + login)
    path("notifications/register-token/", RegisterFCMTokenView.as_view(),       name="fcm-register"),

    # In-app notification list (GET) / bulk delete (DELETE)
    path("notifications/",               NotificationListView.as_view(),        name="notification-list"),
    path("notifications/delete-all/",    DeleteAllNotificationsView.as_view(),  name="notification-delete-all"),
    path("notifications/mark-read/",     MarkNotificationsReadView.as_view(),   name="notification-mark-read"),
    path("notifications/unread-count/",  UnreadCountView.as_view(),             name="notification-unread-count"),

    # Single notification — GET auto-marks as read, DELETE removes it
    path("notifications/<uuid:pk>/",     NotificationDetailView.as_view(),      name="notification-detail"),
]