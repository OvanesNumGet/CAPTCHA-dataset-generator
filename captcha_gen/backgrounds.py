"""
Генерация фонов для капч.

Поддерживаем четыре типа:
  • solid     — одноцветный
  • gradient  — линейный градиент из двух цветов
  • noise     — Перлин-подобный пиксельный шум
  • photo     — случайное фото из папки DEFAULT_BG_IMAGES_DIR (если есть)

Выбор типа — случайный, с вероятностями из BACKGROUND_CONFIG.
Если фотографий нет, этот тип исключается автоматически.
"""

from __future__ import annotations

from pathlib import Path
import random

from PIL import Image, ImageFilter
import numpy as np

from captcha_gen.colors import random_color_pair
from captcha_gen.config import DEFAULT_BG_IMAGES_DIR

# ============================================================
# 🖼 КОНФИГУРАЦИЯ ФОНОВ
# ============================================================

BACKGROUND_CONFIG: dict = {
    # Базовые вероятности (нормализуются автоматически, могут не давать 1.0)
    "type_weights": {
        "solid": 0.30,
        "gradient": 0.35,
        "noise": 0.25,
        "photo": 0.10,
    },
    "photos_dir": DEFAULT_BG_IMAGES_DIR,
    "photo_extensions": (".jpg", ".jpeg", ".png", ".webp", ".bmp"),
    # Параметры noise-фона
    "noise_blur_radius_range": (0.0, 2.5),
    "noise_intensity_range": (0, 50),
    # Для photo-фона: «заглушить» фон, чтобы текст был читаем
    "photo_brightness_range": (0.55, 1.0),
    "photo_blur_probability": 1.0,
    "photo_blur_radius_range": (0.0, 2.0),
}

_PHOTO_CACHE: list[Path] | None = None


# ============================================================
# 📷 ФОТО-ФОНЫ
# ============================================================


def _discover_photos() -> list[Path]:
    global _PHOTO_CACHE
    if _PHOTO_CACHE is not None:
        return _PHOTO_CACHE
    photos_dir = Path(BACKGROUND_CONFIG["photos_dir"])
    found: list[Path] = []
    if photos_dir.exists() and photos_dir.is_dir():
        for ext in BACKGROUND_CONFIG["photo_extensions"]:
            found.extend(photos_dir.rglob(f"*{ext}"))
    _PHOTO_CACHE = sorted(found)
    return _PHOTO_CACHE


# ============================================================
# 🎨 ГЕНЕРАТОРЫ
# ============================================================


def _solid_bg(
    size: tuple[int, int], rng: random.Random
) -> tuple[Image.Image, tuple]:
    bg_rgba, text_rgba = random_color_pair(rng)
    img = Image.new("RGB", size, bg_rgba[:3])
    return img, text_rgba


