"""
Мусорные элементы поверх/под капчей:
  • clutter shapes — линии, круги, прямоугольники, полигоны, дуги (контуры);
  • punch holes    — маленькие «дырки» произвольной формы, имитирующие
                     порчу изображения (в дополнение к CoarseDropout).

Философия:
  • ~60% контуров рисуются цветом текста (чтобы сливались с символами
    и реально мешали сегментации), остальные — случайным цветом.
  • Толщина и размер каждого элемента — независимы и случайны.
  • Дырки — маленькие, но их может быть много; они аккуратные и
    НЕ превращают капчу в кашу (есть жёсткие верхние границы).
"""

from __future__ import annotations

import math
import random

from PIL import Image, ImageDraw

# ============================================================
# 🧩 КОНФИГУРАЦИЯ МУСОРА
# ============================================================

CLUTTER_CONFIG: dict = {
    # ---------------- SHAPES (контуры) ----------------
    # Общая вероятность вообще что-то нарисовать
    "apply_probability": 0.70,
    # Сколько мусорных элементов рисовать за раз
    "count_range": (0, 5),
    # Доля элементов, раскрашенных в цвет текста (остальные — случайные)
    "text_color_probability": 0.60,
    # Толщина контура (пиксели)
    "thickness_range": (1, 3),
    # Вероятности для каждого типа (нормализуются)
    "shape_weights": {
        "line": 0.40,
        "polyline": 0.20,
        "circle": 0.15,
        "rectangle": 0.10,
        "polygon": 0.08,
        "arc": 0.07,
    },
    # Параметры конкретных фигур
    "line_length_frac_range": (0.0, 1.15),  # относительно max(w,h)
    "polyline_segments_range": (0, 5),
    "circle_radius_frac_range": (0.0, 0.45),  # относительно min(w,h)
    "rect_size_frac_range": (0.0, 0.7),
    "polygon_vertices_range": (1, 6),
    "polygon_radius_frac_range": (0.0, 0.35),
    "arc_radius_frac_range": (0.0, 0.5),
    # ---------------- PUNCH HOLES ----------------
    # Вероятность вообще применить дырки
    "holes_apply_probability": 0.40,
    # Количество дырок
    "holes_count_range": (0, 14),
    # Размер одной дырки в пикселях (radius-like).
    # Держим маленьким, иначе капча превращается в решето.
    "hole_radius_range": (0, 4),
    # Шанс, что дырка будет не круглой, а «кляксой» из нескольких точек
    "hole_blob_probability": 0.35,
    # Доля дырок, залитых цветом фона (остальные — белые/чёрные случайные).
    # В 100% «цвета фона» смотрится натуральнее, чем явный белый.
    "hole_use_bg_color_probability": 0.85,
}


# ============================================================
# 🎨 ВСПОМОГАТЕЛЬНОЕ
# ============================================================


def _pick_color(
    text_color: tuple[int, int, int, int] | tuple[int, int, int],
    rng: random.Random,
) -> tuple[int, int, int]:
    """Случайный цвет для одного элемента (чаще всего — цвет текста)."""
    if rng.random() < CLUTTER_CONFIG["text_color_probability"]:
        return tuple(text_color[:3])  # type: ignore[return-value]
    return (rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255))


def _rand_thickness(rng: random.Random) -> int:
    return rng.randint(*CLUTTER_CONFIG["thickness_range"])


def _rand_point(w: int, h: int, rng: random.Random) -> tuple[int, int]:
    # Разрешаем немного выходить за края — линии смотрятся естественнее
    margin = -10
    return (
        rng.randint(margin, w - 1 - margin),
        rng.randint(margin, h - 1 - margin),
    )


# ============================================================
# ✏️ ОТДЕЛЬНЫЕ ФИГУРЫ
# ============================================================


