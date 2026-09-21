"""Run automatic QA on existing recordings (cached; resumable).

    python manage.py qa_audio --dry-run
    python manage.py qa_audio                     # pending recordings (default)
    python manage.py qa_audio --needs-review      # re-check uncertain ones (after a QA upgrade)
    python manage.py qa_audio --all --voice ballad --level fast --workers 4

Only real TTS recordings are checked (never mock placeholders or human recordings), and a
decision taken by staff is never overridden.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from apps.ai.services import audio_qa
from apps.ai.services.pipeline import Report
from apps.listening.models import AudioQAResult, AudioVariant, Level
from apps.listening.voices import VOICE_VALUES

QA = AudioVariant.QAStatus


class Command(BaseCommand):
    help = "Automatic QA of generated audio: approved / needs_review / rejected."

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group()
        group.add_argument("--pending", action="store_true", help="Pending recordings (default).")
        group.add_argument("--needs-review", action="store_true", help="Needs-review recordings.")
        group.add_argument("--all", action="store_true", help="Every real TTS recording.")
        parser.add_argument("--voice", choices=VOICE_VALUES, action="append")
        parser.add_argument("--level", choices=Level.values, action="append")
        parser.add_argument("--pilot", action="store_true")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--workers", type=int, default=1)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--fail-fast", action="store_true")

    def handle(self, *args, **opts):
        if not settings.AUDIO_QA_ENABLED:
            raise CommandError("AUDIO_QA_ENABLED is False.")
        qs = (
            AudioVariant.objects.filter(provider="openai")
            .exclude(approval_source=AudioVariant.ApprovalSource.HUMAN)
            .exclude(audio_file="")
            .select_related("phrase", "accent")
            .order_by("phrase_id", "voice", "level")
        )
        if opts["needs_review"]:
            qs = qs.filter(qa_status=QA.NEEDS_REVIEW)
        elif not opts["all"]:
            qs = qs.filter(qa_status=QA.PENDING)
        if opts["voice"]:
            qs = qs.filter(voice__in=opts["voice"])
        if opts["level"]:
            qs = qs.filter(level__in=opts["level"])
        if opts["pilot"]:
            qs = qs.filter(phrase__in_pilot=True)
        variants = list(qs[: opts["limit"]] if opts["limit"] else qs)

        cached = sum(
            1
            for v in variants
            if v.audio_sha256
            and AudioQAResult.objects.filter(
                cache_key=audio_qa.cache_key(
                    v.audio_sha256,
                    settings.AUDIO_QA_TRANSCRIBE_MODEL,
                    settings.AUDIO_QA_EVALUATOR_MODEL,
                    v.pk,
                )
            ).exists()
        )
        self.stdout.write(
            f"{len(variants)} recordings selected\n{cached} with cached QA (reused, no API)\n"
            f"{len(variants) - cached} to check (QA v{settings.AUDIO_QA_VERSION}, "
            f"{settings.AUDIO_QA_TRANSCRIBE_MODEL} + {settings.AUDIO_QA_EVALUATOR_MODEL})"
        )
        if opts["dry_run"] or not variants:
            self.stdout.write(
                "Dry run: no API calls made." if opts["dry_run"] else "Nothing to do."
            )
            return
        if len(variants) > cached and not settings.OPENAI_API_KEY:
            raise CommandError("OPENAI_API_KEY is not set in the environment (.env).")

        report = Report()
        transcriber, evaluator = audio_qa.get_transcriber(), audio_qa.get_evaluator()
        lock = threading.Lock()

        def check(variant):
            try:
                outcome = audio_qa.run_qa(variant, transcriber, evaluator)
                report.record_qa(variant.voice, outcome)
                r = outcome.result
                with lock:
                    self.stdout.write(
                        f"  [{variant.voice}/{variant.level}] {r.decision}"
                        f" ({'reused' if outcome.reused else f'score {r.overall_score}'})"
                        f" {variant.phrase.text}"
                    )
                return r.decision
            finally:
                if threading.current_thread() is not threading.main_thread():
                    connection.close()

        workers = max(1, min(8, opts["workers"]))
        if workers == 1:
            for variant in variants:
                if check(variant) == AudioQAResult.Decision.ERROR and opts["fail_fast"]:
                    break
        else:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                list(pool.map(check, variants))

        d = report.decisions
        self.stdout.write(
            f"\nQA reused: {report.qa_reused}\nQA performed now: {report.qa_performed}\n"
            f"Auto-approved: {d['approved']}\nNeeds review: {d['needs_review']}\n"
            f"Rejected: {d['rejected']}\nQA failed: {d['error']}"
        )
        if d["error"]:
            raise CommandError(f"{d['error']} QA run(s) failed; rerun to retry them.")
