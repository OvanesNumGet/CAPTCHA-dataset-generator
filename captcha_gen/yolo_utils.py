"""
Утилиты YOLO-разметки: нормализация, сериализация, конвертация.
"""

from __future__ import annotations

from captcha_gen.config import CLASS_ID_MAP


def bboxes_to_yolo(
    bboxes_abs: list[tuple[float, float, float, float, str]],
    img_w: int,
    img_h: int,
) -> tuple[
    list[tuple[float, float, float, float]],  # (xc, yc, w, h) normalized
    list[int],  # class ids
    list[str],  # отформатированные строки
]:
    """
    Переводит (x, y, w, h, char) в пикселях → YOLO-строки и parallel lists.

    Отфильтровывает боксы, у которых ширина/высота вышли из кадра.
    """
    norm: list[tuple[float, float, float, float]] = []
    class_ids: list[int] = []
    lines: list[str] = []

    for bx, by, bw, bh, ch in bboxes_abs:
        bx = max(0.0, min(bx, img_w - 1))
        by = max(0.0, min(by, img_h - 1))
        bw = min(bw, img_w - bx)
        bh = min(bh, img_h - by)
        if bw <= 0 or bh <= 0:
            continue

        x_center = (bx + bw / 2) / img_w
        y_center = (by + bh / 2) / img_h
        n_w = bw / img_w
        n_h = bh / img_h

        if ch not in CLASS_ID_MAP:
            continue
        cid = CLASS_ID_MAP[ch]

        norm.append((x_center, y_center, n_w, n_h))
        class_ids.append(cid)
        lines.append(
            f"{cid} {x_center:.6f} {y_center:.6f} {n_w:.6f} {n_h:.6f}"
        )

    return norm, class_ids, lines


def yolo_to_lines(
    yolo_bboxes: list[tuple[float, float, float, float]],
    class_ids: list[int],
) -> list[str]:
    out = []
    for (xc, yc, w, h), cid in zip(yolo_bboxes, class_ids, strict=False):
        out.append(f"{cid} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}")
    return out
