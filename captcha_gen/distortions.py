"""
Собственные геометрические искажения (mesh-wave).

Albumentations закрывает ElasticTransform/Affine и прочее, но «фирменная»
волна поверх букв — наша фишка, поэтому оставляем её отдельно.
"""

from __future__ import annotations

import math
import random

from PIL import Image
import numpy as np

# ============================================================
# 🌊 КОНФИГУРАЦИЯ ВОЛНЫ
# ============================================================

WAVE_CONFIG: dict = {
    "grid_size": 5,
    "amplitude_x_range": (0.0, 4.0),
    "amplitude_y_range": (0.0, 5.0),
    "period_x_range": (30, 90),
    "period_y_range": (30, 90),
    "apply_probability": 0.80,
}


def _create_valid_mask(image: Image.Image, threshold: int = 8) -> Image.Image:
    """
    Создаёт бинарную маску: 255 для пикселей, которые не являются
    «пустыми» (чёрными/прозрачными), и 0 для артефактов на краях.

    Полностью vectorized через numpy — без Python-циклов по пикселям.
    """
    arr = np.asarray(image)

    if image.mode == "RGBA":
        # Пиксель валиден, если альфа > 0 И хотя бы один RGB-канал > threshold
        alpha = arr[:, :, 3]
        rgb = arr[:, :, :3]
        valid = (alpha > 0) & (np.any(rgb > threshold, axis=2))
    else:
        # Для RGB: просто проверяем, что хотя бы один канал > threshold
        valid = np.any(arr > threshold, axis=2)

    mask_arr = (valid.astype(np.uint8)) * 255
    return Image.fromarray(mask_arr, mode="L")


def apply_wave(
    image: Image.Image,
    rng: random.Random | None = None,
) -> Image.Image:
    """Mesh-warp с синусоидами по X и Y. Возвращает новое изображение."""
    r = rng or random
    w, h = image.size
    grid = WAVE_CONFIG["grid_size"]
    original = image.copy()  # Сохраняем оригинал для композитинга

    amp_x = r.uniform(*WAVE_CONFIG["amplitude_x_range"])
    amp_y = r.uniform(*WAVE_CONFIG["amplitude_y_range"])
    per_x = r.uniform(*WAVE_CONFIG["period_x_range"])
    per_y = r.uniform(*WAVE_CONFIG["period_y_range"])
    phase_x = r.uniform(0, 2 * math.pi)
    phase_y = r.uniform(0, 2 * math.pi)

    mesh = []

    def tp(px: float, py: float) -> tuple[float, float]:
        nx = px + amp_x * math.sin(2 * math.pi * py / per_x + phase_x)
        ny = py + amp_y * math.sin(2 * math.pi * px / per_y + phase_y)
        return nx, ny

    for x in range(0, w, grid):
        for y in range(0, h, grid):
            box = (x, y, x + grid, y + grid)
            x0, y0 = tp(x, y)
            x1, y1 = tp(x, y + grid)
            x2, y2 = tp(x + grid, y + grid)
            x3, y3 = tp(x + grid, y)
            mesh.append((box, (x0, y0, x1, y1, x2, y2, x3, y3)))

    # Применяем трансформацию
    warped = image.transform(
        image.size, Image.MESH, mesh, resample=Image.BICUBIC
    )

    # Создаём маску валидных пикселей и композитим поверх оригинала
    # чтобы убрать чёрные края
    mask = _create_valid_mask(warped)

    # Конвертируем original в RGBA для композитинга
    if original.mode != "RGBA":
        original = original.convert("RGBA")
    if warped.mode != "RGBA":
        warped = warped.convert("RGBA")

    # Накладываем warped на original через маску
    result = Image.composite(warped, original, mask)
    return result.convert("RGB")


def maybe_apply_wave(
    image: Image.Image,
    rng: random.Random | None = None,
) -> Image.Image:
    r = rng or random
    if r.random() < WAVE_CONFIG["apply_probability"]:
        return apply_wave(image, r)
    return image
