
from django.urls import path

from . import api

urlpatterns = [
    path("", api.debt_list_create, name="debt-list-create"),
    path("<int:debt_id>/", api.debt_detail, name="debt-detail"),
]
