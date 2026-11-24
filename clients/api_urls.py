
from django.urls import path

from . import api

urlpatterns = [
    path("", api.client_list_create, name="api-client-list-create"),
    path(
        "<int:client_id>/",
        api.client_detail,
        name="api-client-detail",
    ),
    path(
        "<int:client_id>/archive/",
        api.client_archive,
        name="api-client-archive",
    ),
]
