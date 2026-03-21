"""Echo_Solutions root URL configuration."""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

admin.site.site_header = "Echo_Solutions Administration"
admin.site.site_title  = "Echo_Solutions Admin"
admin.site.index_title = "Property Management System"

urlpatterns = [
    path("admin/",       admin.site.urls),
    path("",             include("apps.landing.urls",        namespace="landing")),
    path("auth/",        include("apps.authentication.urls", namespace="auth")),
    path("dashboard/",   include("apps.dashboard.urls",      namespace="dashboard")),
    path("properties/",  include("apps.properties.urls",     namespace="properties")),
    path("tenants/",     include("apps.tenants.urls",        namespace="tenants")),
    path("payments/",    include("apps.payments.urls",       namespace="payments")),
    path("maintenance/", include("apps.maintenance.urls",    namespace="maintenance")),
    path("messages/",    include("apps.messaging.urls",      namespace="messaging")),
    path("reports/",     include("apps.reports.urls",        namespace="reports")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,  document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