def _gradient_bg(
    size: tuple[int, int], rng: random.Random
) -> tuple[Image.Image, tuple]:
    w, h = size
    bg_rgba, text_rgba = random_color_pair(rng)
    c1 = np.array(bg_rgba[:3], dtype=np.float32)

    shift = rng.uniform(-40, 40)
    c2 = np.clip(c1 + shift, 0, 255)

    direction = rng.choice(["h", "v", "d1", "d2"])
    if direction == "h":
        t = np.linspace(0, 1, w, dtype=np.float32)[None, :, None]
        arr = c1 * (1 - t) + c2 * t
        arr = np.broadcast_to(arr, (h, w, 3))
    elif direction == "v":
        t = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
        arr = c1 * (1 - t) + c2 * t
        arr = np.broadcast_to(arr, (h, w, 3))
    else:
        xs = np.linspace(0, 1, w, dtype=np.float32)
        ys = np.linspace(0, 1, h, dtype=np.float32)
        gx, gy = np.meshgrid(xs, ys)
        t = (gx + gy) / 2 if direction == "d1" else (gx + (1 - gy)) / 2
        t = t[..., None]
        arr = c1 * (1 - t) + c2 * t

    arr = np.clip(arr, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB"), text_rgba


def _noise_bg(
    size: tuple[int, int], rng: random.Random
) -> tuple[Image.Image, tuple]:
    w, h = size
    bg_rgba, text_rgba = random_color_pair(rng)
    base = np.array(bg_rgba[:3], dtype=np.int16)

    intensity = rng.randint(*BACKGROUND_CONFIG["noise_intensity_range"])
    noise = np.random.randint(
        -intensity, intensity + 1, size=(h, w, 3), dtype=np.int16
    )
    arr = np.clip(base + noise, 0, 255).astype(np.uint8)

    img = Image.fromarray(arr, "RGB")
    radius = rng.uniform(*BACKGROUND_CONFIG["noise_blur_radius_range"])
    img = img.filter(ImageFilter.GaussianBlur(radius=radius))
    return img, text_rgba


def _photo_bg(
    size: tuple[int, int], rng: random.Random
) -> tuple[Image.Image, tuple] | None:
    photos = _discover_photos()
    if not photos:
        return None

    path = rng.choice(photos)
    try:
        img = Image.open(path).convert("RGB")
    except Exception:
        return None

    # Случайный crop под нужный aspect ratio
    w, h = size
    iw, ih = img.size
    target_ratio = w / h
    cur_ratio = iw / ih
    if cur_ratio > target_ratio:
        new_w = int(ih * target_ratio)
        x0 = rng.randint(0, iw - new_w)
        img = img.crop((x0, 0, x0 + new_w, ih))
    else:
        new_h = int(iw / target_ratio)
        y0 = rng.randint(0, ih - new_h)
        img = img.crop((0, y0, iw, y0 + new_h))

    img = img.resize(size, Image.BICUBIC)

    # Легкое размытие + затемнение для читаемости текста
    if rng.random() < BACKGROUND_CONFIG["photo_blur_probability"]:
        radius = rng.uniform(*BACKGROUND_CONFIG["photo_blur_radius_range"])
        img = img.filter(ImageFilter.GaussianBlur(radius=radius))

    bright = rng.uniform(*BACKGROUND_CONFIG["photo_brightness_range"])
    arr = (
        (np.asarray(img, dtype=np.float32) * bright)
        .clip(0, 255)
        .astype(np.uint8)
    )
    img = Image.fromarray(arr, "RGB")

    # Цвет текста подбираем от противного: относительно средней яркости фото
    mean_v = arr.mean()
    if mean_v > 127:
        text_rgba = (
            rng.randint(0, 60),
            rng.randint(0, 60),
            rng.randint(0, 60),
            255,
        )
    else:
        text_rgba = (
            rng.randint(200, 255),
            rng.randint(200, 255),
            rng.randint(200, 255),
            255,
        )

    return img, text_rgba


# ============================================================
# 🚪 ПУБЛИЧНЫЙ API
# ============================================================


def random_background(
    size: tuple[int, int],
    rng: random.Random | None = None,
) -> tuple[Image.Image, tuple]:
    """
    Возвращает (background_rgb_image, text_color_rgba).

    Тип фона выбирается случайно согласно BACKGROUND_CONFIG['type_weights'].
    """
    r = rng or random
    weights = BACKGROUND_CONFIG["type_weights"].copy()
    if not _discover_photos():
        weights.pop("photo", None)

    types = list(weights.keys())
    probs = list(weights.values())

    chosen = r.choices(types, weights=probs)[0]

    if chosen == "solid":
        return _solid_bg(size, r)
    if chosen == "gradient":
        return _gradient_bg(size, r)
    if chosen == "noise":
        return _noise_bg(size, r)
    if chosen == "photo":
        result = _photo_bg(size, r)
        if result is not None:
            return result
        return _gradient_bg(size, r)

    return _solid_bg(size, r)
