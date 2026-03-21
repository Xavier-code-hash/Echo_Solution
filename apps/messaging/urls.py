from django.urls import path
from apps.messaging import views
app_name = "messaging"
urlpatterns = [
    path("",           views.InboxView.as_view(),        name="inbox"),
    path("compose/",   views.ComposeView.as_view(),       name="compose"),
    path("<uuid:pk>/", views.MessageDetailView.as_view(), name="message-detail"),
]
