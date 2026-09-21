"""Generate a small side-by-side corpus to choose the TTS voice (not stored as AudioVariants).

    python manage.py audition_voices --dry-run
    python manage.py audition_voices --voices marin cedar fable

Writes MEDIA_ROOT/qa/tts-audition/<voice>/<level>/NN-slug.mp3, a manifest.json describing
every file and an index.html to listen to all voices and levels side by side.
Existing files are kept unless --force (so a failed run can simply be repeated).
"""

from __future__ import annotations

import html
import json
from datetime import UTC, datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from apps.ai.services.tts import TTSError, build_request, get_provider, provider_identity
from apps.listening.models import Accent, Level
from apps.listening.seed_data import AUDITION_PHRASES


class Command(BaseCommand):
    help = "Generate the same audition phrases with several voices and all levels."

    def add_arguments(self, parser):
        parser.add_argument("--voices", nargs="+", help="Default: TTS_AUDITION_VOICES.")
        parser.add_argument("--levels", nargs="+", choices=Level.values)
        parser.add_argument("--provider", default="openai", help="openai (default) or mock.")
        parser.add_argument("--accent", help="Accent code (default: the default accent).")
        parser.add_argument("--out", help="Output directory (default: MEDIA_ROOT/qa/tts-audition).")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--force", action="store_true", help="Regenerate existing files.")

    def handle(self, *args, **opts):
        voices = opts["voices"] or list(settings.TTS_AUDITION_VOICES)
        levels = opts["levels"] or list(Level.values)
        provider_name, model = provider_identity(opts["provider"])
        accent = (
            Accent.objects.filter(code=opts["accent"]).first()
            if opts["accent"]
            else Accent.default()
        )
        if accent is None:
            raise CommandError("Accent not found. Run seed_demo first.")
        out = Path(opts["out"] or Path(settings.MEDIA_ROOT) / "qa" / "tts-audition")
        total = len(AUDITION_PHRASES) * len(voices) * len(levels)
        self.stdout.write(
            f"{len(AUDITION_PHRASES)} phrases x {len(voices)} voices x {len(levels)} levels = "
            f"{total} audio generations ({provider_name}/{model}, accent={accent.code}) -> {out}"
        )
        if opts["dry_run"]:
            self.stdout.write("Dry run: no API calls made.")
            return
        if provider_name == "openai" and not settings.OPENAI_API_KEY:
            raise CommandError("OPENAI_API_KEY is not set in the environment (.env).")
        try:
            tts = get_provider(opts["provider"])
        except TTSError as exc:
            raise CommandError(str(exc)) from exc

        manifest_path = out / "manifest.json"
        manifest = {}
        if manifest_path.exists():
            for entry in json.loads(manifest_path.read_text(encoding="utf-8")).get("files", []):
                manifest[entry["filename"]] = entry

        failures = 0
        for n, item in enumerate(AUDITION_PHRASES, start=1):
            for voice in voices:
                for level in levels:
                    request = build_request(item["text"], level, accent, voice)
                    ext = "wav" if provider_name == "mock" else "mp3"
                    rel = f"{voice}/{level}/{n:02d}-{slugify(item['text'])[:50]}.{ext}"
                    path = out / rel
                    if path.exists() and path.stat().st_size and not opts["force"]:
                        continue
                    try:
                        result = tts.synthesize(request)
                    except TTSError as exc:
                        failures += 1
                        self.stderr.write(
                            f"  FAIL [{voice}/{level}] {exc.kind}: {exc} | {item['text']}"
                        )
                        continue
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(result.audio)
                    manifest[rel] = {
                        "phrase": item["text"],
                        "focus": item.get("focus", ""),
                        "voice": voice,
                        "model": result.model,
                        "provider": result.provider,
                        "level": level,
                        "accent": accent.code,
                        "instructions": request.instructions,
                        "speed": request.speed,
                        "filename": rel,
                        "duration_ms": result.duration_ms if result.duration_measured else None,
                        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
                    }
                    self.stdout.write(f"  ok   {rel}")

        out.mkdir(parents=True, exist_ok=True)
        files = sorted(manifest.values(), key=lambda e: e["filename"])
        manifest_path.write_text(
            json.dumps(
                {"engine_version": str(settings.TTS_ENGINE_VERSION), "files": files},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (out / "index.html").write_text(render_index(files, voices, levels), encoding="utf-8")
        self.stdout.write(f"Manifest: {manifest_path}\nListen: {out / 'index.html'}")
        if failures:
            raise CommandError(f"{failures} file(s) failed; rerun to retry (others are kept).")


def render_index(files: list[dict], voices: list[str], levels: list[str]) -> str:
    """Static page: one row per phrase, one column per voice, three levels per cell."""
    by_key = {(f["phrase"], f["voice"], f["level"]): f for f in files}
    phrases = []
    for f in files:
        if f["phrase"] not in [p[0] for p in phrases]:
            phrases.append((f["phrase"], f.get("focus", "")))
    head = "".join(f"<th>{html.escape(v)}</th>" for v in voices)
    rows = []
    for text, focus in phrases:
        cells = []
        for voice in voices:
            parts = []
            for level in levels:
                entry = by_key.get((text, voice, level))
                if entry:
                    parts.append(
                        f'<div class="lv"><b>{level}</b><audio controls preload="none" '
                        f'src="{html.escape(entry["filename"])}"></audio></div>'
                    )
            cells.append(f"<td>{''.join(parts)}</td>")
        rows.append(
            f"<tr><td><p>{html.escape(text)}</p><small>{html.escape(focus)}</small></td>"
            f"{''.join(cells)}</tr>"
        )
    return (
        "<!doctype html><meta charset='utf-8'><title>dictare.ro · TTS voice audition</title>"
        "<style>body{font-family:system-ui,sans-serif;margin:24px;color:#0f1b3d}"
        "table{border-collapse:collapse;width:100%}td,th{border:1px solid #e4eaf4;padding:8px;"
        "vertical-align:top;text-align:left}small{color:#5b6784}.lv{display:flex;gap:8px;"
        "align-items:center;margin:4px 0}.lv b{width:56px;font-size:12px}"
        "audio{height:32px}</style>"
        "<h1>TTS voice audition</h1><p>Same phrases, same settings; compare voices per level.</p>"
        f"<table><tr><th>Phrase</th>{head}</tr>{''.join(rows)}</table>"
    )
