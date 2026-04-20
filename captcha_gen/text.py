"""
Генерация и очистка текста капчи.
"""

from __future__ import annotations

import random
import string

from captcha_gen.config import CAPTCHA_CONFIG

# ============================================================
# 🔤 КОНФИГУРАЦИЯ ТЕКСТА
# ============================================================

TEXT_CONFIG: dict = {
    # Визуально неоднозначные символы — заменяем в смешанных (буквы+цифры) строках
    "ambiguous_replacements": {
        "0": ["O", "o"],
        "1": ["I", "i", "l"],
    },
}

_UPPERS = string.ascii_uppercase
_LOWERS = string.ascii_lowercase
_DIGITS = string.digits


# ============================================================
# 🎲 ГЕНЕРАЦИЯ СЛУЧАЙНОГО ТЕКСТА
# ============================================================


def generate_random_text(
    min_len: int | None = None,
    max_len: int | None = None,
    rng: random.Random | None = None,
) -> str:
    """Случайная строка длиной [min_len; max_len]."""
    r = rng or random
    min_len = min_len if min_len is not None else CAPTCHA_CONFIG["min_length"]
    max_len = max_len if max_len is not None else CAPTCHA_CONFIG["max_length"]

    weights = CAPTCHA_CONFIG["char_type_weights"]
    groups = [_UPPERS, _LOWERS, _DIGITS]
    w = [weights["upper"], weights["lower"], weights["digit"]]

    length = r.randint(min_len, max_len)
    out: list[str] = []
    for _ in range(length):
        grp = r.choices(groups, weights=w)[0]
        out.append(r.choice(grp))
    return "".join(out)


# ============================================================
# 🧹 САНИТИЗАЦИЯ
# ============================================================


def sanitize_text(text: str, rng: random.Random | None = None) -> str:
    """
    В смешанных строках (есть и буква, и цифра) заменяет неоднозначные
    символы на их буквенные аналоги — чтобы сетка не «галлюцинировала».
    """
    r = rng or random
    has_digit = any(c.isdigit() for c in text)
    has_alpha = any(c.isalpha() for c in text)
    if not (has_digit and has_alpha):
        return text

    repl = TEXT_CONFIG["ambiguous_replacements"]
    out = []
    for ch in text:
        if ch in repl:
            ch = r.choice(repl[ch])
        out.append(ch)
    return "".join(out)
