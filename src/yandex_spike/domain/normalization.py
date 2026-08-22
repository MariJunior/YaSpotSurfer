from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Не схлопываем remaster/live в original — только помечаем.
# Длинные фразы раньше коротких, чтобы "radio edit" не резался на "radio".
VERSION_TAGS = (
    "radio edit",
    "extended edit",
    "club edit",
    "sped up",
    "remastered",
    "instrumental",
    "acoustic",
    "extended",
    "remaster",
    "remix",
    "slowed",
    "cover",
    "demo",
    "live",
    "mono",
    "stereo",
    "edit",
)

_FEAT_RE = re.compile(
    r"\s*[\(\[]?\s*(?:feat\.?|ft\.?|featuring)\s+.+",
    re.IGNORECASE,
)
_BRACKET_RE = re.compile(r"[\(\[\{].*?[\)\]\}]")
_PUNCT_RE = re.compile(r"[^\w\s]+", re.UNICODE)
_SPACE_RE = re.compile(r"\s+")
# Год рядом с remaster/live: "2011 Remaster", не заголовок вроде "1999".
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
# Spotify часто пишет подзаголовок после " - ", Яндекс — в скобках.
_DASH_SPLIT_RE = re.compile(r"\s+[-–—]\s+")
_VERSION_FIND_RE = re.compile(
    r"\b(?:"
    + "|".join(re.escape(tag) for tag in VERSION_TAGS)
    + r")\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class NormalizedTitle:
    text: str
    version_tags: tuple[str, ...]


def _fold_yo(value: str) -> str:
    return value.replace("ё", "е").replace("Ё", "е")


def extract_version_tags(title: str) -> tuple[str, ...]:
    lowered = unicodedata.normalize("NFKC", title).lower()
    # Границы слов: иначе "Olivia" ловит live, "coverage" ловит cover.
    found = [tag for tag in VERSION_TAGS if re.search(rf"\b{re.escape(tag)}\b", lowered)]
    return tuple(found)


def title_head(title: str | None) -> str:
    """Часть до первого ' - '. Сам normalize_title тире не режет: «Ёлка — Прованс»."""
    return _DASH_SPLIT_RE.split(title or "", maxsplit=1)[0]


def _strip_version_noise(text: str) -> str:
    text = _VERSION_FIND_RE.sub(" ", text)
    text = _YEAR_RE.sub(" ", text)
    return text


def normalize_title(title: str | None) -> NormalizedTitle:
    raw = title or ""
    tags = extract_version_tags(raw)
    text = unicodedata.normalize("NFKC", raw)
    text = _fold_yo(text)
    text = _FEAT_RE.sub("", text)
    text = _BRACKET_RE.sub(" ", text)
    # "Song Name - 2011 Remaster" и скобочные формы сводим к одному original.
    if tags:
        text = _strip_version_noise(text)
    text = text.lower()
    text = _PUNCT_RE.sub(" ", text)
    text = _SPACE_RE.sub(" ", text).strip()
    return NormalizedTitle(text=text, version_tags=tags)


def normalize_artist(name: str | None) -> str:
    raw = name or ""
    text = unicodedata.normalize("NFKC", raw)
    text = _fold_yo(text)
    text = _FEAT_RE.sub("", text)
    text = text.lower()
    text = _PUNCT_RE.sub(" ", text)
    text = _SPACE_RE.sub(" ", text).strip()
    return text
