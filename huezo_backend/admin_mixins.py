from django.urls import reverse
from django.utils.html import format_html

class RowActionsMixin:
    def row_actions(self, obj):
        app_label = obj._meta.app_label
        model_name = obj._meta.model_name
        
        change_url = reverse(f"admin:{app_label}_{model_name}_change", args=[obj.pk])
        delete_url = reverse(f"admin:{app_label}_{model_name}_delete", args=[obj.pk])
        
        return format_html(
            '<div class="flex items-center gap-1.5">'
            '  <a href="{}" class="bg-primary-600 hover:bg-primary-700 text-white font-medium px-2 py-1 rounded text-xs transition-colors">Edit</a>'
            '  <a href="{}" class="bg-red-600 hover:bg-red-700 text-white font-medium px-2 py-1 rounded text-xs transition-colors">Delete</a>'
            '</div>',
            change_url, delete_url
        )
    row_actions.short_description = "Actions"
