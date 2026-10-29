from django.urls import path

from .rule_views import rules_page, save_journey_rules
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
    path("rules/", rules_page, name="rules"),
    path("journeys/<int:journey_id>/rules/", save_journey_rules, name="save_rules"),
    path("<uuid:run_id>/", run_detail, name="detail"),
]
