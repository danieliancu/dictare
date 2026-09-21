"""The voices offered to learners — the single source of truth.

Other OpenAI voices remain technically usable by the generation commands (e.g. for
auditions), but only these are offered in the product and stored as preferences.
"""

VOICE_CHOICES = [
    ("marin", "Marin"),
    ("ballad", "Ballad"),
    ("cedar", "Cedar"),
]
VOICE_VALUES = [value for value, _ in VOICE_CHOICES]
DEFAULT_VOICE = "marin"
# When a recording in the learner's voice is missing, only this voice may stand in for it.
FALLBACK_VOICE = DEFAULT_VOICE