def _draw_line(draw: ImageDraw.ImageDraw, w: int, h: int, color, rng):
    x1, y1 = _rand_point(w, h, rng)
    angle = rng.uniform(0, 2 * math.pi)
    length_frac = rng.uniform(*CLUTTER_CONFIG["line_length_frac_range"])
    length = length_frac * max(w, h)
    x2 = int(x1 + math.cos(angle) * length)
    y2 = int(y1 + math.sin(angle) * length)
    draw.line([(x1, y1), (x2, y2)], fill=color, width=_rand_thickness(rng))


def _draw_polyline(draw: ImageDraw.ImageDraw, w: int, h: int, color, rng):
    n = rng.randint(*CLUTTER_CONFIG["polyline_segments_range"])
    points = [_rand_point(w, h, rng) for _ in range(n + 1)]
    draw.line(points, fill=color, width=_rand_thickness(rng), joint="curve")


def _draw_circle(draw: ImageDraw.ImageDraw, w: int, h: int, color, rng):
    cx, cy = _rand_point(w, h, rng)
    r = int(
        rng.uniform(*CLUTTER_CONFIG["circle_radius_frac_range"]) * min(w, h)
    )
    bbox = [cx - r, cy - r, cx + r, cy + r]
    draw.ellipse(bbox, outline=color, width=_rand_thickness(rng))


