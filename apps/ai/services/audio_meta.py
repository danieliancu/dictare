"""Read the real duration of generated audio without extra dependencies."""

from __future__ import annotations

import io
import wave

# MPEG audio: bitrate tables (kbps) indexed by [version_is_mpeg1][layer][index].
_BITRATES = {
    (True, 3): [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320],
    (True, 2): [0, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384],
    (True, 1): [0, 32, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384, 416, 448],
    (False, 3): [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],
    (False, 2): [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],
    (False, 1): [0, 32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256],
}
_SAMPLE_RATES = {3: [44100, 48000, 32000], 2: [22050, 24000, 16000], 0: [11025, 12000, 8000]}
_LAYERS = {1: 3, 2: 2, 3: 1}  # header bits -> layer number


def mp3_duration_ms(data: bytes) -> int | None:
    """Sum the duration of every MPEG frame. Returns None if the data is not a readable MP3."""
    pos = 0
    if data[:3] == b"ID3" and len(data) >= 10:
        size = (data[6] << 21) | (data[7] << 14) | (data[8] << 7) | data[9]
        pos = 10 + size
    total_seconds = 0.0
    frames = 0
    n = len(data)
    while pos + 4 <= n:
        b1, b2 = data[pos + 1], data[pos + 2]
        if data[pos] != 0xFF or (b1 & 0xE0) != 0xE0:
            if frames:
                break  # trailing tag / padding after the audio frames
            pos += 1
            continue
        version_bits = (b1 >> 3) & 0x03
        layer = _LAYERS.get((b1 >> 1) & 0x03)
        bitrate_index = (b2 >> 4) & 0x0F
        rate_index = (b2 >> 2) & 0x03
        if version_bits == 1 or layer is None or bitrate_index in (0, 15) or rate_index == 3:
            pos += 1
            continue
        mpeg1 = version_bits == 3
        bitrate = _BITRATES[(mpeg1, layer)][bitrate_index] * 1000
        sample_rate = _SAMPLE_RATES[version_bits][rate_index]
        padding = (b2 >> 1) & 0x01
        if layer == 1:
            samples = 384
            length = (12 * bitrate // sample_rate + padding) * 4
        else:
            samples = 1152 if (layer == 2 or mpeg1) else 576
            length = (samples // 8) * bitrate // sample_rate + padding
        if length <= 4:
            break
        total_seconds += samples / sample_rate
        frames += 1
        pos += length
    if not frames:
        return None
    return round(total_seconds * 1000)


def wav_duration_ms(data: bytes) -> int | None:
    try:
        with wave.open(io.BytesIO(data)) as wav:
            return round(1000 * wav.getnframes() / wav.getframerate())
    except (wave.Error, EOFError, ZeroDivisionError):
        return None


def audio_duration_ms(data: bytes, extension: str) -> int | None:
    if extension == "wav":
        return wav_duration_ms(data)
    if extension == "mp3":
        return mp3_duration_ms(data)
    return None


def looks_like_mp3(data: bytes) -> bool:
    return len(data) > 128 and (
        data[:3] == b"ID3" or (data[0] == 0xFF and (data[1] & 0xE0) == 0xE0)
    )
