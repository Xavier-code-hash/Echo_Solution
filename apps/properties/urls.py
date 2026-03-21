from django.urls import path
from apps.properties import views
app_name = "properties"
urlpatterns = [
    path("",                                      views.PropertyListView.as_view(),   name="list"),
    path("new/",                                  views.PropertyCreateView.as_view(), name="create"),
    path("<uuid:pk>/",                            views.PropertyDetailView.as_view(), name="detail"),
    path("<uuid:pk>/edit/",                       views.PropertyEditView.as_view(),   name="edit"),
    path("<uuid:pk>/delete/",                     views.PropertyDeleteView.as_view(), name="delete"),
    path("<uuid:prop_pk>/units/new/",             views.UnitCreateView.as_view(),     name="unit-create"),
    path("<uuid:prop_pk>/units/<uuid:unit_pk>/edit/",   views.UnitEditView.as_view(),  name="unit-edit"),
    path("<uuid:prop_pk>/units/<uuid:unit_pk>/delete/", views.UnitDeleteView.as_view(), name="unit-delete"),
]
