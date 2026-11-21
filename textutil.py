"""Text normalisation + phrase matching that works for English, Hindi and Hinglish.

Why this exists
---------------
* Python's ``\\w`` does not match Devanagari vowel signs (matras), so a naive
  tokenizer cuts Hindi words in pieces. We use an explicit Devanagari range.
* Hindi spelling varies a lot (nukta, chandrabindu/anusvara, spaces inside
  compound words such as "प्रमाण पत्र" / "प्रमाणपत्र"). We normalise both the
  searched text and the search phrases the same way, and for longer Hindi
  phrases we compare with spaces removed.
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

DEVA_RE = re.compile(r"[ऀ-ॿ]")
# letters/digits/Devanagari (excluding danda U+0964/0965)
TOKEN_RE = re.compile(r"[\wऀ-ॣ०-ॿ]+", re.UNICODE)

# zero-width chars, soft hyphen, nukta -> removed ; chandrabindu -> anusvara
_TRANS = {ord(c): None for c in "​‌‍⁠﻿­़"}
_TRANS[0x0901] = "ं"
_TRANS.update({0x0966 + i: ord(str(i)) for i in range(10)})  # Devanagari digits -> ASCII

_ACRONYM_RE = re.compile(r"(?<![a-z0-9])(?:[a-z]\.){2,}")
_PUNCT_RE = re.compile(r"[^\wऀ-ॣ०-ॿ\s]+|_+")
_LETTER_DIGIT_RE = re.compile(r"(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])")
_WS_RE = re.compile(r"\s+")


def normalize_text(s: object) -> str:
    """Lower-case, strip punctuation, unify Hindi spelling variants."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", str(s))
    s = s.translate(_TRANS).lower()
    s = _ACRONYM_RE.sub(lambda m: m.group(0).replace(".", ""), s)
    s = s.replace("&", " and ")
    s = _PUNCT_RE.sub(" ", s)
    s = _LETTER_DIGIT_RE.sub(" ", s)
    return _WS_RE.sub(" ", s).strip()


def tokens(s: object) -> list[str]:
    return normalize_text(s).split()


def has_devanagari(s: str) -> bool:
    return bool(DEVA_RE.search(s or ""))


def devanagari_ratio(s: str) -> float:
    letters = [c for c in s if c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if "ऀ" <= c <= "ॿ") / len(letters)


@lru_cache(maxsize=20000)
def _phrase_kind(phrase: str) -> tuple[bool, str]:
    """(use_squashed_matching, squashed_phrase)"""
    sq = phrase.replace(" ", "")
    return (bool(DEVA_RE.search(phrase)) and len(sq) >= 6), sq


class TextView:
    """A normalised text that can be searched for normalised phrases."""

    __slots__ = ("padded", "_sq")

    def __init__(self, text: str = "", *, normalized: bool = False):
        norm = text if normalized else normalize_text(text)
        self.padded = f" {norm} "
        self._sq: str | None = None

    @property
    def norm(self) -> str:
        return self.padded[1:-1]

    @property
    def squashed(self) -> str:
        if self._sq is None:
            self._sq = self.padded.replace(" ", "")
        return self._sq

    def count(self, phrase: str) -> int:
        if not phrase:
            return 0
        use_sq, sq = _phrase_kind(phrase)
        if use_sq:
            return self.squashed.count(sq)
        return self.padded.count(f" {phrase} ")

    def has(self, phrase: str) -> bool:
        if not phrase:
            return False
        use_sq, sq = _phrase_kind(phrase)
        if use_sq:
            return sq in self.squashed
        return f" {phrase} " in self.padded

    def without(self, phrases) -> "TextView":
        """Return a view with the given phrases blanked out (used for exclusions)."""
        t = self.padded
        changed = False
        for ph in phrases:
            key = f" {ph} "
            if key in t:
                changed = True
                while key in t:
                    t = t.replace(key, " ")
        return TextView(t.strip(), normalized=True) if changed else self

    def __len__(self) -> int:
        return len(self.norm)


STOPWORDS = frozenset(
    """the of and or for to in a an by with copy copies self attested certified valid latest
    bidder bidders firm company document documents submit submitted scanned duly signed stamped
    relevant required proof as per on from at is be shall should must any all each form format
    details detail regarding related applicable if last years year three five certificate
    letter statement list report registration number no
    की का के में से और एवं तथा हेतु द्वारा पर को है हैं यह वह प्रति सत्यापित स्व स्वप्रमाणित वैध नवीनतम
    फर्म बोलीदाता निविदाकार दस्तावेज संबंधित संलग्न प्रस्तुत विवरण""".split()
)


def significant_tokens(s: str, min_len: int = 3) -> list[str]:
    out: list[str] = []
    for t in tokens(s):
        if t in STOPWORDS or t.isdigit():
            continue
        if len(t) < min_len:
            continue
        if t not in out:
            out.append(t)
    return out
