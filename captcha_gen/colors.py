"""
Цветовые палитры для капч.

Цель — уйти от фиксированного фиолетового и генерировать полностью
случайные, но «читаемые» пары цветов (фон / текст) с гарантированным
контрастом. Часть капч рендерится в grayscale для разнообразия.
"""

from __future__ import annotations

import colorsys
import random

# ============================================================
# 🎨 КОНФИГУРАЦИЯ ЦВЕТОВ
# ============================================================

COLOR_CONFIG: dict = {
    # Вероятность рендера полностью в grayscale
    "grayscale_probability": 0.20,
    # Минимальный контраст (WCAG-like relative luminance difference, 0..1)
    # Чем больше, тем более контрастные пары; типичные пороги: 0.35..0.6
    "min_luminance_contrast": 0.35,
    # Максимум попыток сгенерировать контрастную пару
    "max_attempts": 50,
    # Насколько «ярче/темнее» фон относительно текста (в 50% случаев — текст светлее)
    "dark_text_probability": 0.70,
    # Диапазон насыщенности цветных пар (HSV)
    "saturation_range": (0.0, 0.80),
    # Яркость «светлой» и «тёмной» стороны пары (HSV value)
    "light_value_range": (0.80, 1.00),
    "dark_value_range": (0, 0.30),
    # Диапазон яркости для grayscale (фон светлый, текст тёмный — или наоборот)
    "grayscale_light_range": (190, 250),
    "grayscale_dark_range": (5, 70),
}

RGBA = tuple[int, int, int, int]
RGB = tuple[int, int, int]


# ============================================================
# 🔬 УТИЛИТЫ
# ============================================================


def _relative_luminance(rgb: RGB) -> float:
    """Упрощённый расчёт воспринимаемой яркости (0..1)."""
    r, g, b = (c / 255.0 for c in rgb)

    def _lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def _contrast(a: RGB, b: RGB) -> float:
    la, lb = _relative_luminance(a), _relative_luminance(b)
    return abs(la - lb)


def _hsv_to_rgb(h: float, s: float, v: float) -> RGB:
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return int(r * 255), int(g * 255), int(b * 255)


# ============================================================
# 🎨 ПУБЛИЧНОЕ API
# ============================================================


def random_color_pair(rng: random.Random | None = None) -> tuple[RGBA, RGBA]:
    """
    Возвращает (bg_rgba, text_rgba) — контрастную пару цветов.

    В 30% случаев пара строится в grayscale, в остальных — полноцветная.
    """
    r = rng or random

    if r.random() < COLOR_CONFIG["grayscale_probability"]:
        bg, text = _grayscale_pair(r)
    else:
        bg, text = _rgb_pair(r)

    return (*bg, 255), (*text, 255)


def _grayscale_pair(r: random.Random) -> tuple[RGB, RGB]:
    light = r.randint(*COLOR_CONFIG["grayscale_light_range"])
    dark = r.randint(*COLOR_CONFIG["grayscale_dark_range"])
    if r.random() < COLOR_CONFIG["dark_text_probability"]:
        return (light, light, light), (dark, dark, dark)
    return (dark, dark, dark), (light, light, light)


def _rgb_pair(r: random.Random) -> tuple[RGB, RGB]:
    """Генерирует полноцветную пару с нужным контрастом."""
    min_c = COLOR_CONFIG["min_luminance_contrast"]

    for _ in range(COLOR_CONFIG["max_attempts"]):
        # Золотое сечение для лучшего распределения Hue
        h1 = r.random()
        # Для текста выбираем либо контрастный тон (opposite), либо аналогичный
        h2 = (h1 + r.uniform(0.2, 0.8)) % 1.0

        s1 = r.uniform(*COLOR_CONFIG["saturation_range"])
        s2 = r.uniform(*COLOR_CONFIG["saturation_range"])

        # Дополнительная защита: если цвет попадает в "токсичный" зеленый (0.25-0.45),
        # принудительно снижаем его насыщенность
        if 0.25 < h1 < 0.45:
            s1 *= 0.7
        if 0.25 < h2 < 0.45:
            s2 *= 0.7

        if r.random() < COLOR_CONFIG["dark_text_probability"]:
            bg_v = r.uniform(*COLOR_CONFIG["light_value_range"])
            tx_v = r.uniform(*COLOR_CONFIG["dark_value_range"])
        else:
            bg_v = r.uniform(*COLOR_CONFIG["dark_value_range"])
            tx_v = r.uniform(*COLOR_CONFIG["light_value_range"])

        bg = _hsv_to_rgb(h1, s1, bg_v)
        tx = _hsv_to_rgb(h2, s2, tx_v)

        if _contrast(bg, tx) >= min_c:
            return bg, tx

    # fallback — гарантированно контрастная чёрно-белая пара
    return (245, 245, 245), (20, 20, 20)
