from notifications.models import Notification

def admin_notifications(request):
    """
    Context processor to pass unread notifications count and recent notifications
    to the admin templates.
    """
    if request.user and request.user.is_authenticated and request.user.is_staff:
        unread_notifications = Notification.objects.filter(user=request.user, is_read=False)
        unread_count = unread_notifications.count()
        recent_notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]
        return {
            'admin_unread_count': unread_count,
            'admin_recent_notifications': recent_notifications,
        }
    return {
        'admin_unread_count': 0,
        'admin_recent_notifications': [],
    }
