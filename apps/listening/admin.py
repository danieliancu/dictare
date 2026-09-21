from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Prefetch
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
from django.views.decorators.http import require_POST

from apps.ai.services.tts import TTSError, generate_variant

from .models import (
    Accent,
    AudioVariant,
    AudioVariantPattern,
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
    fields = [
        "pattern",
        "fragment",
        "expected_from_level",
        "sounds_like",
        "ro_approximation",
        "explanation_ro",
    ]
    autocomplete_fields = ["pattern"]


class AudioVariantInline(admin.TabularInline):
    model = AudioVariant
    extra = 0
    fields = ["level", "accent", "voice", "provider", "qa_status", "audio_file", audio_preview]
    readonly_fields = ["qa_status", audio_preview]
    show_change_link = True


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
    list_display = [
        "text",
        "topic",
        "difficulty",
        "active",
        "in_pilot",
        "pattern_list",
        "audio_count",
    ]
    list_filter = ["active", "in_pilot", "difficulty", "topic", "patterns"]
    list_editable = ["difficulty", "active"]
    search_fields = ["text", "translation_ro", "slug"]
    readonly_fields = ["slug", "created_at", "updated_at"]
    list_select_related = ["topic"]
    list_per_page = 50
    inlines = [PhrasePatternInline, AudioVariantInline]
    actions = ["generate_audio", "activate", "deactivate"]
    fieldsets = [
        (
            None,
            {"fields": ["text", "translation_ro", "topic", "difficulty", "active", "in_pilot"]},
        ),
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

    @admin.action(description="Generează audio (max. 10 fraze; altfel comanda generate_audio)")
    def generate_audio(self, request, queryset):
        if queryset.count() > 10:
            self.message_user(
                request,
                "Pentru mai mult de 10 fraze folosește comanda generate_audio (cu --dry-run).",
                messages.WARNING,
            )
            return
        accent = Accent.default()
        made = 0
        try:
            for phrase in queryset:
                for level in Level.values:
                    generate_variant(phrase, level, accent)
                    made += 1
        except TTSError as exc:
            self.message_user(request, f"Audio indisponibil ({exc.kind}): {exc}", messages.ERROR)
            return
        self.message_user(request, f"{made} variante audio (din cache sau generate, de verificat).")

    @admin.action(description="Activează")
    def activate(self, request, queryset):
        queryset.update(active=True)

    @admin.action(description="Dezactivează")
    def deactivate(self, request, queryset):
        queryset.update(active=False)


@admin.register(PhrasePattern)
class PhrasePatternAdmin(admin.ModelAdmin):
    list_display = [
        "phrase",
        "pattern",
        "fragment",
        "expected_from_level",
        "sounds_like",
        "ro_approximation",
    ]
    list_filter = ["expected_from_level", "pattern__group", "pattern"]
    search_fields = ["phrase__text", "fragment", "explanation_ro"]
    list_select_related = ["phrase", "pattern"]
    autocomplete_fields = ["phrase", "pattern"]


class AudioVariantPatternInline(admin.TabularInline):
    """Mark which phenomena are really audible in this recording."""

    model = AudioVariantPattern
    extra = 0
    fields = [
        "phrase_pattern",
        "verification",
        "realisation",
        "explanation_override_ro",
        "verified_by",
        "verified_at",
    ]
    readonly_fields = ["verified_by", "verified_at"]
    verbose_name_plural = "Tipare: ce se aude efectiv în această înregistrare"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "phrase_pattern":
            variant_id = request.resolver_match.kwargs.get("object_id")
            variant = AudioVariant.objects.filter(pk=variant_id).first() if variant_id else None
            qs = PhrasePattern.objects.select_related("pattern")
            kwargs["queryset"] = qs.filter(phrase=variant.phrase) if variant else qs.none()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.display(description="Durată")
def duration_label(obj):
    if not obj.duration_ms:
        return "—"
    seconds = f"{obj.duration_ms / 1000:.1f}s"
    return seconds if obj.duration_measured else f"≈{seconds}"


@admin.register(AudioVariant)
class AudioVariantAdmin(admin.ModelAdmin):
    list_display = [
        "phrase",
        "level",
        "accent",
        "voice",
        "provider",
        "model",
        duration_label,
        "qa_status",
        "generated_at",
        audio_preview,
    ]
    list_filter = [
        "qa_status",
        "level",
        "voice",
        "provider",
        "engine_version",
        "accent",
        "phrase__in_pilot",
    ]
    search_fields = ["phrase__text", "voice", "qa_notes"]
    list_select_related = ["phrase", "accent"]
    autocomplete_fields = ["phrase"]
    readonly_fields = [
        audio_preview,
        "model",
        "instructions",
        "speed",
        "engine_version",
        "cache_key",
        "generation_settings",
        "duration_ms",
        "duration_measured",
        "generated_at",
        "reviewed_by",
        "reviewed_at",
    ]
    fieldsets = [
        (
            None,
            {
                "fields": [
                    "phrase",
                    "level",
                    "accent",
                    "voice",
                    "provider",
                    "audio_file",
                    audio_preview,
                ]
            },
        ),
        ("QA", {"fields": ["qa_status", "qa_notes", "reviewed_by", "reviewed_at"]}),
        (
            "Generare",
            {
                "classes": ["collapse"],
                "fields": [
                    "model",
                    "instructions",
                    "speed",
                    "engine_version",
                    "duration_ms",
                    "duration_measured",
                    "cache_key",
                    "generation_settings",
                    "generated_at",
                ],
            },
        ),
    ]
    inlines = [AudioVariantPatternInline]
    actions = ["approve_selected", "reject_selected"]
    date_hierarchy = "generated_at"
    change_list_template = "admin/listening/audiovariant/change_list.html"

    def save_model(self, request, obj, form, change):
        if "qa_status" in form.changed_data:
            obj.reviewed_by = request.user
            obj.reviewed_at = timezone.now()
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        from .services.qa import mark_pattern_checked

        instances = formset.save(commit=False)
        for obj in instances:
            if isinstance(obj, AudioVariantPattern):
                mark_pattern_checked(obj, request.user)
            obj.save()
        for obj in formset.deleted_objects:
            obj.delete()

    @admin.action(description="Aprobă variantele selectate", permissions=["change"])
    def approve_selected(self, request, queryset):
        from .services.qa import set_status

        changed, skipped = set_status(queryset, AudioVariant.QAStatus.APPROVED, request.user)
        msg = f"{changed} variante aprobate."
        if skipped:
            msg += f" {skipped} omise (audio mock/placeholder sau fără fișier nu se aprobă)."
        self.message_user(request, msg)

    @admin.action(description="Respinge variantele selectate", permissions=["change"])
    def reject_selected(self, request, queryset):
        from .services.qa import set_status

        changed, _ = set_status(queryset, AudioVariant.QAStatus.REJECTED, request.user)
        self.message_user(request, f"{changed} variante respinse.")

    # --- side-by-side review --------------------------------------------------------------

    def get_urls(self):
        custom = [
            path(
                "review/",
                self.admin_site.admin_view(self.review_view),
                name="listening_audiovariant_review",
            ),
            path(
                "review/<int:pk>/status/",
                self.admin_site.admin_view(require_POST(self.review_status_view)),
                name="listening_audiovariant_review_status",
            ),
        ]
        return custom + super().get_urls()

    def review_view(self, request):
        """Clear / Natural / Fast of each phrase side by side, for listening QA."""
        if not self.has_view_permission(request):
            raise PermissionDenied
        only_pilot = request.GET.get("pilot", "1") == "1"
        status = request.GET.get("status", "")
        voice = request.GET.get("voice", "")
        variants = AudioVariant.objects.exclude(provider="mock").select_related("accent")
        if status:
            variants = variants.filter(qa_status=status)
        if voice:
            variants = variants.filter(voice=voice)
        phrases = (
            ListeningPhrase.objects.active()
            .order_by("pk")
            .prefetch_related(
                Prefetch(
                    "audio_variants",
                    queryset=variants.order_by("level", "-generated_at"),
                    to_attr="review_variants",
                )
            )
        )
        if only_pilot:
            phrases = phrases.filter(in_pilot=True)
        rows = []
        for phrase in phrases:
            if not phrase.review_variants:
                continue
            columns = [
                (label, [v for v in phrase.review_variants if v.level == level])
                for level, label in Level.choices
            ]
            rows.append((phrase, columns))
        context = {
            **self.admin_site.each_context(request),
            "title": "Verificare audio: Clear / Natural / Fast",
            "rows": rows,
            "only_pilot": only_pilot,
            "status": status,
            "voice": voice,
            "statuses": AudioVariant.QAStatus.choices,
            "voices": sorted(
                set(AudioVariant.objects.exclude(provider="mock").values_list("voice", flat=True))
            ),
            "can_change": self.has_change_permission(request),
            "opts": self.model._meta,
        }
        return TemplateResponse(request, "admin/listening/audiovariant/review.html", context)

    def review_status_view(self, request, pk: int):
        from .services.qa import set_status

        if not self.has_change_permission(request):
            raise PermissionDenied
        variant = AudioVariant.objects.filter(pk=pk).first()
        status = request.POST.get("status")
        if variant is None or status not in AudioVariant.QAStatus.values:
            messages.error(request, "Cerere invalidă.")
        else:
            _, skipped = set_status(
                [variant],
                status,
                request.user,
                notes=request.POST.get("qa_notes", variant.qa_notes),
            )
            if skipped:
                messages.warning(request, "Audio mock/placeholder nu poate fi aprobat.")
        back = request.POST.get("next") or ""
        if not back.startswith("/admin/"):
            back = reverse("admin:listening_audiovariant_review")
        return redirect(back)
