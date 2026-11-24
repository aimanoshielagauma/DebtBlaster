
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import RedirectView

from payments.views import create_payment


urlpatterns = [
    path("admin/", admin.site.urls),

    path(
        "accounts/login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
        ),
        name="login",
    ),
    path(
        "accounts/logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),

    # Existing application pages
    path("clients/", include("clients.urls")),
    path("debts/", include("debts.urls")),
    path("payments/create/", create_payment, name="payment-create"),

    # API endpoints
    path("api/clients/", include("clients.api_urls")),
    path("api/debts/", include("debts.api_urls")),

    # Homepage
    path(
        "",
        RedirectView.as_view(url="/clients/", permanent=False),
        name="home",
    ),
]
