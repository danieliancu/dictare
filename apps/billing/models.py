from django.conf import settings
from django.db import models


class Plan(models.Model):
    class Code(models.TextChoices):
        FREE = "free", "Gratuit"
        PRO = "pro", "Pro"

    code = models.CharField(max_length=10, choices=Code.choices, unique=True)
    name = models.CharField("nume", max_length=40)
    tagline = models.CharField("descriere scurtă", max_length=140, blank=True)
    price_monthly = models.DecimalField("preț lunar (GBP)", max_digits=6, decimal_places=2)
    stripe_price_id = models.CharField(max_length=100, blank=True)
    daily_exercise_limit = models.PositiveSmallIntegerField(
        "limită exerciții/zi", null=True, blank=True, help_text="Gol = nelimitat."
    )
    natural_level = models.BooleanField("Engleză naturală", default=False)
    fast_level = models.BooleanField("Engleză rapidă", default=False)
    full_mistake_history = models.BooleanField("istoric complet greșeli", default=False)
    personalized_training = models.BooleanField("antrenament personalizat", default=False)
    advanced_progress = models.BooleanField("progres avansat", default=False)
    features_ro = models.TextField("beneficii (câte unul pe rând)", blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order"]
        verbose_name = "plan"
        verbose_name_plural = "planuri"

    def __str__(self) -> str:
        return self.name

    @property
    def feature_list(self) -> list[str]:
        return [line.strip() for line in self.features_ro.splitlines() if line.strip()]


class Subscription(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Activ"
        TRIALING = "trialing", "Perioadă de probă"
        PAST_DUE = "past_due", "Plată restantă"
        CANCELED = "canceled", "Anulat"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscription"
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    provider = models.CharField(max_length=20, default="manual")
    provider_customer_id = models.CharField(max_length=100, blank=True)
    provider_subscription_id = models.CharField(max_length=100, blank=True, db_index=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "abonament"
        verbose_name_plural = "abonamente"

    def __str__(self) -> str:
        return f"{self.user} · {self.plan} ({self.get_status_display()})"

    @property
    def is_active(self) -> bool:
        from django.utils import timezone

        if self.status not in {self.Status.ACTIVE, self.Status.TRIALING}:
            return False
        return self.current_period_end is None or self.current_period_end > timezone.now()
