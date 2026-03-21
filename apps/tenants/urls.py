from django.urls import path
from apps.tenants import views
app_name = "tenants"
urlpatterns = [
    path("",                   views.TenantListView.as_view(),   name="list"),
    path("new/",               views.TenantCreateView.as_view(), name="create"),
    path("leases/",            views.LeaseListView.as_view(),    name="leases"),
    path("leases/<uuid:pk>/",  views.LeaseDetailView.as_view(),  name="lease-detail"),
    path("<uuid:pk>/",         views.TenantDetailView.as_view(), name="detail"),
]
