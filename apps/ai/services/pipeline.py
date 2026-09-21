"""Batch generation + automatic QA with progress counters (used by the management commands)."""

from __future__ import annotations

import threading
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from django.db import connection

from apps.listening.models import AudioQAResult

from . import audio_qa
from .retry import with_retries
from .tts import TTSError, cached_variant, generate_variant, planned_key

Decision = AudioQAResult.Decision


@dataclass
class Report:
    cached: int = 0
    generated: int = 0
    generation_failed: int = 0
    qa_reused: int = 0
    qa_performed: int = 0
    decisions: Counter = field(default_factory=Counter)
    per_voice: dict = field(default_factory=lambda: defaultdict(Counter))
    failures: list = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record_qa(self, voice: str, outcome) -> None:
        with self.lock:
            if outcome.reused:
                self.qa_reused += 1
            else:
                self.qa_performed += 1
            decision = outcome.result.decision
            self.decisions[decision] += 1
            self.per_voice[voice][decision] += 1

    def lines(self, active: int, voices: int, levels: int, possible: int) -> list[str]:
        d = self.decisions
        out = [
            f"Active phrases: {active}",
            f"Voices: {voices}",
            f"Levels: {levels}",
            "",
            f"Possible variants: {possible}",
            "",
            f"Already cached: {self.cached}",
            f"Generated now: {self.generated}",
            f"Generation failed: {self.generation_failed}",
            "",
            f"QA reused: {self.qa_reused}",
            f"QA performed now: {self.qa_performed}",
            "",
            f"Auto-approved: {d[Decision.APPROVED]}",
            f"Needs review: {d[Decision.NEEDS_REVIEW]}",
            f"Rejected: {d[Decision.REJECTED]}",
            f"QA failed: {d[Decision.ERROR]}",
        ]
        for voice, c in self.per_voice.items():
            out += [
                "",
                f"{voice.capitalize()}:",
                f"approved {c[Decision.APPROVED]} / review {c[Decision.NEEDS_REVIEW]} / "
                f"rejected {c[Decision.REJECTED]} / qa failed {c[Decision.ERROR]}",
            ]
        return out


def run_group(
    voice,
    phrase,
    levels,
    accent,
    provider,
    *,
    auto_qa,
    report: Report,
    echo,
    transcriber=None,
    evaluator=None,
    header: str = "",
) -> None:
    """Generate the levels of one phrase in one voice, then QA them together (the delivery
    check needs all three levels). In a worker thread it owns and closes its DB connection."""
    lines = [header or f"[{voice}] {phrase.text}"]
    variants = []
    try:
        for level in levels:
            variant = cached_variant(planned_key(phrase, level, accent, voice, provider))
            if variant is not None:
                with report.lock:
                    report.cached += 1
                lines.append(f"  {level:8} cached")
                variants.append(variant)
                continue
            try:
                variant = with_retries(
                    lambda lv=level: generate_variant(
                        phrase, lv, accent, voice=voice, provider=provider
                    ),
                    label=f"tts {voice}/{level}",
                )
            except TTSError as exc:
                with report.lock:
                    report.generation_failed += 1
                    report.failures.append((phrase.text, voice, level, exc.kind))
                lines.append(f"  {level:8} FAILED ({exc.kind})")
                continue
            with report.lock:
                report.generated += 1
            lines.append(f"  {level:8} generated")
            variants.append(variant)
        if auto_qa:
            for variant in variants:
                outcome = audio_qa.run_qa(variant, transcriber, evaluator)
                report.record_qa(voice, outcome)
                r = outcome.result
                lines.append(
                    f"  {variant.level:8} QA {r.decision}"
                    f" ({'reused' if outcome.reused else f'score {r.overall_score}'})"
                )
    finally:
        if threading.current_thread() is not threading.main_thread():
            connection.close()  # worker threads own their connection
    echo("\n".join(lines))


def run_groups(
    tasks, levels, accent, provider, *, auto_qa, workers, report, echo, fail_fast=False
) -> None:
    transcriber = audio_qa.get_transcriber() if auto_qa else None
    evaluator = audio_qa.get_evaluator() if auto_qa else None

    def job(task, header=""):
        voice, phrase = task
        run_group(
            voice,
            phrase,
            levels,
            accent,
            provider,
            auto_qa=auto_qa,
            report=report,
            echo=echo,
            transcriber=transcriber,
            evaluator=evaluator,
            header=header,
        )

    if workers <= 1:
        current_voice = None
        per_voice = Counter(v for v, _ in tasks)
        index = Counter()
        for task in tasks:
            voice, phrase = task
            if voice != current_voice:
                echo(f"Voice: {voice.capitalize()}")
                current_voice = voice
            index[voice] += 1
            job(task, header=f"Phrase {index[voice]}/{per_voice[voice]}: {phrase.text}")
            if fail_fast and (report.generation_failed or report.decisions[Decision.ERROR]):
                return
        return
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(job, t) for t in tasks]
        for future in as_completed(futures):
            future.result()
            if fail_fast and (report.generation_failed or report.decisions[Decision.ERROR]):
                for f in futures:
                    f.cancel()
                return
