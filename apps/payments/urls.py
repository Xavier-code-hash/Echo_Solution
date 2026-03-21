from django.urls import path
from apps.payments import views

app_name = "payments"

urlpatterns = [
    # Invoices
    path("",                         views.InvoiceListView.as_view(),   name="list"),
    path("new/",                     views.InvoiceCreateView.as_view(), name="invoice-create"),
    path("<uuid:pk>/",               views.InvoiceDetailView.as_view(), name="invoice-detail"),
    path("<uuid:pk>/pay/",           views.PayView.as_view(),           name="pay"),

    # Stripe
    path("stripe/confirm/",          views.stripe_confirm,              name="stripe-confirm"),
    path("webhooks/stripe/",         views.stripe_webhook,              name="stripe-webhook"),

    # M-Pesa
    path("mpesa/callback/",          views.mpesa_callback,              name="mpesa-callback"),
    path("mpesa/retry/<uuid:pk>/",   views.mpesa_retry,                 name="mpesa-retry"),

    # PayPal
    path("paypal/success/",          views.paypal_success,              name="paypal-success"),
    path("paypal/cancel/",           views.paypal_cancel,               name="paypal-cancel"),

    # Receipts
    path("receipts/",                views.receipt_list,                name="receipt-list"),
    path("receipts/<uuid:pk>/pdf/",  views.receipt_download,            name="receipt-download"),
]