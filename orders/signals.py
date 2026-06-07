from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from .models import Order, ALL_STATUS_CHOICES

STATUS_DICT = dict(ALL_STATUS_CHOICES)


@receiver(pre_save, sender=Order)
def order_pre_save(sender, instance, **kwargs):
    """
    Cache original values of fields in the instance to track changes in post_save.
    """
    if instance.pk:
        try:
            old_instance = Order.objects.get(pk=instance.pk)
            instance._old_status = old_instance.status
            instance._old_assigned_to_id = old_instance.assigned_to_id
            instance._old_total_quantity = old_instance.total_quantity
            instance._old_size_breakdown = old_instance.size_breakdown
            instance._old_notes = old_instance.notes
            instance._old_tracking_code = old_instance.tracking_code
        except Order.DoesNotExist:
            pass


@receiver(post_save, sender=Order)
def order_post_save(sender, instance, created, **kwargs):
    """
    Trigger notifications to the assigned staff member when relevant fields are updated.
    """
    # Only notify if staff is assigned
    if not instance.assigned_to:
        return

    # If assignment changed, do not trigger generic update notifications
    # (send_order_assigned_notification already handles assignment events)
    old_assigned_to_id = getattr(instance, "_old_assigned_to_id", None)
    if not created and old_assigned_to_id != instance.assigned_to_id:
        return

    # If just created and assigned, send a creation notice
    if created:
        try:
            from notifications.service import send_push
            send_push(
                user  = instance.assigned_to,
                title = f"🆕 New Order: {instance.order_number}",
                body  = f"A new order {instance.order_number} has been created and assigned to you.",
                data  = {
                    "type":         "order_staff_update",
                    "order_id":     str(instance.id),
                    "order_number": instance.order_number,
                    "order_type":   instance.order_type,
                    "change_type":  "created",
                },
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(
                f"Failed to send order creation notification to staff: {e}"
            )
        return

    # Retrieve old cached values
    old_status         = getattr(instance, "_old_status", None)
    old_total_quantity = getattr(instance, "_old_total_quantity", None)
    old_size_breakdown = getattr(instance, "_old_size_breakdown", None)
    old_notes          = getattr(instance, "_old_notes", None)
    old_tracking_code  = getattr(instance, "_old_tracking_code", None)

    changes = []
    change_type = "update"

    # Detect updates
    if old_status and old_status != instance.status:
        if instance.status in ("advance_paid", "payment_done"):
            change_type = "payment"
        changes.append(f"Status changed to '{STATUS_DICT.get(instance.status, instance.status)}'")

    if old_total_quantity is not None and old_total_quantity != instance.total_quantity:
        changes.append(f"Quantity changed from {old_total_quantity} to {instance.total_quantity}")

    if old_size_breakdown != instance.size_breakdown:
        changes.append("Size breakdown updated")

    if old_notes != instance.notes:
        changes.append("Admin notes updated")

    if old_tracking_code != instance.tracking_code:
        changes.append("Tracking details updated")

    # Send push notification if changes occurred
    if changes:
        try:
            from notifications.service import send_push

            details = ", ".join(changes)

            if change_type == "payment":
                title = f"💰 Payment Done: {instance.order_number}"
                body  = f"Payment update: {STATUS_DICT.get(instance.status, instance.status)}."
                # Append other changes if they occurred at the same time
                other_changes = [c for c in changes if "Status" not in c]
                if other_changes:
                    body += f" Other updates: {', '.join(other_changes)}."
            else:
                title = f"🔄 Order Updated: {instance.order_number}"
                body  = f"Order details updated: {details}."

            send_push(
                user  = instance.assigned_to,
                title = title,
                body  = body,
                data  = {
                    "type":         "order_staff_update",
                    "order_id":     str(instance.id),
                    "order_number": instance.order_number,
                    "order_type":   instance.order_type,
                    "change_type":  change_type,
                },
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(
                f"Failed to send order update notification to staff: {e}"
            )
