from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile, User


@receiver(post_save, sender=User)
def ensure_profile(sender, instance: User, created: bool, **kwargs) -> None:
    if created:
        Profile.objects.get_or_create(user=instance)


@receiver(user_logged_in)
def claim_trial_attempts(sender, request, user, **kwargs) -> None:
    """Keep the exercises a visitor did before creating an account or logging in."""
    if request is None or not hasattr(request, "session"):
        return
    from apps.practice.services.sessions import ANON_SESSION_KEY, claim_anonymous_work

    anon_key = request.session.pop(ANON_SESSION_KEY, "")
    if anon_key:
        claim_anonymous_work(user, anon_key)
