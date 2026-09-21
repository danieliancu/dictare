from django.contrib import admin

from .models import AttemptMistake, ListeningAttempt, PracticeSession, SessionItem


class ReadOnlyAdmin(admin.ModelAdmin):
    """Diagnostic views: attempts are written by the app only."""

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class AttemptMistakeInline(admin.TabularInline):
    model = AttemptMistake
    extra = 0
    fields = [
        "position",
        "expected_word",
        "typed_word",
        "mistake_type",
        "speech_pattern",
        "severity",
    ]
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ListeningAttempt)
class ListeningAttemptAdmin(ReadOnlyAdmin):
    list_display = [
        "started_at",
        "user",
        "phrase",
        "level",
        "score",
        "word_accuracy",
        "listened_count",
        "replay_count",
        "revealed_before_check",
        "completed",
    ]
    list_filter = ["completed", "level", "revealed_before_check", "slowed_down"]
    search_fields = ["user__email", "phrase__text", "typed_answer"]
    list_select_related = ["user", "phrase"]
    date_hierarchy = "started_at"
    inlines = [AttemptMistakeInline]


@admin.register(AttemptMistake)
class AttemptMistakeAdmin(ReadOnlyAdmin):
    list_display = [
        "attempt",
        "expected_word",
        "typed_word",
        "mistake_type",
        "speech_pattern",
        "severity",
    ]
    list_filter = ["mistake_type", "speech_pattern"]
    search_fields = ["expected_word", "typed_word", "attempt__user__email"]
    list_select_related = ["attempt__phrase", "attempt__user", "speech_pattern"]


class SessionItemInline(admin.TabularInline):
    model = SessionItem
    extra = 0
    readonly_fields = ["position", "phrase"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(PracticeSession)
class PracticeSessionAdmin(ReadOnlyAdmin):
    list_display = [
        "created_at",
        "user",
        "kind",
        "level",
        "accent",
        "topic",
        "pattern",
        "target_count",
        "completed_at",
    ]
    list_filter = ["kind", "level", "accent"]
    search_fields = ["user__email", "anon_key"]
    list_select_related = ["user", "accent", "topic", "pattern"]
    date_hierarchy = "created_at"
    inlines = [SessionItemInline]
