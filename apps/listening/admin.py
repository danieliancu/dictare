from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Prefetch
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from django.views.decorators.http import require_POST

from apps.ai.services.tts import TTSError, generate_variant

from .models import (
    Accent,
    AudioQAResult,
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
        "source",
        "confidence",
        "verified_by",
        "verified_at",
    ]
    readonly_fields = ["source", "confidence", "verified_by", "verified_at"]
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


@admin.display(description="Fișier")
def file_status(obj):
    from .services.audio import file_exists

    return "✓" if file_exists(obj) else "lipsă"


@admin.display(description="Neverificate")
def unverified_count(obj):
    from .services.qa import unreviewed_patterns

    count = len(unreviewed_patterns(obj))
    return count or "—"


def _latest_qa(obj):
    results = getattr(obj, "_qa_cache", None)
    if results is None:
        results = list(obj.qa_results.all())
        obj._qa_cache = results
    return results[0] if results else None


def _yes_no(value):
    return "—" if value is None else ("✓" if value else "✗")


@admin.display(description="Auto-QA")
def qa_decision(obj):
    r = _latest_qa(obj)
    return (
        f"{r.get_decision_display()} · {r.overall_score}"
        if r and r.overall_score is not None
        else (r.get_decision_display() if r else "—")
    )


@admin.display(description="Transcriere")
def qa_transcript(obj):
    r = _latest_qa(obj)
    if not r or r.transcript_similarity is None:
        return "—"
    conf = f" · {r.confidence_label}" if r.confidence_label else ""
    return f"{r.transcript_similarity:.0f}%{conf}"


@admin.display(description="Accent / livrare / fonetic")
def qa_flags(obj):
    r = _latest_qa(obj)
    if not r:
        return "—"
    return f"{_yes_no(r.accent_pass)} / {_yes_no(r.delivery_pass)} / {_yes_no(r.phonetic_pass)}"


class AudioQAResultInline(admin.TabularInline):
    model = AudioQAResult
    extra = 0
    can_delete = False
    fields = [
        "created_at",
        "qa_version",
        "decision",
        "overall_score",
        "transcript_text",
        "transcript_similarity",
        "confidence_label",
        "duration_pass",
        "accent_label",
        "delivery_pass",
        "phonetic_pass",
        "reasons",
    ]
    readonly_fields = fields
    verbose_name_plural = "Auto-QA (cel mai recent primul)"

    def has_add_permission(self, request, obj=None):
        return False


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
        "approval_source",
        qa_decision,
        qa_transcript,
        qa_flags,
        unverified_count,
        file_status,
        audio_preview,
    ]
    list_filter = [
        "qa_status",
        "approval_source",
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
        "pattern_review",
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
        "approval_source",
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
        (
            "QA",
            {
                "fields": [
                    "qa_status",
                    "approval_source",
                    "pattern_review",
                    "qa_notes",
                    "reviewed_by",
                    "reviewed_at",
                ]
            },
        ),
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
    inlines = [AudioVariantPatternInline, AudioQAResultInline]
    actions = ["approve_selected", "reject_selected"]
    date_hierarchy = "generated_at"
    change_list_template = "admin/listening/audiovariant/change_list.html"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .prefetch_related("pattern_checks", "phrase__phrase_patterns", "qa_results")
        )

    @admin.display(description="Verificare fenomene")
    def pattern_review(self, obj):
        from .services.qa import pattern_summary, unverified_label

        if obj is None or obj.pk is None:
            return "—"
        summary = pattern_summary(obj)
        if summary["unverified"]:
            return unverified_label(summary["unverified"]) + " (necesare pentru aprobare)"
        return "Toate fenomenele așteptate sunt verificate."

    def save_model(self, request, obj, form, change):
        """Approval is applied in save_related, after the pattern verifications are saved."""
        self._requested_status = None
        if "qa_status" in form.changed_data:
            self._requested_status = obj.qa_status
            obj.qa_status = form.initial.get("qa_status", AudioVariant.QAStatus.PENDING)
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        from .services.qa import approval_problems, set_status

        super().save_related(request, form, formsets, change)
        status = getattr(self, "_requested_status", None)
        if not status:
            return
        variant = AudioVariant.objects.get(pk=form.instance.pk)
        problems = approval_problems(variant) if status == AudioVariant.QAStatus.APPROVED else []
        if problems:
            messages.error(request, "Nu poate fi aprobată: " + "; ".join(problems) + ".")
            return
        set_status([variant], status, request.user)

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
        from .services.qa import describe_result, set_status

        changed, skipped = set_status(queryset, AudioVariant.QAStatus.APPROVED, request.user)
        level = messages.WARNING if skipped else messages.SUCCESS
        self.message_user(request, describe_result(changed, skipped), level)

    @admin.action(description="Respinge variantele selectate", permissions=["change"])
    def reject_selected(self, request, queryset):
        from .services.qa import describe_result, set_status

        changed, skipped = set_status(queryset, AudioVariant.QAStatus.REJECTED, request.user)
        self.message_user(request, describe_result(changed, skipped, "respinse"))

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
        from .services.qa import approval_problems, pattern_summary

        if not self.has_view_permission(request):
            raise PermissionDenied
        only_pilot = request.GET.get("pilot", "1") == "1"
        status = request.GET.get("status", "")
        voice = request.GET.get("voice", "")
        variants = (
            AudioVariant.objects.exclude(provider="mock")
            .select_related("accent", "phrase")
            .prefetch_related("pattern_checks", "phrase__phrase_patterns")
        )
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
                (
                    label,
                    [
                        (v, pattern_summary(v), approval_problems(v))
                        for v in phrase.review_variants
                        if v.level == level
                    ],
                )
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
        from .services.qa import approval_problems, set_status

        if not self.has_change_permission(request):
            raise PermissionDenied
        variant = AudioVariant.objects.filter(pk=pk).first()
        status = request.POST.get("status")
        if variant is None or status not in AudioVariant.QAStatus.values:
            messages.error(request, "Cerere invalidă.")
        else:
            problems = (
                approval_problems(variant) if status == AudioVariant.QAStatus.APPROVED else []
            )
            if problems:
                messages.error(request, "Nu poate fi aprobată: " + "; ".join(problems) + ".")
            else:
                set_status(
                    [variant],
                    status,
                    request.user,
                    notes=request.POST.get("qa_notes", variant.qa_notes),
                )
        back = request.POST.get("next") or ""
        if not back.startswith("/admin/"):
            back = reverse("admin:listening_audiovariant_review")
        return redirect(back)
