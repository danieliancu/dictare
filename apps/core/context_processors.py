from django.conf import settings


def site(request):
    user = getattr(request, "user", None)
    streak = None
    if user is not None and user.is_authenticated:
        from apps.progress.services.streak import user_streak

        streak = getattr(request, "_streak", None)
        if streak is None:
            streak = request._streak = user_streak(user)
    return {
        "SITE_NAME": "dictare.ro",
        "SITE_URL": settings.SITE_URL,
        "user_streak": streak,
        "SOCIAL_LINKS": [
            ("YouTube", "youtube", settings.SOCIAL_YOUTUBE_URL),
            ("Instagram", "instagram", settings.SOCIAL_INSTAGRAM_URL),
            ("X", "x-social", settings.SOCIAL_X_URL),
        ],
    }
