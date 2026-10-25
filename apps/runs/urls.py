from django.urls import path

from .views import run_detail, run_list, start_run

app_name = "runs"

urlpatterns = [
    path("", run_list, name="list"),
    path("journeys/<int:journey_id>/start/", start_run, name="start"),
    path("<uuid:run_id>/", run_detail, name="detail"),
]