def _draw_rectangle(draw: ImageDraw.ImageDraw, w: int, h: int, color, rng):
    cx, cy = _rand_point(w, h, rng)
    rw = int(rng.uniform(*CLUTTER_CONFIG["rect_size_frac_range"]) * w)
    rh = int(rng.uniform(*CLUTTER_CONFIG["rect_size_frac_range"]) * h)
    bbox = [cx - rw // 2, cy - rh // 2, cx + rw // 2, cy + rh // 2]
    draw.rectangle(bbox, outline=color, width=_rand_thickness(rng))


def _draw_polygon(draw: ImageDraw.ImageDraw, w: int, h: int, color, rng):
    n = rng.randint(*CLUTTER_CONFIG["polygon_vertices_range"])
    cx, cy = _rand_point(w, h, rng)
    r = int(
        rng.uniform(*CLUTTER_CONFIG["polygon_radius_frac_range"]) * min(w, h)
    )
    start_angle = rng.uniform(0, 2 * math.pi)
    points = []
    for i in range(n):
        a = start_angle + i * 2 * math.pi / n + rng.uniform(-0.3, 0.3)
        rr = r * rng.uniform(0.6, 1.2)
        points.append((int(cx + math.cos(a) * rr), int(cy + math.sin(a) * rr)))
    # «Контур» полигона: рисуем линиями, а не fill
    closed = points + [points[0]]
    draw.line(closed, fill=color, width=_rand_thickness(rng), joint="curve")


def _draw_arc(draw: ImageDraw.ImageDraw, w: int, h: int, color, rng):
    cx, cy = _rand_point(w, h, rng)
    r = int(rng.uniform(*CLUTTER_CONFIG["arc_radius_frac_range"]) * min(w, h))
    bbox = [cx - r, cy - r, cx + r, cy + r]
    start = rng.randint(0, 359)
    end = start + rng.randint(40, 300)
    draw.arc(
        bbox, start=start, end=end, fill=color, width=_rand_thickness(rng)
    )


_SHAPE_DISPATCH = {
    "line": _draw_line,
    "polyline": _draw_polyline,
    "circle": _draw_circle,
    "rectangle": _draw_rectangle,
    "polygon": _draw_polygon,
    "arc": _draw_arc,
}


# ============================================================
# 🚪 ПУБЛИЧНОЕ API: CLUTTER SHAPES
# ============================================================


def draw_clutter(
    image: Image.Image,
    text_color: tuple,
    rng: random.Random | None = None,
) -> Image.Image:
    """
    Дорисовывает поверх изображения случайные «мусорные» контуры.
    Работает с RGB и RGBA.
    """
    r = rng or random
    if r.random() >= CLUTTER_CONFIG["apply_probability"]:
        return image

    mode = image.mode
    if mode not in ("RGB", "RGBA"):
        image = image.convert("RGB")
        mode = "RGB"

    # Рисуем в копии, чтобы не портить исходник
    work = image.copy()
    draw = ImageDraw.Draw(work)

    w, h = work.size
    count = r.randint(*CLUTTER_CONFIG["count_range"])

    shape_names = list(CLUTTER_CONFIG["shape_weights"].keys())
    shape_probs = list(CLUTTER_CONFIG["shape_weights"].values())

    for _ in range(count):
        shape = r.choices(shape_names, weights=shape_probs)[0]
        color = _pick_color(text_color, r)
        _SHAPE_DISPATCH[shape](draw, w, h, color, r)

    return work


# ============================================================
# 🕳 PUNCH HOLES — маленькие дырки по всему изображению
# ============================================================


def _sample_bg_color(
    image: Image.Image, rng: random.Random
) -> tuple[int, int, int]:
    """Берём среднее по краям — аппроксимация цвета фона."""
    w, h = image.size
    rgb = image.convert("RGB")
    # несколько случайных точек с края
    samples = []
    for _ in range(12):
        side = rng.choice(["top", "bottom", "left", "right"])
        if side == "top":
            samples.append(rgb.getpixel((rng.randint(0, w - 1), 0)))
        elif side == "bottom":
            samples.append(rgb.getpixel((rng.randint(0, w - 1), h - 1)))
        elif side == "left":
            samples.append(rgb.getpixel((0, rng.randint(0, h - 1))))
        else:
            samples.append(rgb.getpixel((w - 1, rng.randint(0, h - 1))))
    rr = sum(s[0] for s in samples) // len(samples)
    gg = sum(s[1] for s in samples) // len(samples)
    bb = sum(s[2] for s in samples) // len(samples)
    return (rr, gg, bb)


def _draw_single_hole(
    draw: ImageDraw.ImageDraw,
    w: int,
    h: int,
    color: tuple[int, int, int],
    rng: random.Random,
) -> None:
    cx = rng.randint(0, w - 1)
    cy = rng.randint(0, h - 1)
    radius = rng.randint(*CLUTTER_CONFIG["hole_radius_range"])

    if rng.random() < CLUTTER_CONFIG["hole_blob_probability"]:
        # «Клякса»: 2–4 смещённых круга
        blobs = rng.randint(2, 4)
        for _ in range(blobs):
            ox = cx + rng.randint(-radius, radius)
            oy = cy + rng.randint(-radius, radius)
            rr = max(1, radius + rng.randint(-1, 1))
            draw.ellipse([ox - rr, oy - rr, ox + rr, oy + rr], fill=color)
    else:
        draw.ellipse(
            [cx - radius, cy - radius, cx + radius, cy + radius],
            fill=color,
        )


def punch_holes(
    image: Image.Image,
    rng: random.Random | None = None,
) -> Image.Image:
    """
    Добавляет маленькие случайные дырки (разрывы) по всему изображению.
    Дырки заливаются цветом фона (чаще) или случайным светлым/тёмным.
    """
    r = rng or random
    if r.random() >= CLUTTER_CONFIG["holes_apply_probability"]:
        return image

    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGB")

    work = image.copy()
    draw = ImageDraw.Draw(work)

    w, h = work.size
    count = r.randint(*CLUTTER_CONFIG["holes_count_range"])

    bg_color = _sample_bg_color(work, r)

    for _ in range(count):
        if r.random() < CLUTTER_CONFIG["hole_use_bg_color_probability"]:
            color = bg_color
        else:
            # случайный очень светлый или очень тёмный
            if r.random() < 0.5:
                color = (
                    r.randint(220, 255),
                    r.randint(220, 255),
                    r.randint(220, 255),
                )
            else:
                color = (
                    r.randint(0, 35),
                    r.randint(0, 35),
                    r.randint(0, 35),
                )
        _draw_single_hole(draw, w, h, color, r)

    return work
