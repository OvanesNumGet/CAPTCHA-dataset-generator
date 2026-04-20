"""
Цветовые палитры для капч.

Цель — генерировать всевозможные стили: пастельные, неоновые, тёмные,
тусклые, контрастные, монохромные. Гарантируется читаемость с помощью
WCAG contrast ratio, но порог снижен для создания сложных для ИИ капч.
"""

from __future__ import annotations

import colorsys
import random

# ============================================================
# 🎨 КОНФИГУРАЦИЯ ЦВЕТОВ
# ============================================================

COLOR_CONFIG: dict = {
    # Вероятность полностью обесцвеченной пары (чёрно-белая / оттенки серого)
    "grayscale_probability": 0.15,
    # Минимальный контраст по стандарту WCAG (1 - неразличимо, 21 - ч/б).
    # 2.2 - это читаемо человеком, но уже немного «блёкло» или тяжело.
    # Больше 4.5 - отлично читаемо.
    "min_contrast_ratio": 2.2,
    # Максимум попыток подобрать контрастную пару
    "max_attempts": 100,
}

RGBA = tuple[int, int, int, int]
RGB = tuple[int, int, int]


# ============================================================
# 🔬 УТИЛИТЫ КОНТРАСТА (WCAG)
# ============================================================


def _relative_luminance(rgb: RGB) -> float:
    """Расчёт воспринимаемой яркости (0..1) по стандарту sRGB."""
    r, g, b = (c / 255.0 for c in rgb)

    def _lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def _contrast(a: RGB, b: RGB) -> float:
    """WCAG Contrast Ratio (1.0 .. 21.0)."""
    la = _relative_luminance(a)
    lb = _relative_luminance(b)
    l1 = max(la, lb)
    l2 = min(la, lb)
    return (l1 + 0.05) / (l2 + 0.05)


def _hsv_to_rgb(h: float, s: float, v: float) -> RGB:
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return int(r * 255), int(g * 255), int(b * 255)


# ============================================================
# 🎨 ПУБЛИЧНОЕ API
# ============================================================


def random_color_pair(rng: random.Random | None = None) -> tuple[RGBA, RGBA]:
    """
    Возвращает (bg_rgba, text_rgba) — пару цветов всевозможных стилей
    и оттенков (неоновые, пастельные, тёмные, светлые), прошедших
    проверку на читаемость (контраст).
    """
    r = rng or random

    if r.random() < COLOR_CONFIG["grayscale_probability"]:
        bg, text = _grayscale_pair(r)
    else:
        bg, text = _rgb_pair(r)

    return (*bg, 255), (*text, 255)


def _grayscale_pair(r: random.Random) -> tuple[RGB, RGB]:
    """Любые случайные оттенки серого с достаточным контрастом."""
    min_c = COLOR_CONFIG["min_contrast_ratio"]
    for _ in range(COLOR_CONFIG["max_attempts"]):
        v1 = r.random()
        v2 = r.random()
        bg = (int(v1 * 255), int(v1 * 255), int(v1 * 255))
        tx = (int(v2 * 255), int(v2 * 255), int(v2 * 255))
        if _contrast(bg, tx) >= min_c:
            return bg, tx
    return (245, 245, 245), (20, 20, 20)


def _rgb_pair(r: random.Random) -> tuple[RGB, RGB]:
    """
    Генерирует пару через один из паттернов (пастель, неон, тусклые, монохром),
    а также полностью случайно, проверяя читаемость по контрасту.
    """
    min_c = COLOR_CONFIG["min_contrast_ratio"]

    strategies = [
        "pure_random",
        "pastel_vs_dark",
        "dark_vs_neon",
        "muted_vs_light",
        "monochrome_ish",
        "high_saturation",
        "faded",
    ]

    for _ in range(COLOR_CONFIG["max_attempts"]):
        mode = r.choice(strategies)

        if mode == "pure_random":
            h1, s1, v1 = r.random(), r.random(), r.random()
            h2, s2, v2 = r.random(), r.random(), r.random()

        elif mode == "pastel_vs_dark":
            # Пастель (высокая яркость, низкая насыщенность) против тёмного
            h1, s1, v1 = r.random(), r.uniform(0.1, 0.4), r.uniform(0.8, 1.0)
            h2, s2, v2 = r.random(), r.random(), r.uniform(0.0, 0.35)
            if r.random() < 0.5:
                h1, s1, v1, h2, s2, v2 = h2, s2, v2, h1, s1, v1

        elif mode == "dark_vs_neon":
            # Очень тёмный фон и ядовитый неон (или наоборот)
            h1, s1, v1 = r.random(), r.uniform(0.5, 1.0), r.uniform(0.0, 0.2)
            h2, s2, v2 = r.random(), r.uniform(0.7, 1.0), r.uniform(0.8, 1.0)
            if r.random() < 0.5:
                h1, s1, v1, h2, s2, v2 = h2, s2, v2, h1, s1, v1

        elif mode == "muted_vs_light":
            # Приглушённые средние тона против очень светлых/белых
            h1, s1, v1 = r.random(), r.uniform(0.1, 0.4), r.uniform(0.3, 0.6)
            h2, s2, v2 = r.random(), r.uniform(0.0, 0.15), r.uniform(0.85, 1.0)
            if r.random() < 0.5:
                h1, s1, v1, h2, s2, v2 = h2, s2, v2, h1, s1, v1

        elif mode == "monochrome_ish":
            # Один оттенок, но разная яркость/насыщенность
            base_h = r.random()
            h1 = base_h
            h2 = (base_h + r.uniform(-0.05, 0.05)) % 1.0
            s1, v1 = r.random(), r.random()
            s2, v2 = r.random(), r.random()

        elif mode == "high_saturation":
            # Оба цвета насыщенные, но один светлый, а другой тёмный
            h1, s1, v1 = r.random(), r.uniform(0.7, 1.0), r.uniform(0.8, 1.0)
            h2, s2, v2 = r.random(), r.uniform(0.7, 1.0), r.uniform(0.1, 0.4)
            if r.random() < 0.5:
                h1, s1, v1, h2, s2, v2 = h2, s2, v2, h1, s1, v1

        else:  # "faded"
            # Блёклые, низкоконтрастные цвета (всё стремится к серому)
            h1, s1, v1 = r.random(), r.uniform(0.0, 0.3), r.uniform(0.4, 0.8)
            h2, s2, v2 = r.random(), r.uniform(0.0, 0.3), r.uniform(0.2, 0.9)

        bg = _hsv_to_rgb(h1, s1, v1)
        tx = _hsv_to_rgb(h2, s2, v2)

        # Если контраст удовлетворяет нашему пониженному порогу - берём
        if _contrast(bg, tx) >= min_c:
            return bg, tx

    # Запасной вариант, если за 100 попыток не нашли (почти невозможно)
    return (245, 245, 245), (20, 20, 20)
