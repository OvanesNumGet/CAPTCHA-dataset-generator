"""
Низкоуровневый рендеринг символов капчи.

В отличие от старой версии, тут:
  • шрифт выбирается per-character (в 30% случаев);
  • stroke_width варьируется 1..5;
  • is_filled — редкий и только для «жирных» шрифтов;
  • текст может быть уменьшен/увеличен (с гарантией полного попадания);
  • возвращается холст БЕЗ letterbox — это делает generator.py отдельно.
"""

from __future__ import annotations

import random

from PIL import Image, ImageDraw, ImageFont

from captcha_gen.fonts import random_font

# ============================================================
# ✏️ КОНФИГУРАЦИЯ РЕНДЕРЕРА
# ============================================================

RENDER_CONFIG: dict = {
    # Доля «залитых» (is_filled=True) символов. Снижено — залитые тонкие
    # шрифты выглядят нечитаемо, а вместе с волной вообще превращаются в кляксу.
    "filled_probability": 0.25,
    # Минимальная «плотность» глифа (доля непрозрачных пикселей в bbox),
    # при которой шрифт можно считать достаточно жирным для filled-режима.
    # Иначе filled отключается принудительно.
    "filled_min_glyph_density": 0.28,
    # Толщина обводки (включительно)
    "stroke_width_range": (1, 4),
    "stroke_width_filled_range": (0, 2),
    # Случайный угол поворота каждого символа
    "rotation_range_deg": (-35, 35),
    # Горизонтальный overlap соседних символов (доля ширины), смягчено
    "char_overlap_range": (-0.20, 0.30),
    # Вертикальный «jitter» каждого символа (в пикселях внутри строки), смягчено
    "line_vertical_jitter": 6,
    # Вертикальное перекрытие двух строк, смягчено
    "line_vertical_overlap_range": (-6, 12),
    # Шанс, что шрифт для каждого символа выбирается заново (а не один на всю капчу)
    "per_char_font_probability": 0.40,
    # Шанс, что размер шрифта жонглируется между символами
    "per_char_size_jitter_probability": 0.55,
    "per_char_size_jitter_range": (-4, 4),
    # Масштаб всей композиции текста (min, max).
    # Нижнюю границу подняли, чтобы буквы не были слишком мелкими.
    "text_scale_range": (0.75, 1.05),
    # «Безопасные» отступы от краёв канваса (пиксели), в которые текст не залезает
    "canvas_margin": 6,
    # Разделение на 1 или 2 строки (если длины достаточно)
    "two_lines_probability": 0.55,
    "min_len_for_two_lines": 4,
}


# ============================================================
# 🔍 АНАЛИЗ ШРИФТА: поддерживает ли он filled-режим
# ============================================================

# Кеш, чтобы не пересчитывать плотность для одного и того же шрифта.
_FILLED_SUPPORT_CACHE: dict[tuple[str, int], bool] = {}


def _font_supports_filled(font: ImageFont.FreeTypeFont) -> bool:
    """
    Эвристика: считаем долю непрозрачных пикселей в маске глифа 'M'
    при текущем размере шрифта. Если шрифт тонкий (плотность низкая) —
    залитый режим выглядит ужасно (превращается в кашу под аугментациями),
    поэтому отключаем его.
    """
    path = getattr(font, "path", None)
    size = getattr(font, "size", 0)
    key = (str(path), int(size))
    if key in _FILLED_SUPPORT_CACHE:
        return _FILLED_SUPPORT_CACHE[key]

    try:
        mask = font.getmask("M")
        w, h = mask.size
        if w == 0 or h == 0:
            _FILLED_SUPPORT_CACHE[key] = False
            return False
        # mask — это 'L' изображение: считаем долю ненулевых пикселей
        total = w * h
        non_zero = sum(1 for px in mask if px > 32)
        density = non_zero / total if total else 0.0
        ok = density >= RENDER_CONFIG["filled_min_glyph_density"]
    except Exception:
        ok = True  # не удалось проверить — не запрещаем

    _FILLED_SUPPORT_CACHE[key] = ok
    return ok


# ============================================================
# 🧱 ОТРИСОВКА ОДНОГО СИМВОЛА
# ============================================================


