"""
Визуализация:
  • simulate_dataset + build_visualizations — дашборд распределений;
  • visualize_annotations — рисование YOLO bbox поверх готовых картинок.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import random
import string

from PIL import Image, ImageDraw, ImageFont

from captcha_gen.augmentations import AUGMENTATION_CONFIG
from captcha_gen.backgrounds import BACKGROUND_CONFIG
from captcha_gen.colors import COLOR_CONFIG
from captcha_gen.config import CAPTCHA_CONFIG, INV_CLASS_ID_MAP
from captcha_gen.distortions import WAVE_CONFIG
from captcha_gen.fonts import FONT_CONFIG, discover_fonts
from captcha_gen.renderer import RENDER_CONFIG
from captcha_gen.text import generate_random_text

# ============================================================
# 📊 СИМУЛЯЦИЯ СТАТИСТИКИ
# ============================================================


def simulate_dataset(n: int) -> dict:
    lengths: list[int] = []
    char_counts: Counter = Counter()
    type_counts: Counter = Counter()
    stroke_widths: list[int] = []
    angles_all: list[float] = []
    overlaps: list[float] = []
    filled_counts: Counter = Counter()
    v_overlaps: list[int] = []
    amplitude_xs: list[float] = []
    amplitude_ys: list[float] = []
    distort_counts: Counter = Counter()
    grayscale_counts: Counter = Counter()
    bg_counts: Counter = Counter()
    empty_counts: Counter = Counter()

    uppers = set(string.ascii_uppercase)
    lowers = set(string.ascii_lowercase)
    digits_set = set(string.digits)

    bg_types = list(BACKGROUND_CONFIG["type_weights"].keys())
    bg_weights = list(BACKGROUND_CONFIG["type_weights"].values())

    for _ in range(n):
        # пустая капча?
        if random.random() < 0.03:
            empty_counts["Empty"] += 1
            continue
        empty_counts["WithText"] += 1

        text = generate_random_text()
        lengths.append(len(text))

        for ch in text:
            char_counts[ch] += 1
            if ch in uppers:
                type_counts["Uppercase"] += 1
            elif ch in lowers:
                type_counts["Lowercase"] += 1
            elif ch in digits_set:
                type_counts["Digit"] += 1

        stroke_widths.append(
            random.randint(*RENDER_CONFIG["stroke_width_range"])
        )
        for _ in text:
            angles_all.append(
                random.uniform(*RENDER_CONFIG["rotation_range_deg"])
            )
            overlaps.append(
                random.uniform(*RENDER_CONFIG["char_overlap_range"]) * 100
            )

        filled_counts[
            "Filled"
            if random.random() < RENDER_CONFIG["filled_probability"]
            else "Outline"
        ] += 1
        v_overlaps.append(
            random.randint(*RENDER_CONFIG["line_vertical_overlap_range"])
        )

        has_distort = random.random() < WAVE_CONFIG["apply_probability"]
        distort_counts["Warped" if has_distort else "Clean"] += 1
        amplitude_xs.append(
            random.uniform(*WAVE_CONFIG["amplitude_x_range"])
            if has_distort
            else 0
        )
        amplitude_ys.append(
            random.uniform(*WAVE_CONFIG["amplitude_y_range"])
            if has_distort
            else 0
        )

        grayscale_counts[
            "Grayscale"
            if random.random() < COLOR_CONFIG["grayscale_probability"]
            else "Color"
        ] += 1
        bg_counts[random.choices(bg_types, weights=bg_weights)[0]] += 1

    return {
        "n": n,
        "lengths": lengths,
        "char_counts": char_counts,
        "type_counts": type_counts,
        "stroke_widths": stroke_widths,
        "angles_all": angles_all,
        "overlaps": overlaps,
        "filled_counts": filled_counts,
        "v_overlaps": v_overlaps,
        "amplitude_xs": amplitude_xs,
        "amplitude_ys": amplitude_ys,
        "distort_counts": distort_counts,
        "grayscale_counts": grayscale_counts,
        "bg_counts": bg_counts,
        "empty_counts": empty_counts,
    }


# ============================================================
# 📈 ДАШБОРД
# ============================================================


def build_visualizations(
    stats: dict, output_path: Path | None, show: bool = False
) -> None:
    try:
        import matplotlib

        if not show:
            matplotlib.use("Agg")
        import matplotlib.gridspec as gridspec
        from matplotlib.patches import Patch
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("❌ matplotlib не установлен. `pip install matplotlib numpy`")
        return

    n = stats["n"]
    PURPLE = "#4646A0"
    LIGHT = "#A0A0D8"
    ACCENT = "#E05C5C"
    BG = "#F8F8FF"
    GRID = "#DCDCF0"

    plt.rcParams.update({
        "figure.facecolor": BG,
        "axes.facecolor": BG,
        "axes.edgecolor": PURPLE,
        "axes.labelcolor": PURPLE,
        "axes.titlecolor": PURPLE,
        "xtick.color": PURPLE,
        "ytick.color": PURPLE,
        "grid.color": GRID,
        "grid.linestyle": "--",
        "grid.linewidth": 0.6,
        "font.family": "DejaVu Sans",
        "font.size": 9,
    })

    fig = plt.figure(figsize=(20, 24), facecolor=BG)
    fig.suptitle(
        f"📊 Распределение параметров генератора (симуляция {n:,} образцов)",
        fontsize=16,
        fontweight="bold",
        color=PURPLE,
        y=0.995,
    )

    gs = gridspec.GridSpec(
        5,
        3,
        figure=fig,
        hspace=0.55,
        wspace=0.35,
        top=0.96,
        bottom=0.04,
        left=0.06,
        right=0.97,
    )

    def styled(ax, title, xlabel="", ylabel="Частота"):
        ax.set_title(title, fontsize=10, fontweight="bold", pad=6)
        ax.set_xlabel(xlabel, fontsize=8)
        ax.set_ylabel(ylabel, fontsize=8)
        ax.grid(axis="y", zorder=0)
        ax.spines[["top", "right"]].set_visible(False)

    # 1. Длина текста
    ax = fig.add_subplot(gs[0, 0])
    len_counter = Counter(stats["lengths"])
    xs = list(
        range(CAPTCHA_CONFIG["min_length"], CAPTCHA_CONFIG["max_length"] + 1)
    )
    ys = [len_counter.get(x, 0) for x in xs]
    bars = ax.bar(xs, ys, color=PURPLE, zorder=3, width=0.6, edgecolor="white")
    for b, v in zip(bars, ys, strict=False):
        ax.text(
            b.get_x() + b.get_width() / 2,
            b.get_height() + n * 0.005,
            f"{v / max(n, 1) * 100:.1f}%",
            ha="center",
            va="bottom",
            fontsize=7,
            color=PURPLE,
        )
    ax.set_xticks(xs)
    styled(ax, "Длина текста", "Символов")

    # 2. Типы символов
    ax = fig.add_subplot(gs[0, 1])
    tc = stats["type_counts"]
    labels = list(tc.keys())
    sizes = [tc[l] for l in labels]
    _w, _t, auto = ax.pie(
        sizes,
        labels=labels,
        autopct="%1.1f%%",
        colors=[PURPLE, LIGHT, ACCENT][: len(labels)],
        startangle=140,
        wedgeprops={"edgecolor": "white", "linewidth": 1.5},
        textprops={"fontsize": 9},
    )
    for t in auto:
        t.set_color("white")
        t.set_fontweight("bold")
    ax.set_title(
        "Типы символов", fontsize=10, fontweight="bold", pad=6, color=PURPLE
    )

    # 3. Топ-30 символов
    ax = fig.add_subplot(gs[0, 2])
    top30 = stats["char_counts"].most_common(30)
    if top30:
        ch_labels, ch_vals = zip(*top30, strict=False)
        colors = [
            PURPLE
            if c in string.ascii_uppercase
            else LIGHT
            if c in string.ascii_lowercase
            else ACCENT
            for c in ch_labels
        ]
        ax.bar(ch_labels, ch_vals, color=colors, zorder=3, edgecolor="white")
        ax.set_xticks(range(len(ch_labels)))
        ax.set_xticklabels(ch_labels, fontsize=7)
    ax.legend(
        handles=[
            Patch(facecolor=PURPLE, label="Upper"),
            Patch(facecolor=LIGHT, label="Lower"),
            Patch(facecolor=ACCENT, label="Digit"),
        ],
        fontsize=7,
        framealpha=0.5,
    )
    styled(ax, "Топ-30 символов", "Символ")

    # 4. Stroke width
    ax = fig.add_subplot(gs[1, 0])
    swc = Counter(stats["stroke_widths"])
    keys = sorted(swc.keys())
    vals = [swc[k] for k in keys]
    ax.bar(
        [str(k) for k in keys],
        vals,
        color=[PURPLE, LIGHT, ACCENT, "#6666C0", "#8080E0"][: len(keys)],
        zorder=3,
        width=0.5,
        edgecolor="white",
    )
    for i, (_k, v) in enumerate(zip(keys, vals, strict=False)):
        ax.text(
            i,
            v + n * 0.005,
            f"{v / max(n, 1) * 100:.1f}%",
            ha="center",
            va="bottom",
            fontsize=8,
            color=PURPLE,
        )
    styled(ax, "Толщина обводки (1–5)", "px")

    # 5. Filled vs Outline
    ax = fig.add_subplot(gs[1, 1])
    fc = stats["filled_counts"]
    lbl = ["Outline", "Filled"]
    vals = [fc.get("Outline", 0), fc.get("Filled", 0)]
    ax.bar(
        lbl,
        vals,
        color=[PURPLE, ACCENT],
        zorder=3,
        width=0.4,
        edgecolor="white",
    )
    for i, v in enumerate(vals):
        ax.text(
            i,
            v + n * 0.005,
            f"{v / max(n, 1) * 100:.1f}%",
            ha="center",
            va="bottom",
            fontsize=9,
            color=PURPLE,
        )
    styled(ax, "Режим отрисовки (filled 50/50)", "Режим")

    # 6. Grayscale vs Color
    ax = fig.add_subplot(gs[1, 2])
    gsc = stats["grayscale_counts"]
    lbl = ["Color", "Grayscale"]
    vals = [gsc.get("Color", 0), gsc.get("Grayscale", 0)]
    ax.bar(
        lbl,
        vals,
        color=[PURPLE, "#888888"],
        zorder=3,
        width=0.4,
        edgecolor="white",
    )
    for i, v in enumerate(vals):
        ax.text(
            i,
            v + n * 0.005,
            f"{v / max(n, 1) * 100:.1f}%",
            ha="center",
            va="bottom",
            fontsize=9,
            color=PURPLE,
        )
    styled(ax, "Цветовой режим", "Режим")

    # 7. Углы
    ax = fig.add_subplot(gs[2, 0])
    import numpy as np

    a = np.array(stats["angles_all"]) if stats["angles_all"] else np.array([0])
    counts, edges = np.histogram(
        a, bins=36, range=RENDER_CONFIG["rotation_range_deg"]
    )
    centers = (edges[:-1] + edges[1:]) / 2
    ax.bar(
        centers,
        counts,
        width=(edges[1] - edges[0]) * 0.9,
        color=PURPLE,
        zorder=3,
        edgecolor="white",
        alpha=0.85,
    )
    ax.axvline(0, color=ACCENT, linewidth=1.2, linestyle="--")
    ax.axvline(
        a.mean(),
        color=LIGHT,
        linewidth=1.2,
        linestyle="-.",
        label=f"mean={a.mean():.1f}°",
    )
    ax.legend(fontsize=7)
    styled(ax, "Угол поворота символов", "°")

    # 8. Горизонтальный overlap
    ax = fig.add_subplot(gs[2, 1])
    o = np.array(stats["overlaps"]) if stats["overlaps"] else np.array([0])
    lo, hi = [v * 100 for v in RENDER_CONFIG["char_overlap_range"]]
    counts, edges = np.histogram(o, bins=20, range=(lo, hi))
    centers = (edges[:-1] + edges[1:]) / 2
    ax.bar(
        centers,
        counts,
        width=(edges[1] - edges[0]) * 0.9,
        color=LIGHT,
        zorder=3,
        edgecolor="white",
    )
    ax.axvline(
        o.mean(),
        color=ACCENT,
        linewidth=1.4,
        linestyle="--",
        label=f"mean={o.mean():.1f}%",
    )
    ax.legend(fontsize=7)
    styled(ax, "Горизонтальный overlap символов", "% ширины")

    # 9. Vertical overlap
    ax = fig.add_subplot(gs[2, 2])
    vo = stats["v_overlaps"]
    if vo:
        voc = Counter(vo)
        keys = sorted(voc.keys())
        vals = [voc[k] for k in keys]
        ax.bar(
            [str(k) for k in keys],
            vals,
            color=PURPLE,
            zorder=3,
            edgecolor="white",
            alpha=0.8,
        )
    styled(ax, "Вертикальное перекрытие строк", "px")

    # 10. Amplitude X
    ax = fig.add_subplot(gs[3, 0])
    ax_data = (
        np.array(stats["amplitude_xs"])
        if stats["amplitude_xs"]
        else np.array([0])
    )
    counts, edges = np.histogram(
        ax_data, bins=20, range=WAVE_CONFIG["amplitude_x_range"]
    )
    centers = (edges[:-1] + edges[1:]) / 2
    ax.bar(
        centers,
        counts,
        width=(edges[1] - edges[0]) * 0.9,
        color=ACCENT,
        zorder=3,
        edgecolor="white",
        alpha=0.85,
    )
    ax.axvline(
        ax_data.mean(),
        color=PURPLE,
        linewidth=1.4,
        linestyle="--",
        label=f"mean={ax_data.mean():.2f}",
    )
    ax.legend(fontsize=7)
    styled(ax, "Амплитуда волны X", "px")

    # 11. Amplitude Y
    ax = fig.add_subplot(gs[3, 1])
    ay_data = (
        np.array(stats["amplitude_ys"])
        if stats["amplitude_ys"]
        else np.array([0])
    )
    counts, edges = np.histogram(
        ay_data, bins=20, range=WAVE_CONFIG["amplitude_y_range"]
    )
    centers = (edges[:-1] + edges[1:]) / 2
    ax.bar(
        centers,
        counts,
        width=(edges[1] - edges[0]) * 0.9,
        color=LIGHT,
        zorder=3,
        edgecolor="white",
        alpha=0.85,
    )
    ax.axvline(
        ay_data.mean(),
        color=ACCENT,
        linewidth=1.4,
        linestyle="--",
        label=f"mean={ay_data.mean():.2f}",
    )
    ax.legend(fontsize=7)
    styled(ax, "Амплитуда волны Y", "px")

    # 12. BG types
    ax = fig.add_subplot(gs[3, 2])
    bgc = stats["bg_counts"]
    keys = list(bgc.keys())
    vals = [bgc[k] for k in keys]
    ax.bar(
        keys,
        vals,
        color=[PURPLE, LIGHT, ACCENT, "#6666C0"][: len(keys)],
        zorder=3,
        edgecolor="white",
        width=0.5,
    )
    for i, v in enumerate(vals):
        ax.text(
            i,
            v + n * 0.005,
            f"{v / max(n, 1) * 100:.1f}%",
            ha="center",
            va="bottom",
            fontsize=8,
            color=PURPLE,
        )
    styled(ax, "Тип фона", "Тип")

    # 13. Пустые капчи
    ax = fig.add_subplot(gs[4, 0])
    ec = stats["empty_counts"]
    lbl = ["WithText", "Empty"]
    vals = [ec.get("WithText", 0), ec.get("Empty", 0)]
    ax.bar(
        lbl,
        vals,
        color=[PURPLE, ACCENT],
        zorder=3,
        width=0.4,
        edgecolor="white",
    )
    for i, v in enumerate(vals):
        ax.text(
            i,
            v + n * 0.005,
            f"{v / max(n, 1) * 100:.1f}%",
            ha="center",
            va="bottom",
            fontsize=9,
            color=PURPLE,
        )
    styled(ax, "Пустые капчи (негативные примеры)", "Тип")

    # 14. Таблица конфига
    ax = fig.add_subplot(gs[4, 1:])
    ax.axis("off")
    n_fonts = len(discover_fonts())
    charset_len = len(CAPTCHA_CONFIG["charset"])
    table = [
        ["Параметр", "Значение"],
        ["Алфавит", f"{charset_len} символов"],
        [
            "Длина",
            f"{CAPTCHA_CONFIG["min_length"]}–{CAPTCHA_CONFIG["max_length"]}",
        ],
        ["Размер", f"{CAPTCHA_CONFIG["width"]}×{CAPTCHA_CONFIG["height"]}"],
        ["Шрифтов", str(n_fonts)],
        [
            "Размер шрифта",
            f"{FONT_CONFIG["size_range"][0]}–{FONT_CONFIG["size_range"][1]}",
        ],
        [
            "Stroke width",
            f"{RENDER_CONFIG["stroke_width_range"][0]}–{RENDER_CONFIG["stroke_width_range"][1]}",
        ],
        ["Filled prob", f"{RENDER_CONFIG["filled_probability"] * 100:.0f}%"],
        [
            "Grayscale prob",
            f"{COLOR_CONFIG["grayscale_probability"] * 100:.0f}%",
        ],
        ["Wave prob", f"{WAVE_CONFIG["apply_probability"] * 100:.0f}%"],
        [
            "Augment prob",
            f"{AUGMENTATION_CONFIG["apply_probability"] * 100:.0f}%",
        ],
        ["Типы фона", ", ".join(BACKGROUND_CONFIG["type_weights"].keys())],
        ["Симуляций", f"{n:,}"],
    ]
    tbl = ax.table(
        cellText=table[1:],
        colLabels=table[0],
        cellLoc="left",
        loc="center",
        bbox=[0, 0, 1, 1],
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8)
    for (r_, _c), cell in tbl.get_celld().items():
        cell.set_edgecolor(GRID)
        if r_ == 0:
            cell.set_facecolor(PURPLE)
            cell.set_text_props(color="white", fontweight="bold")
        elif r_ % 2 == 0:
            cell.set_facecolor("#EDEDFA")
        else:
            cell.set_facecolor(BG)
    ax.set_title(
        "Конфигурация генератора",
        fontsize=10,
        fontweight="bold",
        pad=8,
        color=PURPLE,
    )

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        print(f"✅ График сохранён: {output_path.absolute()}")

    if show:
        plt.show()
    else:
        plt.close(fig)


# ============================================================
# 🎯 ОТРИСОВКА BBOX
# ============================================================


def _draw_bboxes_on_image(
    image_path: Path, label_path: Path, output_path: Path
) -> None:
    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = img.size

    try:
        font = ImageFont.truetype("arial.ttf", 12)
    except Exception:
        font = ImageFont.load_default()

    if label_path.exists():
        with open(label_path) as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) != 5:
                    continue
                cid, xc, yc, bw, bh = map(float, parts)
                cid = int(cid)
                x_center = xc * w
                y_center = yc * h
                box_w = bw * w
                box_h = bh * h
                x1 = x_center - box_w / 2
                y1 = y_center - box_h / 2
                x2 = x_center + box_w / 2
                y2 = y_center + box_h / 2
                name = INV_CLASS_ID_MAP.get(cid, str(cid))
                draw.rectangle([x1, y1, x2, y2], outline="red", width=1)
                draw.text((x1, y1 - 12), name, fill="red", font=font)

    img.save(output_path)


def visualize_annotations(
    images_dir: Path, labels_dir: Path, output_dir: Path
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    images = list(images_dir.glob("*.png")) + list(images_dir.glob("*.jpg"))
    if not images:
        print("❌ Нет изображений для визуализации.")
        return

    print(f"🎨 Рисую боксы для {len(images)} изображений → {output_dir}")
    for img_path in images:
        lbl = labels_dir / (img_path.stem + ".txt")
        out = output_dir / (img_path.stem + "_bbox.png")
        _draw_bboxes_on_image(img_path, lbl, out)
    print("✅ Визуализация завершена.")
