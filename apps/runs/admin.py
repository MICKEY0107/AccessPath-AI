from django.contrib import admin

from .models import Finding, Run, RunArtifact, RunStep


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


@admin.register(Finding)
class FindingAdmin(admin.ModelAdmin):
    list_display = (
        "rule_id",
        "wcag_criterion",
        "severity",
        "status",
        "ignored",
        "run",
        "created_at",
    )
    list_filter = ("severity", "status", "rule_id", "ignored")
    search_fields = ("title", "summary", "url")
    readonly_fields = ("data",)
