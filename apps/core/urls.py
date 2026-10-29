from django.urls import path

from .views import home, load_demo, status

app_name = "core"

urlpatterns = [
    path("", home, name="home"),
    path("demo/", load_demo, name="load_demo"),
    path("status/", status, name="status"),
]
