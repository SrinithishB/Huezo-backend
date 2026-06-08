from django.urls import reverse
from django.utils.html import format_html

class RowActionsMixin:
    def changelist_view(self, request, extra_context=None):
        self.request = request
        return super().changelist_view(request, extra_context)

    def row_actions(self, obj):
        app_label = obj._meta.app_label
        model_name = obj._meta.model_name
        
        request = getattr(self, "request", None)
        
        can_change = True
        can_delete = True
        if request:
            can_change = request.user.has_perm(f"{app_label}.change_{model_name}")
            can_delete = request.user.has_perm(f"{app_label}.delete_{model_name}")
            if hasattr(self, "has_change_permission"):
                can_change = self.has_change_permission(request, obj)
            if hasattr(self, "has_delete_permission"):
                can_delete = self.has_delete_permission(request, obj)
        
        buttons = []
        if can_change:
            change_url = reverse(f"admin:{app_label}_{model_name}_change", args=[obj.pk])
            buttons.append(
                format_html('<a href="{}" class="bg-primary-600 hover:bg-primary-700 text-white font-medium px-2 py-1 rounded text-xs transition-colors">Edit</a>', change_url)
            )
        if can_delete:
            delete_url = reverse(f"admin:{app_label}_{model_name}_delete", args=[obj.pk])
            buttons.append(
                format_html('<a href="{}" class="bg-red-600 hover:bg-red-700 text-white font-medium px-2 py-1 rounded text-xs transition-colors">Delete</a>', delete_url)
            )
        
        from django.utils.safestring import mark_safe
        return format_html(
            '<div class="flex items-center gap-1.5">{}</div>',
            mark_safe("".join(buttons))
        )
    row_actions.short_description = "Actions"
