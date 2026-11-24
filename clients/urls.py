
from django.urls import path

from . import views

urlpatterns = [
    path("", views.client_list, name="client-list"),
    path("add/", views.client_create, name="client-create"),
    path("<int:pk>/", views.client_detail, name="client-detail"),
    path("<int:pk>/edit/", views.client_edit, name="client-edit"),
    path(
        "<int:pk>/archive/",
        views.client_toggle_archive,
        name="client-toggle-archive",
    ),
]