def _render_char(
    char: str,
    font: ImageFont.FreeTypeFont,
    stroke_width: int,
    text_color: tuple,
    bg_color: tuple,
    is_filled: bool,
    rng: random.Random,
) -> Image.Image:
    bbox = font.getbbox(char)
    left, top, right, bottom = bbox
    cw = max(right - left, 10)
    ch = max(bottom - top, 10)

    pad = 30
    img = Image.new("RGBA", (cw + pad * 2, ch + pad * 2), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)

    # Если запросили filled, но шрифт слишком тонкий — падаем в outline
    effective_filled = is_filled and _font_supports_filled(font)

    # Если символ залит (filled), отключаем обводку (stroke)
    current_stroke_width = (
        random.randint(*RENDER_CONFIG["stroke_width_filled_range"])
        if effective_filled
        else stroke_width
    )

    x = pad - left
    y = pad - top
    draw.text(
        (x, y),
        char,
        font=font,
        fill=text_color if effective_filled else bg_color,
        stroke_width=current_stroke_width,
        stroke_fill=text_color,
    )

    angle = rng.uniform(*RENDER_CONFIG["rotation_range_deg"])
    img = img.rotate(angle, resample=Image.BICUBIC, expand=True)

    crop = img.getbbox()
    if crop:
        img = img.crop(crop)
    return img


# ============================================================
# ✂️ ОТРИСОВКА СТРОКИ
# ============================================================


