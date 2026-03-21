from django.contrib import admin
from apps.landing.models import CallbackRequest


@admin.register(CallbackRequest)
class CallbackRequestAdmin(admin.ModelAdmin):
    list_display = ("created_at", "full_name", "phone", "preferred_time", "status")
    list_filter = ("status", "preferred_time", "created_at")
    search_fields = ("full_name", "phone", "email", "message")
    readonly_fields = ("created_at", "contacted_at")
