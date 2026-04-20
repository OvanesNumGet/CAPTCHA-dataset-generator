"""
Работа со шрифтами.

Сканирует директорию fonts/ (рекурсивно) и позволяет случайно выбирать
из доступных файлов .ttf/.otf. Кеширует список, чтобы не ходить в ФС
на каждую капчу.
"""

from __future__ import annotations

from pathlib import Path
import random

from PIL import ImageFont

from captcha_gen.config import DEFAULT_FONTS_DIR

# ============================================================
# 🔤 КОНФИГУРАЦИЯ ШРИФТОВ
# ============================================================

FONT_CONFIG: dict = {
    # Диапазон случайных размеров шрифта (в pt)
    "size_range": (45, 85),
    # Расширения, которые считаем шрифтами
    "extensions": (".ttf", ".otf", ".ttc"),
    # Fallback-шрифты, если папка пуста или не найдена
    "fallback_fonts": ("arial.ttf", "times.ttf", "DejaVuSans.ttf"),
}

# Кеш по директории: {str(fonts_dir): list[Path]}
_FONT_CACHE: dict[str, list[Path]] = {}


# ============================================================
# 📦 ПОИСК ШРИФТОВ
# ============================================================


def discover_fonts(fonts_dir: str | Path = DEFAULT_FONTS_DIR) -> list[Path]:
    """Рекурсивно ищет шрифты в указанной папке. Кеширует результат."""
    key = str(fonts_dir)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]

    fonts_dir = Path(fonts_dir)
    found: list[Path] = []
    if fonts_dir.exists() and fonts_dir.is_dir():
        for ext in FONT_CONFIG["extensions"]:
            found.extend(fonts_dir.rglob(f"*{ext}"))

    result = sorted(found)
    _FONT_CACHE[key] = result
    return result


def reset_font_cache() -> None:
    """Сбросить кеш (например, после добавления новых шрифтов или в дочернем процессе)."""
    global _FONT_CACHE
    _FONT_CACHE = {}


# ============================================================
# 🎲 СЛУЧАЙНЫЙ ВЫБОР ШРИФТА
# ============================================================


def random_font(
    rng: random.Random | None = None,
    size: int | None = None,
    fonts_dir: str | Path = DEFAULT_FONTS_DIR,
) -> ImageFont.FreeTypeFont:
    """
    Возвращает случайный ImageFont.FreeTypeFont случайного размера.

    Если размер не указан — берётся случайный из FONT_CONFIG['size_range'].
    Если в папке нет шрифтов, пробуем fallback, а в крайнем случае —
    встроенный default.
    """
    r = rng or random
    if size is None:
        size = r.randint(*FONT_CONFIG["size_range"])

    candidates = discover_fonts(fonts_dir)

    if candidates:
        font_path = r.choice(candidates)
        try:
            return ImageFont.truetype(str(font_path), size)
        except Exception:
            pass  # испорченный файл — идём в fallback

    for fallback in FONT_CONFIG["fallback_fonts"]:
        try:
            return ImageFont.truetype(fallback, size)
        except Exception:
            continue

    # Крайний случай — бит-мап шрифт Pillow
    return ImageFont.load_default()


def random_font_size(rng: random.Random | None = None) -> int:
    r = rng or random
    return r.randint(*FONT_CONFIG["size_range"])
