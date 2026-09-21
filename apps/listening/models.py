import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify

from apps.scoring.normalize import tokenize

from .validators import validate_audio_file


class Level(models.TextChoices):
    """Listening level. Each level has its own recording, not just a playback-rate change."""

    CLEAR = "clear", "Engleză britanică"
    NATURAL = "natural", "Engleză naturală"
    FAST = "fast", "Engleză rapidă"


LEVEL_DESCRIPTIONS = {
    Level.CLEAR: "Articulare clară, ritm puțin mai lent. Ideal pentru început.",
    Level.NATURAL: "Ritm normal, cuvinte legate și forme slabe, ca în viața reală.",
    Level.FAST: "Ritm nativ rapid, reduceri naturale. Pentru urechi antrenate.",
}


class Difficulty(models.IntegerChoices):
    BEGINNER = 1, "1 · Ușor"
    ELEMENTARY = 2, "2 · Accesibil"
    INTERMEDIATE = 3, "3 · Mediu"
    ADVANCED = 4, "4 · Dificil"
    EXPERT = 5, "5 · Foarte dificil"


class TimeStamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Topic(TimeStamped):
    slug = models.SlugField(unique=True)
    name_ro = models.CharField("nume (RO)", max_length=80)
    name_en = models.CharField("nume (EN)", max_length=80)
    description_ro = models.CharField("descriere", max_length=200, blank=True)
    icon = models.CharField("iconiță", max_length=40, default="chat")
    order = models.PositiveSmallIntegerField("ordine", default=0)
    active = models.BooleanField("activ", default=True)

    class Meta:
        ordering = ["order", "name_ro"]
        verbose_name = "temă"
        verbose_name_plural = "teme"

    def __str__(self) -> str:
        return self.name_ro


class Accent(TimeStamped):
    """A British accent. Separate from difficulty: any level can exist in any accent."""

    code = models.SlugField(unique=True)
    name_ro = models.CharField("nume (RO)", max_length=80)
    name_en = models.CharField("nume (EN)", max_length=80)
    description_ro = models.TextField("descriere", blank=True)
    tts_supported = models.BooleanField(
        "suportat de sinteza vocală",
        default=False,
        help_text="Bifează doar dacă vocea sintetizată redă accentul fiabil. "
        "Altfel, folosește înregistrări umane încărcate manual.",
    )
    tts_instructions = models.CharField(
        "instrucțiuni TTS",
        max_length=300,
        blank=True,
        help_text="Descrierea accentului trimisă providerului TTS.",
    )
    is_default = models.BooleanField("implicit", default=False)
    order = models.PositiveSmallIntegerField("ordine", default=0)
    active = models.BooleanField("activ", default=True)

    class Meta:
        ordering = ["order", "name_ro"]
        verbose_name = "accent"
        verbose_name_plural = "accente"
        constraints = [
            models.UniqueConstraint(
                fields=["is_default"],
                condition=models.Q(is_default=True),
                name="single_default_accent",
            )
        ]

    def __str__(self) -> str:
        return self.name_ro

    @classmethod
    def default(cls) -> "Accent | None":
        return (
            cls.objects.filter(is_default=True).first() or cls.objects.filter(active=True).first()
        )


class PatternGroup(models.TextChoices):
    WEAK_FORMS = "weak_forms", "Forme slabe"
    LINKING = "linking", "Sunete legate între cuvinte"
    FREQUENT = "frequent_phrases", "Expresii folosite frecvent"
    ACCENTS = "accents", "Accente britanice"


class SpeechPattern(TimeStamped):
    slug = models.SlugField(unique=True)
    name_ro = models.CharField("nume (RO)", max_length=80)
    name_en = models.CharField("nume (EN)", max_length=80)
    description_ro = models.TextField("descriere")
    group = models.CharField("grup", max_length=20, choices=PatternGroup.choices)
    order = models.PositiveSmallIntegerField("ordine", default=0)

    class Meta:
        ordering = ["order", "name_ro"]
        verbose_name = "tipar de vorbire"
        verbose_name_plural = "tipare de vorbire"

    def __str__(self) -> str:
        return self.name_ro


class PhraseQuerySet(models.QuerySet):
    def active(self):
        return self.filter(active=True)


class ListeningPhrase(TimeStamped):
    text = models.CharField("text (EN)", max_length=300, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    translation_ro = models.CharField("traducere (RO)", max_length=300, blank=True)
    difficulty = models.PositiveSmallIntegerField(
        "dificultate", choices=Difficulty.choices, default=Difficulty.ELEMENTARY
    )
    topic = models.ForeignKey(
        Topic, verbose_name="temă", on_delete=models.PROTECT, related_name="phrases"
    )
    active = models.BooleanField("activ", default=True)
    patterns = models.ManyToManyField(
        SpeechPattern, through="PhrasePattern", related_name="phrases", blank=True
    )

    objects = PhraseQuerySet.as_manager()

    class Meta:
        ordering = ["topic__order", "difficulty", "text"]
        verbose_name = "frază"
        verbose_name_plural = "fraze"
        indexes = [
            models.Index(fields=["active", "difficulty"]),
            models.Index(fields=["topic", "active"]),
        ]

    def __str__(self) -> str:
        return self.text

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.text)[:100] or "fraza"
            slug, n = base, 2
            while ListeningPhrase.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, n = f"{base}-{n}", n + 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def word_count(self) -> int:
        return len(tokenize(self.text))


