from django.contrib import admin

from .models import Run, RunArtifact, RunStep


@admin.register(Run)
class RunAdmin(admin.ModelAdmin):
    list_display = ("id", "journey", "planner_provider", "status", "outcome", "created_at")
    list_filter = ("planner_provider", "status", "outcome")
    search_fields = ("id", "journey__name")
    readonly_fields = ("id", "created_at", "started_at", "finished_at")


@admin.register(RunStep)
class RunStepAdmin(admin.ModelAdmin):
    list_display = ("run", "step_number", "created_at")
    search_fields = ("run__id",)
    readonly_fields = ("created_at",)


@admin.register(RunArtifact)
class RunArtifactAdmin(admin.ModelAdmin):
    list_display = ("run", "kind", "relative_path", "created_at")
    list_filter = ("kind",)
    search_fields = ("run__id", "relative_path")
    readonly_fields = ("created_at",)
