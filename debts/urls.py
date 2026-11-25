
from django.urls import path

from . import views

urlpatterns = [
    path("", views.debt_list, name="debt-list"),
    path("add/", views.debt_create, name="debt-create"),
    path(
        "aging-report/",
        views.debt_aging_report,
        name="debt-aging-report",
    ),
    path("<int:pk>/", views.debt_detail, name="debt-detail"),
    path("<int:pk>/edit/", views.debt_edit, name="debt-edit"),
]
