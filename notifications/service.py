# notifications/service.py
"""
FCM push notification service using Firebase HTTP v1 API.
Uses google-auth for token generation (no firebase-admin needed).

Setup:
  pip install google-auth requests

Add to settings.py:
  FIREBASE_CREDENTIALS_PATH = BASE_DIR / "firebase-credentials.json"

Get credentials JSON from:
  Firebase Console → Project Settings → Service Accounts → Generate new private key
"""

import json
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def _get_access_token():
    """Get a short-lived OAuth2 access token using the service account credentials."""
    from google.oauth2 import service_account
    import google.auth.transport.requests

    credentials = service_account.Credentials.from_service_account_file(
        str(settings.FIREBASE_CREDENTIALS_PATH),
        scopes=["https://www.googleapis.com/auth/firebase.messaging"],
    )
    request = google.auth.transport.requests.Request()
    credentials.refresh(request)
    return credentials.token


def _get_project_id():
    """Read project_id from the credentials file."""
    with open(str(settings.FIREBASE_CREDENTIALS_PATH)) as f:
        return json.load(f)["project_id"]


def send_push(user, title: str, body: str, data: dict = None):
    """
    Send a push notification to ALL active devices of a user.

    Args:
        user:  Django User instance
        title: Notification title
        body:  Notification body text
        data:  Optional dict of extra payload (string values only)

    Returns:
        (success_count, fail_count)
    """
    from .models import FCMDevice, Notification

    # Save to in-app notification log regardless of push result
    Notification.objects.create(
        user  = user,
        title = title,
        body  = body,
        data  = data or {},
    )

    devices = FCMDevice.objects.filter(user=user, is_active=True)
    if not devices.exists():
        logger.info(f"No active FCM devices for user {user.email}")
        return 0, 0

    try:
        token    = _get_access_token()
        proj_id  = _get_project_id()
        url      = f"https://fcm.googleapis.com/v1/projects/{proj_id}/messages:send"
        headers  = {
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
        }
    except Exception as e:
        logger.error(f"Failed to get FCM access token: {e}")
        return 0, devices.count()

    # Convert all data values to strings (FCM requirement)
    str_data = {k: str(v) for k, v in (data or {}).items()}

    success = 0
    failed  = 0

    for device in devices:
        payload = {
            "message": {
                "token": device.fcm_token,
                "notification": {
                    "title": title,
                    "body":  body,
                },
                "data": str_data,
                "android": {
                    "priority": "high",
                    "notification": {
                        "sound":       "default",
                        "click_action": "FLUTTER_NOTIFICATION_CLICK",
                    },
                },
                "apns": {
                    "payload": {
                        "aps": {
                            "sound": "default",
                            "badge": 1,
                        }
                    }
                },
            }
        }

        try:
            res = requests.post(url, headers=headers, json=payload, timeout=10)
            if res.status_code == 200:
                success += 1
            else:
                error = res.json().get("error", {})
                error_code = error.get("details", [{}])[0].get("errorCode", "")

                # Token expired/invalid — deactivate it
                if error_code in (
                    "UNREGISTERED", "INVALID_ARGUMENT",
                    "REGISTRATION_TOKEN_NOT_REGISTERED",
                ):
                    device.is_active = False
                    device.save(update_fields=["is_active"])
                    logger.info(f"Deactivated invalid FCM token for {user.email}")

                failed += 1
                logger.warning(
                    f"FCM send failed for {user.email}: {res.status_code} {res.text[:200]}"
                )
        except Exception as e:
            failed += 1
            logger.error(f"FCM request error for {user.email}: {e}")

    return success, failed


def send_order_assigned_notification(order, assigned_to_user, assigned_by_user):
    """
    Notify a staff/admin member when an order is assigned to them.
    """
    send_push(
        user  = assigned_to_user,
        title = "📋 Order Assigned to You",
        body  = (
            f"Order {order.order_number} has been assigned to you"
            f" by {assigned_by_user.email}."
        ),
        data  = {
            "type":         "order_assigned",
            "order_id":     str(order.id),
            "order_number": order.order_number,
            "order_type":   order.order_type,
            "assigned_by":  assigned_by_user.email,
        },
    )


def send_order_stage_notification(order, stage: str):
    """
    Send a push notification when an order stage is updated.
    Called from orders/admin.py save_model and _bulk_update_status.
    """
    from orders.models import (
        WHITE_LABEL_STAGES, PRIVATE_LABEL_STAGES,
        FABRICS_STAGES_WITH_SWATCH, FABRICS_STAGES_NO_SWATCH,
    )

    # Stage → human label
    all_stages = dict(
        WHITE_LABEL_STAGES +
        PRIVATE_LABEL_STAGES +
        FABRICS_STAGES_WITH_SWATCH +
        FABRICS_STAGES_NO_SWATCH
    )
    stage_label = all_stages.get(stage, stage.replace("_", " ").title())

    # Stage-specific messages
    messages = {
        "order_placed":        ("🎉 Order Placed",       "Your order {num} has been placed successfully."),
        "swatch_sent":         ("🧵 Swatch Dispatched",  "Your fabric swatch for {num} is on its way!"),
        "swatch_received":     ("📬 Swatch Delivered",   "Your swatch for {num} has been delivered. Please review it."),
        "swatch_approved":     ("✅ Swatch Approved",    "Great! Bulk production for {num} will begin shortly."),
        "swatch_rework":       ("🔁 Swatch Rework",      "Your swatch for {num} needs adjustment. We're working on it."),
        "sampling_fabric":     ("🪢 Sampling Fabric",    "We're sourcing fabric samples for your order {num}."),
        "sampling_style":      ("✂️ Sampling Style",     "Your style sample for {num} is being stitched."),
        "sampling_fit":        ("📐 Sampling Fit",       "Fit check in progress for your order {num}."),
        "sample_approval":     ("👕 Sample Ready",       "Your sample for {num} is ready for review."),
        "sample_rework":       ("🔄 Sample Rework",      "Your sample for {num} is being revised."),
        "sample_approved":     ("✅ Sample Approved",    "Sample approved! Bulk production starting for {num}."),
        "fabric_procurement":  ("🏭 Procurement",        "Fabric procurement has started for your order {num}."),
        "procurement":         ("🏭 Procurement",        "Procurement has started for your order {num}."),
        "cutting":             ("✂️ Cutting",            "Cutting has started for your order {num}."),
        "production":          ("🏭 In Production",      "Your order {num} is now in production."),
        "packing":             ("📦 Packing",            "Your order {num} is being packed."),
        "payment_pending":     ("💳 Payment Required",   "Payment is due for your order {num}. Open the app to pay."),
        "payment_done":        ("✅ Payment Confirmed",  "Payment received for your order {num}. Thank you!"),
        "dispatch":            ("🚚 Dispatched",         "Your order {num} has been dispatched and is on its way!"),
        "delivered":           ("🎉 Delivered!",         "Your order {num} has been delivered. Enjoy!"),
    }

    num   = order.order_number
    title_template, body_template = messages.get(
        stage,
        (f"Order Update — {stage_label}", f"Your order {{num}} has been updated to: {stage_label}"),
    )

    title = title_template.format(num=num)
    body  = body_template.format(num=num)

    send_push(
        user  = order.customer_user,
        title = title,
        body  = body,
        data  = {
            "type":     "order_update",
            "order_id": str(order.id),
            "stage":    stage,
            "order_number": num,
        },
    )