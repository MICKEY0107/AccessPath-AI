from django.urls import path

from .model_settings import forget_key, list_provider_models, model_settings, save_model_settings
from .rule_views import rules_page, save_journey_rules
from .views import (
    create_real_site_journey,
    export_report_html,
    export_report_json,
    map_to_code,
    verify_fix_view,
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
    path("models/", model_settings, name="model_settings"),
    path("models/save/", save_model_settings, name="save_model_settings"),
    path("models/forget/", forget_key, name="forget_key"),
    path("models/list/", list_provider_models, name="list_models"),
    path("journeys/<int:journey_id>/rules/", save_journey_rules, name="save_rules"),
    path("<uuid:run_id>/", run_detail, name="detail"),
    path("<uuid:run_id>/report.json", export_report_json, name="report_json"),
    path("<uuid:run_id>/report.html", export_report_html, name="report_html"),
    path("<uuid:run_id>/map-code/", map_to_code, name="map_code"),
    path("findings/<int:finding_id>/verify/", verify_fix_view, name="verify_fix"),
]
