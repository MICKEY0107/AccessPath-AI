from django.urls import path

from . import views

app_name = "codebase"

urlpatterns = [
    path("", views.codebase_page, name="page"),
    path("add/", views.add_binding, name="add"),
    path("<int:binding_id>/analyze/", views.reanalyze_binding, name="analyze"),
    path("<int:binding_id>/journeys/", views.link_journeys, name="journeys"),
    path("<int:binding_id>/remove/", views.remove_binding, name="remove"),
]
