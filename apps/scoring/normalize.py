"""Text normalisation for dictation answers.

Normalises case, punctuation, apostrophes and whitespace, but deliberately keeps
linguistic differences (e.g. "I'll" vs "I will", "realise" vs "realize") visible so the
scorer can treat them as minor, labelled differences rather than hiding them.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "ʼ": "'", "`": "'", "´": "'"})
_SPLIT_RE = re.compile(r"[\s\-‐‑–—/]+")
_STRIP_RE = re.compile(r"[^a-z0-9']+")

NUMBER_WORDS = {
    "0": "zero",
    "1": "one",
    "2": "two",
    "3": "three",
    "4": "four",
    "5": "five",
    "6": "six",
    "7": "seven",
    "8": "eight",
    "9": "nine",
    "10": "ten",
    "11": "eleven",
    "12": "twelve",
    "13": "thirteen",
    "14": "fourteen",
    "15": "fifteen",
    "16": "sixteen",
    "17": "seventeen",
    "18": "eighteen",
    "19": "nineteen",
    "20": "twenty",
    "30": "thirty",
    "40": "forty",
    "50": "fifty",
    "100": "hundred",
}

# Words usually unstressed in connected speech (candidates for weak forms).
FUNCTION_WORDS = frozenset(
    """a an the to of for from at in on into onto by with and but or nor as than that
    some any can could would should will shall must may might do does did have has had
    am is are was were be been being i you he she it we they me him her us them my your
    his its our their there this these those just so if then 'll 'd 's 're 've 'm""".split()
)

# Contracted form -> canonical expansion. Ambiguous clitics keep an alias set.
CONTRACTIONS: dict[str, tuple[str, ...]] = {
    "can't": ("can", "not"),
    "cannot": ("can", "not"),
    "won't": ("will", "not"),
    "shan't": ("shall", "not"),
    "ain't": ("am", "not"),
    "let's": ("let", "us"),
    "gonna": ("going", "to"),
    "wanna": ("want", "to"),
    "gotta": ("got", "to"),
    "gimme": ("give", "me"),
    "lemme": ("let", "me"),
    "dunno": ("do", "not", "know"),
    "kinda": ("kind", "of"),
    "sorta": ("sort", "of"),
    "cuppa": ("cup", "of"),
    "y'all": ("you", "all"),
    "ya": ("you",),
}
_CLITICS: dict[str, tuple[str, frozenset[str]]] = {
    "n't": ("not", frozenset({"not"})),
    "'ll": ("will", frozenset({"will", "shall"})),
    "'re": ("are", frozenset({"are"})),
    "'ve": ("have", frozenset({"have"})),
    "'m": ("am", frozenset({"am"})),
    "'d": ("would", frozenset({"would", "had"})),
    "'s": ("is", frozenset({"is", "has", "us"})),
}
# Single-word equivalents that are spelling/register variants, not listening errors.
ALIASES: dict[str, str] = {"ok": "okay"}
# Contractions typed without the apostrophe (unambiguous ones only: not "ill", "its", "were").
_NO_APOSTROPHE = {
    w.replace("'", ""): w
    for w in """don't didn't doesn't can't won't isn't aren't wasn't weren't haven't hasn't
    hadn't couldn't wouldn't shouldn't mustn't needn't i'm i've you're you've you'll you'd
    they're they've they'll we've that's what's there's he's she's who's where's""".split()
}
_S_CONTRACTING = frozenset(
    {"it", "that", "what", "there", "here", "he", "she", "who", "where", "how", "when"}
)


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").translate(_APOSTROPHES).lower()
    text = text.replace("&", " and ")
    return " ".join(t for t in (_normalize_word(c) for c in _SPLIT_RE.split(text)) if t)


def _normalize_word(chunk: str) -> str:
    word = _STRIP_RE.sub("", chunk.lower()).strip("'")
    if word in NUMBER_WORDS:
        word = NUMBER_WORDS[word]
    word = _NO_APOSTROPHE.get(word, word)
    return ALIASES.get(word, word)


def surface_tokens(text: str) -> list[tuple[str, str]]:
    """(display form, normalised form) pairs. Positions match `tokenize(text)`."""
    text = unicodedata.normalize("NFKC", text or "").translate(_APOSTROPHES)
    text = text.replace("&", " and ")
    pairs = []
    for chunk in _SPLIT_RE.split(text):
        norm = _normalize_word(chunk)
        if norm:
            pairs.append((chunk, norm))
    return pairs


def tokenize(text: str) -> list[str]:
    return [norm for _, norm in surface_tokens(text)]


def spelling_key(word: str) -> str:
    """Collapse common British/American spelling differences (realise/realize, colour/color)."""
    w = word
    w = re.sub(r"yse(s|d)?$", r"yze\1", w)
    w = re.sub(r"is(e|es|ed|ing|ation|ations)$", r"iz\1", w)
    w = re.sub(r"our(s|ed|ing|ite|ites|ful)?$", r"or\1", w)
    w = re.sub(r"tre(s)?$", r"ter\1", w)
    w = re.sub(r"ll(ed|ing|er|ers)$", r"l\1", w)
    w = re.sub(r"ogue(s)?$", r"og\1", w)
    return {"grey": "gray", "programme": "program", "cheque": "check", "tyre": "tire"}.get(w, w)


@dataclass(frozen=True)
class CanonToken:
    """One canonical word. `origin` is the index of the surface token it came from."""

    canon: str
    origin: int
    contracted: bool = False
    aliases: frozenset[str] = field(default_factory=frozenset)

    def matches(self, other: CanonToken) -> bool:
        if self.canon == other.canon:
            return True
        return bool(self.all_forms & other.all_forms)

    @property
    def all_forms(self) -> frozenset[str]:
        return self.aliases | {self.canon}


def expand(tokens: list[str]) -> list[CanonToken]:
    """Split contractions into canonical words so "I'll" and "I will" can be aligned."""
    out: list[CanonToken] = []
    for i, tok in enumerate(tokens):
        if tok in CONTRACTIONS:
            out.extend(CanonToken(p, i, True) for p in CONTRACTIONS[tok])
            continue
        matched = False
        for clitic, (canon, aliases) in _CLITICS.items():
            if tok.endswith(clitic) and len(tok) > len(clitic):
                stem = tok[: -len(clitic)]
                if clitic == "n't":
                    stem = {"wo": "will", "ca": "can", "sha": "shall"}.get(stem, stem)
                if clitic == "'s" and stem not in _S_CONTRACTING:
                    break  # possessive ("John's"): keep as a single word
                out.append(CanonToken(stem, i, True))
                out.append(CanonToken(canon, i, True, aliases))
                matched = True
                break
        if not matched:
            out.append(CanonToken(tok, i))
    return out


def is_function_word(word: str) -> bool:
    return word in FUNCTION_WORDS