class PhrasePattern(models.Model):
    """A speech pattern occurring in a phrase, located by token span."""

    phrase = models.ForeignKey(
        ListeningPhrase, on_delete=models.CASCADE, related_name="phrase_patterns"
    )
    pattern = models.ForeignKey(
        SpeechPattern, on_delete=models.PROTECT, related_name="phrase_patterns"
    )
    fragment = models.CharField(
        "fragment", max_length=120, help_text="Cuvintele exacte din frază (ex. „would you”)."
    )
    start_token = models.PositiveSmallIntegerField(editable=False, default=0)
    end_token = models.PositiveSmallIntegerField(editable=False, default=0)
    sounds_like = models.CharField(
        "sună ca", max_length=80, blank=True, help_text="Opțional: IPA sau formă uzuală (ex. /tə/)."
    )
    explanation_ro = models.CharField("explicație (RO)", max_length=300)

    class Meta:
        ordering = ["phrase", "start_token"]
        verbose_name = "tipar în frază"
        verbose_name_plural = "tipare în fraze"
        constraints = [
            models.UniqueConstraint(
                fields=["phrase", "pattern", "start_token"], name="unique_pattern_span"
            ),
            models.CheckConstraint(
                condition=models.Q(end_token__gte=models.F("start_token")),
                name="pattern_span_ordered",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.pattern} · „{self.fragment}”"

    def save(self, *args, **kwargs):
        span = self.locate()
        if span is None:
            raise ValidationError(f"Fragment „{self.fragment}” not found in „{self.phrase.text}”.")
        self.start_token, self.end_token = span
        super().save(*args, **kwargs)

    def clean(self) -> None:
        if self.phrase_id and self.fragment:
            span = self.locate()
            if span is None:
                raise ValidationError({"fragment": "Fragmentul nu apare în textul frazei."})

    def locate(self) -> tuple[int, int] | None:
        """Return the (start, end) token span of the fragment inside the phrase, inclusive."""
        words = tokenize(self.phrase.text)
        frag = tokenize(self.fragment)
        if not frag:
            return None
        for i in range(len(words) - len(frag) + 1):
            if words[i : i + len(frag)] == frag:
                return i, i + len(frag) - 1
        return None

    def covers(self, position: int) -> bool:
        return self.start_token <= position <= self.end_token


def audio_upload_path(instance: "AudioVariant", filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower()
    key = instance.cache_key or "manual"
    return f"audio/{key[:2]}/{key}.{ext}"


class AudioVariant(models.Model):
    phrase = models.ForeignKey(
        ListeningPhrase, on_delete=models.CASCADE, related_name="audio_variants"
    )
    level = models.CharField("nivel", max_length=10, choices=Level.choices)
    accent = models.ForeignKey(Accent, on_delete=models.PROTECT, related_name="audio_variants")
    voice = models.CharField("voce", max_length=60)
    audio_file = models.FileField(
        "fișier audio", upload_to=audio_upload_path, validators=[validate_audio_file], blank=True
    )
    duration_ms = models.PositiveIntegerField("durată (ms)", default=0)
    provider = models.CharField(
        "sursă", max_length=30, help_text="ex. openai, mock, human (înregistrare umană)"
    )
    cache_key = models.CharField(max_length=64, unique=True, blank=True, editable=False)
    generation_settings = models.JSONField(
        "setări generare",
        default=dict,
        blank=True,
        help_text="Metadate specifice providerului (model, instrucțiuni, viteză).",
    )
    generated_at = models.DateTimeField("generat la", auto_now_add=True)

    class Meta:
        ordering = ["phrase", "level"]
        verbose_name = "variantă audio"
        verbose_name_plural = "variante audio"
        constraints = [
            models.UniqueConstraint(
                fields=["phrase", "level", "accent", "voice"], name="unique_audio_variant"
            )
        ]
        indexes = [models.Index(fields=["phrase", "level", "accent"])]

    def __str__(self) -> str:
        return f"{self.phrase} [{self.get_level_display()}, {self.accent.code}]"

    def save(self, *args, **kwargs):
        if not self.cache_key:  # manual upload (e.g. human recording) from the admin
            self.cache_key = uuid.uuid4().hex + uuid.uuid4().hex
        super().save(*args, **kwargs)

    @property
    def is_placeholder(self) -> bool:
        """Mock audio is a timing placeholder, not real speech."""
        return self.provider == "mock"

    @property
    def duration_seconds(self) -> float:
        return round(self.duration_ms / 1000, 1)
