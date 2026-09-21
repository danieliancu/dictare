"""Generate (or reuse cached) audio variants for learners.

    python manage.py generate_audio --pilot --voice marin --dry-run
    python manage.py generate_audio --pilot --voice marin --real-api
    python manage.py generate_audio --pilot --level natural --limit 5 --real-api
    python manage.py generate_audio                      # all phrases, TTS_PROVIDER

Files already generated with identical settings are reused, so an interrupted run can be
resumed. New variants are `pending` until approved in the admin.
"""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.ai.services.tts import (
    TTSError,
    cached_variant,
    generate_variant,
    planned_key,
    provider_identity,
)
from apps.listening.models import Accent, Level, ListeningPhrase


class Command(BaseCommand):
    help = "Generate TTS audio variants (cached; new variants need QA approval)."

    def add_arguments(self, parser):
        parser.add_argument("--pilot", action="store_true", help="Only the pilot corpus.")
        parser.add_argument("--voice", help="Voice (default: TTS_VOICE).")
        parser.add_argument(
            "--level",
            choices=Level.values,
            action="append",
            help="Repeatable. Default: all three levels.",
        )
        parser.add_argument("--accent", help="Accent code (default: the default accent).")
        parser.add_argument("--limit", type=int, default=0, help="Max number of phrases.")
        parser.add_argument("--provider", help="Override TTS_PROVIDER (mock, openai).")
        parser.add_argument(
            "--real-api",
            action="store_true",
            help="Use the OpenAI Speech API (same as --provider openai).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be generated, without any API call.",
        )
        parser.add_argument("--fail-fast", action="store_true", help="Stop at the first error.")

    def handle(self, *args, **opts):
        provider = "openai" if opts["real_api"] else (opts["provider"] or settings.TTS_PROVIDER)
        try:
            provider_name, model = provider_identity(provider)
        except TTSError as exc:
            raise CommandError(str(exc)) from exc
        voice = opts["voice"] or settings.TTS_VOICE
        levels = opts["level"] or list(Level.values)
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
                    f"{accent.code}: synthetic voices do not reproduce this accent reliably; "
                    "prefer human recordings (provider=human) uploaded in the admin."
                )
            )

        phrases = ListeningPhrase.objects.active().order_by("pk")
        if opts["pilot"]:
            phrases = phrases.filter(in_pilot=True)
        if opts["limit"]:
            phrases = phrases[: opts["limit"]]
        phrases = list(phrases)
        if not phrases:
            raise CommandError("No phrases selected (run seed_demo; --pilot needs pilot phrases).")

        plan = [(phrase, level) for phrase in phrases for level in levels]
        cached = {
            (phrase.pk, level)
            for phrase, level in plan
            if cached_variant(planned_key(phrase, level, accent, voice, provider)) is not None
        }
        todo = [(p, lv) for p, lv in plan if (p.pk, lv) not in cached]
        self.stdout.write(
            f"{len(phrases)} phrases x {len(levels)} levels x 1 voice = {len(plan)} audio "
            f"generations ({provider_name}/{model}, voice={voice}, accent={accent.code}, "
            f"engine v{settings.TTS_ENGINE_VERSION}): {len(cached)} cached, "
            f"{len(todo)} to generate."
        )
        if opts["dry_run"]:
            self.stdout.write("Dry run: no API calls made.")
            return
        if provider_name == "openai" and not settings.OPENAI_API_KEY:
            raise CommandError("OPENAI_API_KEY is not set in the environment (.env).")

        done, failures = 0, []
        for phrase, level in todo:
            try:
                generate_variant(phrase, level, accent, voice=voice, provider=provider)
                done += 1
                self.stdout.write(f"  ok   [{level:7}] {phrase.text}")
            except TTSError as exc:
                failures.append((phrase, level, exc))
                self.stderr.write(
                    f"  FAIL [{level:7}] voice={voice} {exc.kind}: {exc} | {phrase.text}"
                )
                if opts["fail_fast"]:
                    break

        self.stdout.write(
            f"Generated {done}, reused {len(cached)}, failed {len(failures)}. "
            "New variants are pending: review them in the admin before learners hear them."
        )
        if failures:
            raise CommandError(
                f"{len(failures)} generation(s) failed; rerun the same command to retry them "
                "(successful files are cached)."
            )
