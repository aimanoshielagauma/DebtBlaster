
from django.urls import path

from . import views

urlpatterns = [
    path("", views.reminder_history, name="reminder-history"),
]
