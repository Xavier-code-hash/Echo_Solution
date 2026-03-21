from django.contrib import admin
from apps.payments.models import MpesaCallbackLog, Receipt


@admin.register(MpesaCallbackLog)
class MpesaCallbackLogAdmin(admin.ModelAdmin):
    list_display    = ("created_at", "checkout_id", "result_code", "result_desc", "payment", "invoice")
    list_filter     = ("result_code", "created_at")
    search_fields   = ("checkout_id", "result_desc", "payment__mpesa_ref", "payment__mpesa_checkout")
    readonly_fields = ("raw", "created_at")


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display  = (
        "receipt_number", "issued_at", "tenant", "invoice",
        "amount", "gateway", "gateway_ref",
    )
    list_filter   = ("gateway", "issued_at")
    search_fields = (
        "receipt_number", "gateway_ref",
        "tenant__email", "tenant__first_name", "tenant__last_name",
        "invoice__invoice_number",
        "payment__stripe_pi_id", "payment__mpesa_ref", "payment__paypal_order",
    )
    readonly_fields = (
        "receipt_number", "issued_at", "payment", "invoice",
        "tenant", "amount", "gateway", "gateway_ref",
    )
    ordering = ("-issued_at",)

    def has_add_permission(self, request):
        # Receipts are auto-generated — never created manually via admin
        return False

    def has_delete_permission(self, request, obj=None):
        # Receipts are immutable audit records
        return False