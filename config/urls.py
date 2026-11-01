from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path, re_path

from apps.runs.views import evidence_file

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("apps.core.urls")),
    path("runs/", include("apps.runs.urls")),
    path("code/", include("apps.codebase.urls")),
    # Evidence (screenshots) is served by a view, so runs that used a saved sign-in
    # stay visible only to the person who started them.
    re_path(r"^evidence/(?P<path>.+)$", evidence_file, name="evidence"),
]
