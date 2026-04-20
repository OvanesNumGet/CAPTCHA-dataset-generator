"""
Глобальная конфигурация датасета капч.

Здесь лежат ТОЛЬКО параметры, которые определяют «контракт» датасета —
размер итогового изображения, алфавит и порядок классов YOLO.
Случайные параметры генерации живут в других модулях в своих *_CONFIG.
"""

from __future__ import annotations

import string

# ============================================================
# 🎯 ОСНОВНАЯ КОНФИГУРАЦИЯ ДАТАСЕТА
# ============================================================

CAPTCHA_CONFIG: dict = {
    # Алфавит: цифры + латиница (верхний и нижний регистр)
    "charset": string.ascii_letters + string.digits,
    # Длина текста
    "min_length": 3,
    "max_length": 9,
    # Итоговый размер изображения (после letterbox)
    "width": 224,
    "height": 96,
    # Веса выбора типа символа в generate_random_text()
    "char_type_weights": {
        "upper": 0.45,
        "lower": 0.40,
        "digit": 0.15,
    },
}

# ============================================================
# 🧭 РАЗМЕЩЕНИЕ ДЕФОЛТНЫХ ДИРЕКТОРИЙ
# ============================================================

DEFAULT_FONTS_DIR = "fonts"
DEFAULT_BG_IMAGES_DIR = "backgrounds"  # опциональная папка с фото-фонами
DEFAULT_VAL_SPLIT = 0.1

TEST_SAMPLES_COUNT = 10
PROD_SAMPLES_COUNT = 5000

# ============================================================
# 🔢 КАРТА КЛАССОВ YOLO
#   0-9   → цифры
#   10-35 → A-Z
#   36-61 → a-z
# ============================================================


def _build_class_map() -> dict[str, int]:
    mapping: dict[str, int] = {}
    for i, d in enumerate(string.digits):
        mapping[d] = i
    for i, u in enumerate(string.ascii_uppercase, start=10):
        mapping[u] = i
    for i, l in enumerate(string.ascii_lowercase, start=36):
        mapping[l] = i
    return mapping


CLASS_ID_MAP: dict[str, int] = _build_class_map()
INV_CLASS_ID_MAP: dict[int, str] = {v: k for k, v in CLASS_ID_MAP.items()}
NUM_CLASSES: int = len(CLASS_ID_MAP)  # 62
