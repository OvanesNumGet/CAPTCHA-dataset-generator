"""
Командный интерфейс captcha_gen.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

from captcha_gen.config import (
    DEFAULT_FONTS_DIR,
    DEFAULT_VAL_SPLIT,
    PROD_SAMPLES_COUNT,
    TEST_SAMPLES_COUNT,
)
from captcha_gen.generator import generate_dataset
from captcha_gen.visualization import (
    build_visualizations,
    simulate_dataset,
    visualize_annotations,
)

# ============================================================
# 🧭 КОМАНДЫ
# ============================================================


def cmd_generate(args: argparse.Namespace) -> None:
    out = (
        Path(args.output)
        if args.output
        else Path(
            "dataset/test_samples" if args.mode == "test" else "dataset/train"
        )
    )

    total = (
        args.count
        if args.count
        else (
            TEST_SAMPLES_COUNT if args.mode == "test" else PROD_SAMPLES_COUNT
        )
    )

    if args.mode == "test" and args.clean and out.exists():
        for p in out.glob("*"):
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                shutil.rmtree(p)

    generate_dataset(
        total=total,
        output_dir=out,
        mode=args.mode,
        yolo=args.yolo,
        split=args.split if args.split is not None else DEFAULT_VAL_SPLIT,
        fonts_dir=args.fonts_dir,
        seed=args.seed,
    )

    # Для test+YOLO сразу рисуем визуализацию bbox
    if args.mode == "test" and args.yolo:
        img_dir = out / "images"
        lbl_dir = out / "labels"
        vis_dir = out / "visual"
        visualize_annotations(img_dir, lbl_dir, vis_dir)


def cmd_visualize(args: argparse.Namespace) -> None:
    out = Path(args.output) if args.output else None
    print(f"📊 Симуляция {args.samples:,} образцов…")
    stats = simulate_dataset(args.samples)
    print("🎨 Построение дашборда…")
    build_visualizations(stats, out, show=not args.no_show)


def cmd_visualize_boxes(args: argparse.Namespace) -> None:
    visualize_annotations(
        Path(args.images), Path(args.labels), Path(args.output)
    )


# ============================================================
# 🛠 PARSER
# ============================================================


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="generate_dataset",
        description="🔐 Генератор датасета капч + визуализация параметров",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # generate
    p = sub.add_parser("generate", help="Сгенерировать изображения капч")
    p.add_argument("--mode", choices=["test", "prod"], default="test")
    p.add_argument("--count", type=int, default=None, metavar="N")
    p.add_argument("--output", metavar="DIR", default=None)
    p.add_argument(
        "--split",
        type=float,
        default=None,
        metavar="FLOAT",
        help=f"Доля val (только для prod). По умолчанию {DEFAULT_VAL_SPLIT}",
    )
    p.add_argument(
        "--clean",
        action="store_true",
        help="Очистить output (только для test)",
    )
    p.add_argument(
        "--yolo", action="store_true", help="Сохранять YOLO-аннотации"
    )
    p.add_argument(
        "--fonts-dir",
        default=DEFAULT_FONTS_DIR,
        metavar="DIR",
        help=f"Папка со шрифтами (default: {DEFAULT_FONTS_DIR})",
    )
    p.add_argument(
        "--seed", type=int, default=None, help="Seed для воспроизводимости"
    )
    p.set_defaults(func=cmd_generate)

    # visualize
    p = sub.add_parser("visualize", help="Построить дашборд распределений")
    p.add_argument("--samples", type=int, default=5000, metavar="N")
    p.add_argument("--output", metavar="FILE", default="stats.png")
    p.add_argument("--no-show", action="store_true")
    p.set_defaults(func=cmd_visualize)

    # visualize-boxes
    p = sub.add_parser("visualize-boxes", help="Нарисовать bbox из YOLO .txt")
    p.add_argument("--images", required=True, metavar="DIR")
    p.add_argument("--labels", required=True, metavar="DIR")
    p.add_argument("--output", required=True, metavar="DIR")
    p.set_defaults(func=cmd_visualize_boxes)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
