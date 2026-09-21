from django.contrib import admin

from .models import DailyPractice, PatternMastery


@admin.register(DailyPractice)
class DailyPracticeAdmin(admin.ModelAdmin):
    list_display = ["user", "date", "completed_count", "goal", "goal_reached_at"]
    search_fields = ["user__email"]
    date_hierarchy = "date"
    list_select_related = ["user"]


@admin.register(PatternMastery)
class PatternMasteryAdmin(admin.ModelAdmin):
    list_display = ["user", "pattern", "mastery", "exposures", "misses", "last_practiced"]
    list_filter = ["pattern__group", "pattern"]
    search_fields = ["user__email"]
    list_select_related = ["user", "pattern"]
