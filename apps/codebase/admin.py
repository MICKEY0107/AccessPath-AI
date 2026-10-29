from django.contrib import admin

from .models import RepoBinding


@admin.register(RepoBinding)
class RepoBindingAdmin(admin.ModelAdmin):
    list_display = ("repo_url", "branch", "owner", "status", "commit_sha", "analysed_at")
    list_filter = ("status",)
    readonly_fields = ("summary", "error", "commit_sha", "analysed_at")
