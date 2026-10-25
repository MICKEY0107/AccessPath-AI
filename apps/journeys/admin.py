from django.contrib import admin

from .models import Journey


@admin.register(Journey)
class JourneyAdmin(admin.ModelAdmin):
    list_display = ("name", "execution_mode", "is_active", "updated_at")
    readonly_fields = ("created_at", "updated_at")
    list_filter = ("execution_mode", "is_active")
    search_fields = ("name", "goal", "start_url")
