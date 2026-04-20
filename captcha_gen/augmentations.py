"""
Пайплайн аугментаций на базе Albumentations.

Поддерживает bbox-aware режим: если передать YOLO-bbox, они будут
корректно пересчитаны после ElasticTransform / Affine и отфильтрованы
при выпадении из кадра.

Если Albumentations не установлен — пайплайн деградирует в no-op, но
сама генерация капч продолжит работать (волна + шум + фон).
"""

from __future__ import annotations

import random
from typing import Any

import numpy as np

try:
    import albumentations as A

    _HAS_ALBU = True
except ImportError:  # pragma: no cover
    A = None  # type: ignore
    _HAS_ALBU = False

# ============================================================
# ⚗️ КОНФИГУРАЦИЯ АУГМЕНТАЦИЙ
# ============================================================

AUGMENTATION_CONFIG: dict = {
    "enabled": True,
    # Вероятность применить pipeline к одной капче
    "apply_probability": 0.70,
    # Индивидуальные вероятности каждой трансформации
    "gaussian_blur_p": 0.25,
    "motion_blur_p": 0.15,
    "median_blur_p": 0.08,
    "gauss_noise_p": 0.35,
    "iso_noise_p": 0.25,
    "coarse_dropout_p": 0.20,
    "elastic_p": 0.15,
    "grid_distortion_p": 0.12,
    "optical_distortion_p": 0.12,
    "color_jitter_p": 0.40,
    "clahe_p": 0.10,
    # Тонкая настройка шумов (по документации)
    "gauss_noise_std_range": (0.0, 0.10),
    "iso_noise_color_shift": (0.0, 0.05),
    "iso_noise_intensity": (0.0, 0.4),
    # Downscale (пикселизация) выпилен — превращал капчи в нечитаемые блоки.
    "jpeg_compression_p": 0.25,
    # Параметры трансформаций
    "gaussian_blur_limit": (0, 5),
    "motion_blur_limit": (0, 5),
    "median_blur_limit": (0, 5),
    "coarse_dropout": {
        "max_holes": 6,
        "max_height": 10,
        "max_width": 10,
        "min_holes": 1,
        "min_height": 3,
        "min_width": 3,
    },
    # Смягчённые искажения: меньше «резиновых» букв
    "elastic": {"alpha": 1, "sigma": 50, "alpha_affine": 5},
    "grid_distortion": {"num_steps": 5, "distort_limit": 0.15},
    "optical_distortion": {"distort_limit": 0.15, "shift_limit": 0.04},
    "color_jitter": {
        "brightness": 0.2,
        "contrast": 0.2,
        "saturation": 0.2,
        "hue": 0.1,
    },
    "jpeg_quality": (55, 95),
}


# ============================================================
# 🏗 СБОРКА ПАЙПЛАЙНА
# ============================================================


def build_pipeline(with_bboxes: bool = False) -> Any:
    """
    Возвращает скомпилированный Albumentations Compose.
    Если Albumentations не установлен — возвращает no-op объект.
    """
    if not (_HAS_ALBU and AUGMENTATION_CONFIG["enabled"]):
        return _NoOpPipeline()

    cfg = AUGMENTATION_CONFIG

    transforms = [
        A.OneOf(
            [
                A.GaussianBlur(blur_limit=cfg["gaussian_blur_limit"], p=1.0),
                A.MotionBlur(blur_limit=cfg["motion_blur_limit"], p=1.0),
                A.MedianBlur(blur_limit=cfg["median_blur_limit"], p=1.0),
            ],
            p=max(
                cfg["gaussian_blur_p"],
                cfg["motion_blur_p"],
                cfg["median_blur_p"],
            ),
        ),
        A.OneOf(
            [
                A.GaussNoise(
                    std_range=cfg["gauss_noise_std_range"],
                    per_channel=True,
                    p=1.0,
                ),
                A.ISONoise(
                    color_shift=cfg["iso_noise_color_shift"],
                    intensity=cfg["iso_noise_intensity"],
                    p=1.0,
                ),
            ],
            p=max(cfg["gauss_noise_p"], cfg["iso_noise_p"]),
        ),
        A.OneOf(
            [
                A.ElasticTransform(**cfg["elastic"], p=1.0),
                A.GridDistortion(**cfg["grid_distortion"], p=1.0),
                A.OpticalDistortion(**cfg["optical_distortion"], p=1.0),
            ],
            p=max(
                cfg["elastic_p"],
                cfg["grid_distortion_p"],
                cfg["optical_distortion_p"],
            ),
        ),
        A.CoarseDropout(**cfg["coarse_dropout"], p=cfg["coarse_dropout_p"]),
        A.ColorJitter(**cfg["color_jitter"], p=cfg["color_jitter_p"]),
        A.CLAHE(p=cfg["clahe_p"]),
        A.ImageCompression(
            quality_lower=cfg["jpeg_quality"][0],
            quality_upper=cfg["jpeg_quality"][1],
            p=cfg["jpeg_compression_p"],
        ),
    ]

    if with_bboxes:
        return A.Compose(
            transforms,
            bbox_params=A.BboxParams(
                format="yolo",
                label_fields=["class_labels"],
                min_visibility=0.25,
            ),
        )

    return A.Compose(transforms)


class _NoOpPipeline:
    """Заглушка, если Albumentations не установлен."""

    def __call__(self, **kwargs):
        return kwargs


# ============================================================
# 🚪 ПРИМЕНЕНИЕ
# ============================================================


def apply_augmentations(
    image_rgb: np.ndarray,
    yolo_bboxes: list[tuple[float, float, float, float]] | None = None,
    class_labels: list[int] | None = None,
    rng: random.Random | None = None,
) -> tuple[np.ndarray, list[tuple[float, float, float, float]], list[int]]:
    """
    Применяет Albumentations pipeline.

    yolo_bboxes — список (xc, yc, w, h) в относительных координатах (0..1).
    class_labels — список int той же длины.
    """
    r = rng or random
    if r.random() > AUGMENTATION_CONFIG["apply_probability"]:
        return image_rgb, yolo_bboxes or [], class_labels or []

    pipeline = build_pipeline(with_bboxes=bool(yolo_bboxes))

    kwargs = {"image": image_rgb}
    if yolo_bboxes:
        kwargs["bboxes"] = yolo_bboxes
        kwargs["class_labels"] = class_labels or []

    result = pipeline(**kwargs)
    new_image = result["image"]
    new_bboxes = result.get("bboxes", yolo_bboxes or [])
    new_labels = result.get("class_labels", class_labels or [])
    return new_image, list(new_bboxes), list(new_labels)
