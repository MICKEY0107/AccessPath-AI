from django.urls import path

from .views import healthz, home, load_demo, readyz, status

app_name = "core"

urlpatterns = [
    path("", home, name="home"),
    path("demo/", load_demo, name="load_demo"),
    path("status/", status, name="status"),
    path("healthz/", healthz, name="healthz"),
    path("readyz/", readyz, name="readyz"),
]
