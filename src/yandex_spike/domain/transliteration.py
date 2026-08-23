"""Систематическая латиница для сравнения (велосипед → velosiped), не «красивый» английский."""

_CYR_TO_LAT = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "kh",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "shch",
    "ы": "y",
    "э": "e",
    "ю": "yu",
    "я": "ya",
    "ь": "",
    "ъ": "",
}


def has_cyrillic(text: str) -> bool:
    return any("а" <= char <= "я" for char in text.lower())


def transliterate(text: str) -> str:
    """Кириллица → латиница. Латиницу не трогаем."""
    if not text or not has_cyrillic(text):
        return text
    return "".join(_CYR_TO_LAT.get(char, char) for char in text.lower())
