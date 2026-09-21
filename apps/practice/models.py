import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.listening.models import AudioVariant, Level, ListeningPhrase


class SessionKind(models.TextChoices):
    DAILY = "daily", "Ascultare zilnică"
    TOPIC = "topic", "Temă"
    PATTERN = "pattern", "Tipar"
    PERSONALIZED = "personalized", "Personalizat"
    TRIAL = "trial", "Încercare gratuită"


class OwnedQuerySet(models.QuerySet):
    def owned_by(self, user, anon_key: str | None):
        """Rows belonging to the logged-in user, or to the anonymous browser session."""
        if user is not None and user.is_authenticated:
            return self.filter(user=user)
        if anon_key:
            return self.filter(user__isnull=True, anon_key=anon_key)
        return self.none()


class PracticeSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="practice_sessions",
    )
    anon_key = models.CharField(max_length=64, blank=True, db_index=True)
    kind = models.CharField(max_length=20, choices=SessionKind.choices)
    level = models.CharField(max_length=10, choices=Level.choices, default=Level.CLEAR)
    accent = models.ForeignKey("listening.Accent", on_delete=models.PROTECT, related_name="+")
    topic = models.ForeignKey(
        "listening.Topic", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    pattern = models.ForeignKey(
        "listening.SpeechPattern",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    local_date = models.DateField(help_text="Data locală a utilizatorului la creare.")
    target_count = models.PositiveSmallIntegerField(default=10)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    objects = OwnedQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "sesiune de exerciții"
        verbose_name_plural = "sesiuni de exerciții"
        indexes = [models.Index(fields=["user", "kind", "local_date"])]
        constraints = [
            models.CheckConstraint(
                condition=Q(user__isnull=False) | ~Q(anon_key=""), name="session_has_owner"
            )
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} · {self.local_date}"

    @property
    def is_complete(self) -> bool:
        return self.completed_at is not None


class SessionItem(models.Model):
    session = models.ForeignKey(PracticeSession, on_delete=models.CASCADE, related_name="items")
    phrase = models.ForeignKey(ListeningPhrase, on_delete=models.CASCADE, related_name="+")
    position = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["session", "position"]
        constraints = [
            models.UniqueConstraint(fields=["session", "position"], name="unique_session_position"),
            models.UniqueConstraint(fields=["session", "phrase"], name="unique_session_phrase"),
        ]

    def __str__(self) -> str:
        return f"#{self.position + 1} {self.phrase}"


class ListeningAttempt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="attempts",
    )
    anon_key = models.CharField(max_length=64, blank=True)
    session_item = models.ForeignKey(
        SessionItem, on_delete=models.CASCADE, related_name="attempts", null=True, blank=True
    )
    phrase = models.ForeignKey(ListeningPhrase, on_delete=models.CASCADE, related_name="attempts")
    audio_variant = models.ForeignKey(
        AudioVariant, on_delete=models.SET_NULL, null=True, blank=True, related_name="attempts"
    )
    level = models.CharField(max_length=10, choices=Level.choices, default=Level.CLEAR)
    typed_answer = models.TextField("răspuns", blank=True)
    score = models.PositiveSmallIntegerField(null=True, blank=True)
    word_accuracy = models.PositiveSmallIntegerField(null=True, blank=True)
    listened_count = models.PositiveSmallIntegerField("ascultări", default=0)
    replay_count = models.PositiveSmallIntegerField("reluări", default=0)
    time_spent_ms = models.PositiveIntegerField("timp petrecut (ms)", default=0)
    slowed_down = models.BooleanField("a redus viteza", default=False)
    transcript_revealed = models.BooleanField("transcriere afișată", default=False)
    revealed_before_check = models.BooleanField("transcriere înainte de verificare", default=False)
    completed = models.BooleanField(default=False)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    objects = OwnedQuerySet.as_manager()

    class Meta:
        ordering = ["-started_at"]
        verbose_name = "încercare"
        verbose_name_plural = "încercări"
        indexes = [
            models.Index(fields=["user", "completed", "completed_at"]),
            models.Index(fields=["anon_key", "completed"]),
            models.Index(fields=["user", "phrase"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(score__isnull=True) | Q(score__lte=100), name="attempt_score_range"
            ),
            models.CheckConstraint(
                condition=Q(word_accuracy__isnull=True) | Q(word_accuracy__lte=100),
                name="attempt_accuracy_range",
            ),
            models.UniqueConstraint(
                fields=["session_item"],
                condition=Q(session_item__isnull=False),
                name="one_attempt_per_session_item",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user or 'anonim'} · {self.phrase} · {self.score}"


class MistakeType(models.TextChoices):
    MISSING = "missing", "Cuvânt lipsă"
    INCORRECT = "incorrect", "Cuvânt greșit"
    EXTRA = "extra", "Cuvânt în plus"
    ORDER = "order", "Ordine greșită"
    CONTRACTION = "contraction", "Formă contrasă"
    SPELLING = "spelling", "Ortografie UK/US"


class AttemptMistake(models.Model):
    attempt = models.ForeignKey(ListeningAttempt, on_delete=models.CASCADE, related_name="mistakes")
    position = models.PositiveSmallIntegerField(null=True, blank=True)
    expected_word = models.CharField(max_length=80, blank=True)
    typed_word = models.CharField(max_length=80, blank=True)
    mistake_type = models.CharField(max_length=20, choices=MistakeType.choices)
    speech_pattern = models.ForeignKey(
        "listening.SpeechPattern",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mistakes",
    )
    severity = models.FloatField(default=1.0)

    class Meta:
        ordering = ["attempt", "position"]
        verbose_name = "greșeală"
        verbose_name_plural = "greșeli"
        indexes = [models.Index(fields=["speech_pattern", "mistake_type"])]

    def __str__(self) -> str:
        return f"{self.get_mistake_type_display()}: {self.expected_word} → {self.typed_word}"
