import zoneinfo

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone

from apps.listening.voices import DEFAULT_VOICE, VOICE_CHOICES

TIMEZONE_CHOICES = [
    ("Europe/London", "Regatul Unit (Londra)"),
    ("Europe/Dublin", "Irlanda (Dublin)"),
    ("Europe/Bucharest", "România (București)"),
    ("Europe/Chisinau", "Moldova (Chișinău)"),
    ("Europe/Madrid", "Spania (Madrid)"),
    ("Europe/Rome", "Italia (Roma)"),
    ("Europe/Paris", "Franța (Paris)"),
    ("Europe/Berlin", "Germania (Berlin)"),
    ("America/New_York", "SUA (New York)"),
    ("America/Toronto", "Canada (Toronto)"),
    ("Australia/Sydney", "Australia (Sydney)"),
    ("UTC", "UTC"),
]


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra):
        if not email:
            raise ValueError("Adresa de email este obligatorie.")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email: str, password: str | None = None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("email_verified", True)
        return self._create_user(email, password, **extra)


class User(AbstractUser):
    """Email-based account. `username` is removed; `first_name` doubles as display name."""

    username = None
    email = models.EmailField("email", unique=True)
    email_verified = models.BooleanField("email verificat", default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()

    class Meta:
        verbose_name = "utilizator"
        verbose_name_plural = "utilizatori"

    def __str__(self) -> str:
        return self.email

    @property
    def display_name(self) -> str:
        return self.first_name or self.email.split("@")[0]


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    timezone = models.CharField(
        "fus orar", max_length=64, choices=TIMEZONE_CHOICES, default="Europe/London"
    )
    daily_goal = models.PositiveSmallIntegerField("obiectiv zilnic", default=10)
    preferred_voice = models.CharField(
        "vocea exercițiilor",
        max_length=20,
        choices=VOICE_CHOICES,
        default=DEFAULT_VOICE,
        help_text="Alege vocea britanică pe care vrei să o auzi în exerciții.",
    )
    preferred_accent = models.ForeignKey(
        "listening.Accent",
        verbose_name="accent preferat",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "profil"
        verbose_name_plural = "profiluri"

    def __str__(self) -> str:
        return f"Profil {self.user}"

    @property
    def tzinfo(self) -> zoneinfo.ZoneInfo:
        try:
            return zoneinfo.ZoneInfo(self.timezone)
        except (zoneinfo.ZoneInfoNotFoundError, ValueError):
            return zoneinfo.ZoneInfo("Europe/London")

    def local_today(self):
        return timezone.now().astimezone(self.tzinfo).date()