def _render_line(
    text: str,
    base_font: ImageFont.FreeTypeFont,
    base_size: int,
    stroke_width: int,
    text_color: tuple,
    bg_color: tuple,
    is_filled: bool,
    fonts_dir: str,
    rng: random.Random,
) -> tuple[Image.Image, list[tuple[float, float, float, float, str]]]:
    char_images: list[Image.Image] = []

    for ch in text:
        # Per-char font?
        if rng.random() < RENDER_CONFIG["per_char_font_probability"]:
            size = base_size
            if (
                rng.random()
                < RENDER_CONFIG["per_char_size_jitter_probability"]
            ):
                size = max(
                    10,
                    size
                    + rng.randint(
                        *RENDER_CONFIG["per_char_size_jitter_range"]
                    ),
                )
            font = random_font(rng=rng, size=size, fonts_dir=fonts_dir)
        else:
            font = base_font

        char_images.append(
            _render_char(
                ch, font, stroke_width, text_color, bg_color, is_filled, rng
            )
        )

    if not char_images:
        return Image.new("RGBA", (1, 1), (255, 255, 255, 0)), []

    # Предварительно рассчитываем координаты X, так как отрицательный overlap
    # увеличивает итоговую ширину строки сверх суммы ширин символов.
    x_positions = []
    current_x = 0
    for img in char_images:
        x_positions.append(current_x)
        overlap = int(
            img.width * rng.uniform(*RENDER_CONFIG["char_overlap_range"])
        )
        current_x += img.width - overlap

    # Холст должен вмещать самую дальнюю правую границу последнего символа
    total_w = max(
        x + img.width for x, img in zip(x_positions, char_images, strict=False)
    )
    max_h = max(img.height for img in char_images)
    jitter = RENDER_CONFIG["line_vertical_jitter"]

    line_img = Image.new(
        "RGBA", (total_w, max_h + 2 * jitter), (255, 255, 255, 0)
    )

    raw_bboxes: list[tuple[float, float, float, float, str]] = []
    for idx, (img, x_pos) in enumerate(
        zip(char_images, x_positions, strict=False)
    ):
        y_offset = rng.randint(
            0, max(0, line_img.height - img.height - jitter // 2)
        )
        line_img.alpha_composite(img, (x_pos, y_offset))
        raw_bboxes.append((
            x_pos,
            y_offset,
            img.width,
            img.height,
            text[idx],
        ))

    crop = line_img.getbbox()
    if crop:
        cl, ct, cr, cb = crop
        line_img = line_img.crop(crop)
        adjusted = []
        for x, y, w, h, ch in raw_bboxes:
            if x + w > cl and x < cr and y + h > ct and y < cb:
                nx = max(0, x - cl)
                ny = max(0, y - ct)
                nw = min(w, cr - cl - nx)
                nh = min(h, cb - ct - ny)
                adjusted.append((nx, ny, nw, nh, ch))
        raw_bboxes = adjusted

    return line_img, raw_bboxes


# ============================================================
# 🖼 ПОЛНЫЙ ТЕКСТОВЫЙ КОМПОЗИТ
# ============================================================


def render_text_composite(
    text: str,
    canvas_size: tuple[int, int],
    text_color: tuple,
    bg_color: tuple,
    fonts_dir: str,
    rng: random.Random | None = None,
) -> tuple[Image.Image, list[tuple[float, float, float, float, str]]]:
    """
    Возвращает RGBA-картинку текстовой композиции и bbox-ы символов
    (в координатах самой композиции — ДО letterbox).
    """
    r = rng or random
    stroke_width = r.randint(*RENDER_CONFIG["stroke_width_range"])
    is_filled = r.random() < RENDER_CONFIG["filled_probability"]

    base_font = random_font(rng=r, fonts_dir=fonts_dir)
    base_size = base_font.size if hasattr(base_font, "size") else 55

    # Разделение на 1 или 2 строки
    if (
        len(text) >= RENDER_CONFIG["min_len_for_two_lines"]
        and r.random() < RENDER_CONFIG["two_lines_probability"]
    ):
        mid = len(text) // 2
        if len(text) % 2 != 0:
            mid += r.choice([0, 1])
        mid = max(1, min(mid, len(text) - 1))
        lines = [text[:mid], text[mid:]]
    else:
        lines = [text]

    line_imgs: list[Image.Image] = []
    line_bboxes: list[list[tuple[float, float, float, float, str]]] = []
    for line_text in lines:
        img, boxes = _render_line(
            line_text,
            base_font,
            base_size,
            stroke_width,
            text_color,
            bg_color,
            is_filled,
            fonts_dir,
            r,
        )
        line_imgs.append(img)
        line_bboxes.append(boxes)

    # Компонуем строки
    v_overlap = r.randint(*RENDER_CONFIG["line_vertical_overlap_range"])
    total_w = max(img.width for img in line_imgs) + 40
    total_h = sum(img.height for img in line_imgs) - v_overlap * (
        len(line_imgs) - 1
    )
    total_h = max(1, total_h)

    composite = Image.new("RGBA", (total_w, total_h), (255, 255, 255, 0))
    all_bboxes: list[tuple[float, float, float, float, str]] = []

    cur_y = 0
    for img, boxes in zip(line_imgs, line_bboxes, strict=False):
        x_line = (total_w - img.width) // 2 + r.randint(-15, 15)
        composite.alpha_composite(img, (x_line, cur_y))
        for x, y, w, h, ch in boxes:
            all_bboxes.append((x + x_line, y + cur_y, w, h, ch))
        cur_y += img.height - v_overlap

    # Переводим в рабочий канвас с учётом масштаба текста
    cw, ch = canvas_size
    margin = RENDER_CONFIG["canvas_margin"]
    max_w = cw - 2 * margin
    max_h = ch - 2 * margin

    # Сначала принудительно fit (если вылезает), потом умножаем на случайный scale ≤ 1
    fit_scale = min(max_w / composite.width, max_h / composite.height, 1.0)
    rand_scale = r.uniform(*RENDER_CONFIG["text_scale_range"])
    scale = fit_scale * rand_scale
    # Гарантия: итоговый текст ≤ поля канваса
    scale = min(scale, max_w / composite.width, max_h / composite.height)
    if scale <= 0:
        scale = fit_scale

    new_w = max(1, int(composite.width * scale))
    new_h = max(1, int(composite.height * scale))
    composite = composite.resize((new_w, new_h), Image.BICUBIC)
    all_bboxes = [
        (x * scale, y * scale, w * scale, h * scale, ch_)
        for x, y, w, h, ch_ in all_bboxes
    ]

    # Размещение на канвасе (RGBA, прозрачное — наложим поверх фона в generator.py)
    canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    max_off_x = cw - new_w - margin
    max_off_y = ch - new_h - margin
    off_x = r.randint(margin, max(margin, max_off_x))
    off_y = r.randint(margin, max(margin, max_off_y))
    canvas.alpha_composite(composite, (off_x, off_y))

    shifted = [
        (x + off_x, y + off_y, w, h, ch_) for x, y, w, h, ch_ in all_bboxes
    ]
    return canvas, shifted
