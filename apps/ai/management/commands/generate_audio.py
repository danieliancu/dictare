"""Generate (or reuse cached) audio variants for learners — one or more voices at once.

    python manage.py generate_audio --pilot --voices marin ballad cedar --dry-run
    python manage.py generate_audio --pilot --voices marin ballad cedar --real-api
    python manage.py generate_audio --voices marin ballad cedar --real-api   # full corpus
    python manage.py generate_audio --voice marin --level natural --limit 5 --real-api

OpenAI is paid once per variant: files already generated with identical settings are
reused, so an interrupted run is resumed by running the same command again. Playback
never calls OpenAI. New variants stay `pending` until approved in the admin.
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
from apps.listening.voices import VOICE_VALUES


class Command(BaseCommand):
    help = "Generate TTS audio variants for one or more voices (cached; QA approval needed)."

    def add_arguments(self, parser):
        parser.add_argument("--pilot", action="store_true", help="Only the pilot corpus.")
        parser.add_argument(
            "--voices", nargs="+", help="Voices to generate, e.g. --voices marin ballad cedar."
        )
        parser.add_argument(
            "--voice", action="append", help="Single voice (repeatable; same as --voices)."
        )
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
        voices = list(dict.fromkeys((opts["voices"] or []) + (opts["voice"] or [])))
        voices = voices or [settings.TTS_VOICE]
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
        for voice in voices:
            if voice not in VOICE_VALUES:
                self.stdout.write(
                    self.style.WARNING(
                        f"'{voice}' is not a product voice ({', '.join(VOICE_VALUES)}); "
                        "learners cannot select it."
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

        plan = [(v, p, lv) for v in voices for p in phrases for lv in levels]
        cached = {
            (v, p.pk, lv)
            for v, p, lv in plan
            if cached_variant(planned_key(p, lv, accent, v, provider)) is not None
        }
        self.stdout.write(
            f"{len(phrases)} phrases\n"
            f"{len(voices)} voices ({', '.join(voices)})\n"
            f"{len(levels)} levels ({', '.join(levels)})\n"
            f"{len(plan)} possible variants\n"
            f"{len(cached)} already cached\n"
            f"{len(plan) - len(cached)} to generate\n"
            f"provider={provider_name} model={model} accent={accent.code} "
            f"engine=v{settings.TTS_ENGINE_VERSION}"
        )
        if opts["dry_run"]:
            self.stdout.write("Dry run: no API calls made.")
            return
        if provider_name == "openai" and not settings.OPENAI_API_KEY:
            raise CommandError("OPENAI_API_KEY is not set in the environment (.env).")

        generated, reused, failures = 0, 0, []
        stop = False
        for voice in voices:
            self.stdout.write(self.style.MIGRATE_HEADING(f"Voice: {voice.capitalize()}"))
            for n, phrase in enumerate(phrases, start=1):
                self.stdout.write(f"Phrase {n}/{len(phrases)}: {phrase.text}")
                for level in levels:
                    if (voice, phrase.pk, level) in cached:
                        reused += 1
                        self.stdout.write(f"  {level:8} cached")
                        continue
                    try:
                        generate_variant(phrase, level, accent, voice=voice, provider=provider)
                    except TTSError as exc:
                        failures.append((phrase, voice, level, exc))
                        self.stderr.write(f"  {level:8} FAILED ({exc.kind}): {exc}")
                        if opts["fail_fast"]:
                            stop = True
                            break
                        continue
                    generated += 1
                    self.stdout.write(f"  {level:8} generated")
                if stop:
                    break
            if stop:
                break

        self.stdout.write(f"\nGenerated: {generated}\nCached: {reused}\nFailed: {len(failures)}")
        for phrase, voice, level, exc in failures:
            self.stderr.write(f"  - [{voice}/{level}] {exc.kind}: {phrase.text}")
        self.stdout.write("New variants are pending: listen and approve them in the admin.")
        if failures:
            raise CommandError(
                f"{len(failures)} generation(s) failed; rerun the same command to retry them "
                "(successful files are cached)."
            )
