"""Generate (or reuse cached) audio for every active phrase.

python manage.py generate_audio                      # all levels, default accent
python manage.py generate_audio --level natural --provider openai
python manage.py generate_audio --accent modern-rp --limit 10
"""

from django.core.management.base import BaseCommand, CommandError

from apps.ai.services.tts import TTSUnavailable, get_or_create_variant
from apps.listening.models import Accent, Level, ListeningPhrase


class Command(BaseCommand):
    help = "Generate cached TTS audio for active phrases (existing files are reused)."

    def add_arguments(self, parser):
        parser.add_argument("--level", choices=Level.values, action="append")
        parser.add_argument("--accent", help="Accent code (default: the default accent).")
        parser.add_argument("--provider", help="Override TTS_PROVIDER (mock, openai).")
        parser.add_argument("--limit", type=int, default=0)

    def handle(self, *args, **opts):
        accent = (
            Accent.objects.filter(code=opts["accent"]).first()
            if opts["accent"]
            else Accent.default()
        )
        if accent is None:
            raise CommandError("Accent not found. Run seed_demo first.")
        if not accent.tts_supported:
            self.stdout.write(
                self.style.WARNING(
                    f"{accent.name_ro}: synthetic voices do not reproduce this accent reliably. "
                    "Prefer human recordings uploaded in the admin."
                )
            )
        levels = opts["level"] or Level.values
        phrases = ListeningPhrase.objects.active().order_by("pk")
        if opts["limit"]:
            phrases = phrases[: opts["limit"]]

        done = 0
        for phrase in phrases:
            for level in levels:
                try:
                    get_or_create_variant(phrase, level, accent, provider=opts["provider"])
                except TTSUnavailable as exc:
                    raise CommandError(f"Audio unavailable: {exc}") from exc
                done += 1
        self.stdout.write(self.style.SUCCESS(f"{done} audio variants ready ({accent.code})."))
