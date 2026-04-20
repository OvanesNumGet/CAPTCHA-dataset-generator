"""
captcha_gen
===========

Модульная библиотека для генерации датасета капч с YOLO-аннотациями.

Основные точки входа:
    from captcha_gen import CaptchaGenerator, generate_dataset
    from captcha_gen.cli import main
"""

from captcha_gen.clutter import CLUTTER_CONFIG, draw_clutter, punch_holes
from captcha_gen.config import (
    CAPTCHA_CONFIG,
    CLASS_ID_MAP,
    INV_CLASS_ID_MAP,
    NUM_CLASSES,
)
from captcha_gen.generator import CaptchaGenerator, generate_dataset
from captcha_gen.text import generate_random_text, sanitize_text
from captcha_gen.visualization import (
    build_visualizations,
    simulate_dataset,
    visualize_annotations,
)

__all__ = [
    "CAPTCHA_CONFIG",
    "CLASS_ID_MAP",
    "CLUTTER_CONFIG",
    "INV_CLASS_ID_MAP",
    "NUM_CLASSES",
    "CaptchaGenerator",
    "build_visualizations",
    "draw_clutter",
    "generate_dataset",
    "generate_random_text",
    "punch_holes",
    "sanitize_text",
    "simulate_dataset",
    "visualize_annotations",
]

__version__ = "2.1.0"
