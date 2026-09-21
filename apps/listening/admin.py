from django.contrib import admin, messages
from django.db.models import Count
from django.utils.html import format_html

from apps.ai.services.tts import TTSUnavailable, get_or_create_variant

from .models import (
    Accent,
    AudioVariant,
    Level,
    ListeningPhrase,
    PhrasePattern,
    SpeechPattern,
    Topic,
)


@admin.display(description="Ascultă")
def audio_preview(obj):
    if obj.audio_file:
        return format_html('<audio controls preload="none" src="{}"></audio>', obj.audio_file.url)
    return "—"


class PhrasePatternInline(admin.TabularInline):
    model = PhrasePattern
    extra = 1
    fields = ["pattern", "fragment", "sounds_like", "explanation_ro"]
    autocomplete_fields = ["pattern"]


class AudioVariantInline(admin.TabularInline):
    model = AudioVariant
    extra = 0
    fields = ["level", "accent", "voice", "provider", "audio_file", "duration_ms", audio_preview]
    readonly_fields = [audio_preview]


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ["name_ro", "name_en", "slug", "order", "active", "phrase_count"]
    list_editable = ["order", "active"]
    search_fields = ["name_ro", "name_en", "slug"]
    prepopulated_fields = {"slug": ["name_en"]}

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(n=Count("phrases"))

    @admin.display(description="Fraze", ordering="n")
    def phrase_count(self, obj):
        return obj.n


@admin.register(Accent)
class AccentAdmin(admin.ModelAdmin):
    list_display = ["name_ro", "code", "tts_supported", "is_default", "active", "order"]
    list_editable = ["tts_supported", "active", "order"]
    search_fields = ["name_ro", "name_en", "code"]


@admin.register(SpeechPattern)
class SpeechPatternAdmin(admin.ModelAdmin):
    list_display = ["name_ro", "name_en", "slug", "group", "order", "usage"]
    list_filter = ["group"]
    list_editable = ["order"]
    search_fields = ["name_ro", "name_en", "slug"]
    prepopulated_fields = {"slug": ["name_en"]}

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(n=Count("phrase_patterns"))

    @admin.display(description="Folosit în fraze", ordering="n")
    def usage(self, obj):
        return obj.n


@admin.register(ListeningPhrase)
class ListeningPhraseAdmin(admin.ModelAdmin):
    list_display = ["text", "topic", "difficulty", "active", "pattern_list", "audio_count"]
    list_filter = ["active", "difficulty", "topic", "patterns"]
    list_editable = ["difficulty", "active"]
    search_fields = ["text", "translation_ro", "slug"]
    readonly_fields = ["slug", "created_at", "updated_at"]
    list_select_related = ["topic"]
    list_per_page = 50
    inlines = [PhrasePatternInline, AudioVariantInline]
    actions = ["generate_audio", "activate", "deactivate"]
    fieldsets = [
        (None, {"fields": ["text", "translation_ro", "topic", "difficulty", "active"]}),
        ("Meta", {"fields": ["slug", "created_at", "updated_at"], "classes": ["collapse"]}),
    ]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(n_audio=Count("audio_variants", distinct=True))
            .prefetch_related("patterns")
        )

    @admin.display(description="Tipare")
    def pattern_list(self, obj):
        return ", ".join(p.name_ro for p in obj.patterns.all())

    @admin.display(description="Audio", ordering="n_audio")
    def audio_count(self, obj):
        return obj.n_audio

    @admin.action(description="Generează audio (toate nivelurile, accentul implicit)")
    def generate_audio(self, request, queryset):
        accent = Accent.default()
        made = 0
        try:
            for phrase in queryset:
                for level in Level.values:
                    get_or_create_variant(phrase, level, accent)
                    made += 1
        except TTSUnavailable as exc:
            self.message_user(request, f"Audio indisponibil: {exc}", messages.ERROR)
            return
        self.message_user(request, f"{made} variante audio disponibile (din cache sau generate).")

    @admin.action(description="Activează")
    def activate(self, request, queryset):
        queryset.update(active=True)

    @admin.action(description="Dezactivează")
    def deactivate(self, request, queryset):
        queryset.update(active=False)


@admin.register(PhrasePattern)
class PhrasePatternAdmin(admin.ModelAdmin):
    list_display = ["phrase", "pattern", "fragment", "sounds_like", "start_token", "end_token"]
    list_filter = ["pattern__group", "pattern"]
    search_fields = ["phrase__text", "fragment", "explanation_ro"]
    list_select_related = ["phrase", "pattern"]
    autocomplete_fields = ["phrase", "pattern"]


@admin.register(AudioVariant)
class AudioVariantAdmin(admin.ModelAdmin):
    list_display = [
        "phrase",
        "level",
        "accent",
        "voice",
        "provider",
        "duration_ms",
        "generated_at",
        audio_preview,
    ]
    list_filter = ["level", "accent", "provider"]
    search_fields = ["phrase__text", "voice"]
    list_select_related = ["phrase", "accent"]
    autocomplete_fields = ["phrase"]
    readonly_fields = ["cache_key", "generated_at", audio_preview]
    date_hierarchy = "generated_at"
