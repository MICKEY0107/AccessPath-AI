from django.urls import path

from .views import (
    create_real_site_journey,
    remove_real_site_journey,
    run_detail,
    run_list,
    start_run,
)

app_name = "runs"

urlpatterns = [
    path("", run_list, name="list"),
    path("journeys/<int:journey_id>/start/", start_run, name="start"),
    path("journeys/new/", create_real_site_journey, name="create_journey"),
    path("journeys/<int:journey_id>/remove/", remove_real_site_journey, name="remove_journey"),
    path("<uuid:run_id>/", run_detail, name="detail"),
]
