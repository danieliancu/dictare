from django.db import models


class Testimonial(models.Model):
    quote = models.TextField("citat")
    author_name = models.CharField("nume", max_length=80)
    location = models.CharField("locație", max_length=80, blank=True)
    country_code = models.CharField(
        "cod țară", max_length=2, blank=True, help_text="ISO 3166, ex. RO, FR, GB."
    )
    avatar = models.ImageField("avatar", upload_to="testimonials/", blank=True)
    active = models.BooleanField("activ", default=True)
    order = models.PositiveSmallIntegerField("ordine", default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "-created_at"]
        verbose_name = "testimonial"
        verbose_name_plural = "testimoniale"

    def __str__(self) -> str:
        return f"{self.author_name}: {self.quote[:40]}"

    @property
    def initials(self) -> str:
        parts = self.author_name.replace(".", " ").split()
        return "".join(p[0] for p in parts[:2]).upper()
