from django.urls import path
from apps.maintenance import views
app_name = "maintenance"
urlpatterns = [
    path("",           views.RequestListView.as_view(),   name="list"),
    path("new/",       views.RequestCreateView.as_view(), name="create"),
    path("<uuid:pk>/", views.RequestDetailView.as_view(), name="detail"),
]
