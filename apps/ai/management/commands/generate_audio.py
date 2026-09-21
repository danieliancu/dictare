"""Generate (or reuse cached) audio variants — one or more voices, optionally with auto-QA.

    python manage.py generate_audio --voices marin ballad cedar --dry-run
    python manage.py generate_audio --pilot --voices marin ballad cedar --real-api --auto-qa
    python manage.py generate_audio --voices marin ballad cedar --real-api --auto-qa --workers 4
    python manage.py generate_audio --voice marin --level natural --limit 5 --real-api

OpenAI is paid once per variant: files already generated with identical settings are reused
and cached QA results are not recomputed, so an interrupted run resumes by running the same
command again. Playback never calls OpenAI. Without --auto-qa new variants stay `pending`.
"""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.ai.services.pipeline import Report, run_groups
from apps.ai.services.tts import TTSError, cached_variant, planned_key, provider_identity
from apps.listening.models import Accent, Level, ListeningPhrase
from apps.listening.voices import VOICE_VALUES


class Command(BaseCommand):
    help = "Generate TTS audio variants for one or more voices (cached; optional auto-QA)."

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
            "--auto-qa",
            action="store_true",
            help="Run automatic QA after generation (approved / needs_review / rejected).",
        )
        parser.add_argument("--workers", type=int, default=1, help="Parallel workers (1-8).")
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
        workers = max(1, min(8, opts["workers"]))
        accent = (
            Accent.objects.filter(code=opts["accent"]).first()
            if opts["accent"]
            else Accent.default()
        )
        if accent is None:
            raise CommandError("Accent not found. Run seed_demo first.")
        if not accent.tts_supported:
            raise CommandError(
                f"{accent.code}: synthetic voices do not reproduce this accent reliably; "
                "use human recordings (provider=human) uploaded in the admin."
            )
        for voice in voices:
            if voice not in VOICE_VALUES:
                self.stdout.write(
                    self.style.WARNING(
                        f"'{voice}' is not a product voice ({', '.join(VOICE_VALUES)}); "
                        "learners cannot select it."
                    )
                )
        if opts["auto_qa"] and provider_name != "openai":
            raise CommandError("--auto-qa checks real recordings: use it with --real-api.")

        phrases = ListeningPhrase.objects.active().order_by("pk")
        if opts["pilot"]:
            phrases = phrases.filter(in_pilot=True)
        if opts["limit"]:
            phrases = phrases[: opts["limit"]]
        phrases = list(phrases)
        if not phrases:
            raise CommandError("No phrases selected (run seed_demo; --pilot needs pilot phrases).")

        plan = [(v, p, lv) for v in voices for p in phrases for lv in levels]
        cached = sum(
            1
            for v, p, lv in plan
            if cached_variant(planned_key(p, lv, accent, v, provider)) is not None
        )
        self.stdout.write(
            f"{len(phrases)} phrases\n"
            f"{len(voices)} voices ({', '.join(voices)})\n"
            f"{len(levels)} levels ({', '.join(levels)})\n"
            f"{len(plan)} possible variants\n"
            f"{cached} already cached\n"
            f"{len(plan) - cached} to generate\n"
            f"provider={provider_name} model={model} accent={accent.code} "
            f"engine=v{settings.TTS_ENGINE_VERSION}"
            + (f" auto-qa=v{settings.AUDIO_QA_VERSION}" if opts["auto_qa"] else "")
        )
        if opts["dry_run"]:
            self.stdout.write("Dry run: no API calls made.")
            return
        if provider_name == "openai" and not settings.OPENAI_API_KEY:
            raise CommandError("OPENAI_API_KEY is not set in the environment (.env).")

        report = Report()
        tasks = [(v, p) for v in voices for p in phrases]
        run_groups(
            tasks,
            levels,
            accent,
            provider,
            auto_qa=opts["auto_qa"],
            workers=workers,
            report=report,
            echo=self.stdout.write,
            fail_fast=opts["fail_fast"],
        )

        self.stdout.write(
            f"\nGenerated: {report.generated}\nCached: {report.cached}\n"
            f"Failed: {report.generation_failed}"
        )
        for text, voice, level, kind in report.failures:
            self.stderr.write(f"  - [{voice}/{level}] {kind}: {text}")
        if opts["auto_qa"]:
            self.stdout.write(
                "\n" + "\n".join(report.lines(len(phrases), len(voices), len(levels), len(plan)))
            )
        else:
            self.stdout.write("New variants are pending: listen and approve them in the admin.")
        if report.failures:
            raise CommandError(
                f"{len(report.failures)} generation(s) failed; rerun the same command to retry "
                "them (successful files are cached)."
            )
