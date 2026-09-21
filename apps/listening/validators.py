from django.core.exceptions import ValidationError

MAX_AUDIO_BYTES = 5 * 1024 * 1024
ALLOWED_EXTENSIONS = {"mp3", "wav", "ogg", "m4a"}


def _sniff(head: bytes) -> str | None:
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "wav"
    if head[:3] == b"ID3" or (len(head) > 1 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0):
        return "mp3"
    if head[:4] == b"OggS":
        return "ogg"
    if head[4:8] == b"ftyp":
        return "m4a"
    return None


def validate_audio_file(file) -> None:
    """Check size, extension and the actual file signature of an uploaded recording."""
    if file.size and file.size > MAX_AUDIO_BYTES:
        raise ValidationError("Fișierul audio depășește 5 MB.")
    ext = file.name.rsplit(".", 1)[-1].lower() if "." in file.name else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError("Format acceptat: MP3, WAV, OGG sau M4A.")
    try:
        pos = file.tell()
        file.seek(0)
        head = file.read(16)
        file.seek(pos)
    except (AttributeError, OSError, ValueError):
        return
    kind = _sniff(head)
    if kind is None:
        raise ValidationError("Fișierul nu pare să fie un fișier audio valid.")
