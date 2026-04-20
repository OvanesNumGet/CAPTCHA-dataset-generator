"""
Letterbox-ресайз: сохраняет пропорции исходного холста при подгонке под
фиксированный размер (width, height), добавляя рамки (padding).

Пересчитывает bbox, сохраняя их корректность в новой системе координат.
"""

from __future__ import annotations

import random

from PIL import Image
import numpy as np

# ============================================================
# 📦 КОНФИГУРАЦИЯ LETTERBOX
# ============================================================

LETTERBOX_CONFIG: dict = {
    # Если True — padding заливается средним цветом фона (выглядит естественно)
    "use_edge_color_padding": True,
    # Иначе — фиксированный цвет
    "fallback_padding_color": (128, 128, 128),
}


def letterbox_image_and_bboxes(
    image: Image.Image,
    target_size: tuple[int, int],
    bboxes_abs: list[tuple[float, float, float, float, str]] | None = None,
    rng: random.Random | None = None,
) -> tuple[Image.Image, list[tuple[float, float, float, float, str]]]:
    """
    image           — PIL RGB
    target_size     — (target_w, target_h)
    bboxes_abs      — список (x, y, w, h, char) в пикселях исходного image

    Возвращает (resized_image, new_bboxes_abs).
    """
    rng = rng or random
    tw, th = target_size
    iw, ih = image.size

    scale = min(tw / iw, th / ih)
    new_w = max(1, int(round(iw * scale)))
    new_h = max(1, int(round(ih * scale)))

    resized = image.resize((new_w, new_h), Image.BICUBIC)

    # Цвет заливки padding
    if LETTERBOX_CONFIG["use_edge_color_padding"]:
        arr = np.asarray(resized)
        # среднее по краям — хорошая аппроксимация фонового тона
        edges = np.concatenate(
            [arr[0], arr[-1], arr[:, 0], arr[:, -1]], axis=0
        )
        pad_color = tuple(int(v) for v in edges.mean(axis=0))
    else:
        pad_color = LETTERBOX_CONFIG["fallback_padding_color"]

    canvas = Image.new("RGB", (tw, th), pad_color)
    pad_x = (tw - new_w) // 2
    pad_y = (th - new_h) // 2
    canvas.paste(resized, (pad_x, pad_y))

    new_bboxes: list[tuple[float, float, float, float, str]] = []
    if bboxes_abs:
        for x, y, w, h, ch in bboxes_abs:
            nx = x * scale + pad_x
            ny = y * scale + pad_y
            nw = w * scale
            nh = h * scale
            # clip в пределах итогового размера
            nx = max(0.0, min(nx, tw - 1))
            ny = max(0.0, min(ny, th - 1))
            nw = max(1.0, min(nw, tw - nx))
            nh = max(1.0, min(nh, th - ny))
            new_bboxes.append((nx, ny, nw, nh, ch))

    return canvas, new_bboxes
