"""
Высокоуровневый генератор капч.

Объединяет модули: фон → clutter(под) → рендер текста → композит →
clutter(сверху) → волна → letterbox → albumentations → punch_holes →
запись на диск.

Поддерживает параллельную генерацию через multiprocessing для ускорения.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
import os
from pathlib import Path
import random
import uuid

from PIL import Image
import numpy as np

from captcha_gen.augmentations import apply_augmentations
from captcha_gen.backgrounds import random_background
from captcha_gen.clutter import draw_clutter, punch_holes
from captcha_gen.config import (
    CAPTCHA_CONFIG,
    DEFAULT_FONTS_DIR,
    DEFAULT_VAL_SPLIT,
)
from captcha_gen.distortions import maybe_apply_wave
from captcha_gen.letterbox import letterbox_image_and_bboxes
from captcha_gen.renderer import render_text_composite
from captcha_gen.text import generate_random_text, sanitize_text
from captcha_gen.yolo_utils import bboxes_to_yolo, yolo_to_lines

# ============================================================
# 🧩 ВЫСОКОУРОВНЕВАЯ КОНФИГУРАЦИЯ
# ============================================================

GENERATOR_CONFIG: dict = {
    # Шанс, что капча будет «пустой» (фон без текста). Полезно для негативных примеров.
    "empty_captcha_probability": 0.03,
    # Использовать ли letterbox-resize (иначе — простой resize без сохранения пропорций)
    "use_letterbox": True,
    # Рабочий «холст» до letterbox — можно сделать крупнее итогового, чтобы был запас
    # для aug-ий; обычно совпадает с финальным (width, height).
    "working_canvas_scale": 1.0,
    # Вероятности слоёв clutter (независимы друг от друга)
    "clutter_under_probability": 0.65,  # контуры ПОД текстом (на фоне)
    "clutter_over_probability": 0.65,  # контуры ПОВЕРХ текста
    # Параллелизм: количество рабочих процессов (None = auto по числу ядер)
    "num_workers": None,
    # Размер батча для воркера (сколько капч генерирует один воркер за раз)
    "worker_batch_size": 50,
}


# ============================================================
# 📦 РЕЗУЛЬТАТ ГЕНЕРАЦИИ
# ============================================================


@dataclass
class GeneratedSample:
    image: Image.Image  # RGB, итоговый размер
    text: str  # может быть пустой строкой у empty-captcha
    yolo_lines: list[str] = field(default_factory=list)
    is_empty: bool = False


# ============================================================
# 🏭 КЛАСС-ГЕНЕРАТОР
# ============================================================


class CaptchaGenerator:
    def __init__(
        self,
        fonts_dir: str | Path = DEFAULT_FONTS_DIR,
        seed: int | None = None,
    ) -> None:
        self.fonts_dir = str(fonts_dir)
        self.rng = random.Random(seed)

    # ---------- низкоуровневый генератор одного образца ----------
    def generate(
        self, text: str | None = None, save_yolo: bool = False
    ) -> GeneratedSample:
        r = self.rng

        # Пустая капча (без текста) с некоторой вероятностью
        force_empty = (
            text is None
            and r.random() < GENERATOR_CONFIG["empty_captcha_probability"]
        )

        final_w = CAPTCHA_CONFIG["width"]
        final_h = CAPTCHA_CONFIG["height"]
        ws = GENERATOR_CONFIG["working_canvas_scale"]
        work_size = (int(final_w * ws), int(final_h * ws))

        # --- фон ---
        bg_img, text_color_rgba = random_background(work_size, rng=r)

        if force_empty:
            # даже у пустой капчи могут быть мусорные линии (реалистичнее)
            if r.random() < GENERATOR_CONFIG["clutter_under_probability"]:
                bg_img = draw_clutter(bg_img, text_color_rgba, rng=r)
            return self._finalize(bg_img, "", [], save_yolo, is_empty=True)

        # --- текст ---
        if text is None:
            text = generate_random_text(rng=r)
            text = sanitize_text(text, rng=r)

        # --- clutter под текстом (прямо на фоне) ---
        if r.random() < GENERATOR_CONFIG["clutter_under_probability"]:
            bg_img = draw_clutter(bg_img, text_color_rgba, rng=r)

        # --- рендер текстовой композиции ---
        text_layer, bboxes_abs = render_text_composite(
            text=text,
            canvas_size=work_size,
            text_color=text_color_rgba,
            bg_color=(255, 255, 255, 0),  # прозрачный фон у слоя
            fonts_dir=self.fonts_dir,
            rng=r,
        )

        # --- композит: фон + текст ---
        composed = bg_img.convert("RGBA")
        composed = Image.alpha_composite(composed, text_layer)

        # --- clutter поверх текста ---
        if r.random() < GENERATOR_CONFIG["clutter_over_probability"]:
            composed = draw_clutter(composed, text_color_rgba, rng=r)

        # --- волна ---
        composed = maybe_apply_wave(composed, rng=r)
        composed = composed.convert("RGB")

        # --- letterbox (с пересчётом bbox) ---
        if GENERATOR_CONFIG["use_letterbox"]:
            composed, bboxes_abs = letterbox_image_and_bboxes(
                composed, (final_w, final_h), bboxes_abs, rng=r
            )
        else:
            composed = composed.resize((final_w, final_h), Image.BICUBIC)
            sx = final_w / work_size[0]
            sy = final_h / work_size[1]
            bboxes_abs = [
                (x * sx, y * sy, w * sx, h * sy, ch)
                for x, y, w, h, ch in bboxes_abs
            ]

        # --- нормализуем bbox → YOLO ---
        norm, class_ids, _ = bboxes_to_yolo(bboxes_abs, final_w, final_h)

        # --- Albumentations с bbox-awareness ---
        arr = np.array(composed)
        arr, new_norm, new_ids = apply_augmentations(
            arr,
            norm if save_yolo else None,
            class_ids if save_yolo else None,
            rng=r,
        )
        composed = Image.fromarray(arr)

        # --- punch holes (маленькие дырки) в самом конце ---
        composed = punch_holes(composed, rng=r)

        yolo_lines: list[str] = []
        if save_yolo and new_norm:
            yolo_lines = yolo_to_lines(new_norm, new_ids)

        return self._finalize(composed, text, yolo_lines, save_yolo)

    # ---------- служебное ----------
    @staticmethod
    def _finalize(
        img: Image.Image,
        text: str,
        yolo_lines: list[str],
        save_yolo: bool,
        is_empty: bool = False,
    ) -> GeneratedSample:
        if img.mode != "RGB":
            img = img.convert("RGB")
        return GeneratedSample(
            image=img,
            text=text,
            yolo_lines=yolo_lines if save_yolo else [],
            is_empty=is_empty,
        )


# ============================================================
# 📁 ПАКЕТНАЯ ГЕНЕРАЦИЯ ДАТАСЕТА
# ============================================================


def _save_sample(
    sample: GeneratedSample,
    img_dir: Path,
    lbl_dir: Path | None,
    filename_stem: str,
) -> None:
    img_path = img_dir / f"{filename_stem}.png"
    sample.image.save(img_path)
    if lbl_dir is not None:
        lbl_path = lbl_dir / f"{filename_stem}.txt"
        with open(lbl_path, "w") as f:
            f.write("\n".join(sample.yolo_lines))


def _sample_stem(
    sample: GeneratedSample,
    index: int,
    with_label: bool = True,
    with_index: bool = False,
) -> str:
    """
    Формирует имя файла.
    - Если with_label=True: [текст]_[индекс]_[uid]
    - Если with_label=False: [длинный_uid]
    """
    if not with_label:
        # Для prod: используем полный UUID для минимизации коллизий без меток
        return uuid.uuid4().hex[:16]

    # Для test: метка + индекс + короткий хеш
    uid = uuid.uuid4().hex[:8]
    tag = "empty" if sample.is_empty else sample.text or "empty"
    if with_index:
        return f"{tag}_{index:04d}_{uid}"
    return f"{tag}_{uid}"


# ============================================================
# 🔀 ПАРАЛЛЕЛЬНАЯ ГЕНЕРАЦИЯ (MULTIPROCESSING)
# ============================================================


def _get_num_workers() -> int:
    """Определяет оптимальное количество рабочих процессов."""
    configured = GENERATOR_CONFIG["num_workers"]
    if configured is not None:
        return max(1, configured)
    try:
        cpu_count = os.cpu_count() or 1
        # Оставляем 1 ядро для ОС, но минимум 1 воркер
        return max(1, cpu_count - 1)
    except Exception:
        return 1


def _worker_generate_batch(
    batch_size: int,
    fonts_dir: str,
    seed: int,
    save_yolo: bool,
    img_dir: str,
    lbl_dir: str | None,
    with_label: bool,
    with_index: bool,
    start_index: int,
) -> int:
    """
    Функция-воркер: генерирует и сохраняет пачку капч в отдельном процессе.
    Возвращает количество сгенерированных образцов.
    """
    from captcha_gen.fonts import reset_font_cache

    # Сбрасываем кеш шрифтов в дочернем процессе (пути могут отличаться)
    reset_font_cache()

    gen = CaptchaGenerator(fonts_dir=fonts_dir, seed=seed)
    img_path = Path(img_dir)
    lbl_path = Path(lbl_dir) if lbl_dir else None

    for i in range(batch_size):
        sample = gen.generate(save_yolo=save_yolo)
        stem = _sample_stem(
            sample,
            index=start_index + i,
            with_label=with_label,
            with_index=with_index,
        )
        _save_sample(sample, img_path, lbl_path, stem)

    return batch_size


def _run_split_parallel(
    name: str,
    count: int,
    fonts_dir: str,
    base_seed: int | None,
    img_dir: Path,
    lbl_dir: Path | None,
    yolo: bool,
    progress_every: int,
) -> None:
    """Параллельная генерация одного сплита (train или val)."""
    num_workers = _get_num_workers()
    batch_size = GENERATOR_CONFIG["worker_batch_size"]

    # Разбиваем на задачи
    tasks: list[tuple[int, int, int]] = []  # (batch_sz, seed, start_idx)
    remaining = count
    idx = 0
    task_id = 0
    while remaining > 0:
        bs = min(batch_size, remaining)
        # Каждый батч получает уникальный seed (детерминированный, если base_seed задан)
        if base_seed is not None:
            seed = base_seed + task_id * 100_000
        else:
            seed = random.randint(0, 2**31)
        tasks.append((bs, seed, idx))
        idx += bs
        remaining -= bs
        task_id += 1

    if num_workers <= 1 or count <= batch_size:
        # Однопоточный режим (малый датасет или 1 ядро)
        done = 0
        for bs, seed, start_idx in tasks:
            _worker_generate_batch(
                batch_size=bs,
                fonts_dir=fonts_dir,
                seed=seed,
                save_yolo=yolo,
                img_dir=str(img_dir),
                lbl_dir=str(lbl_dir) if lbl_dir else None,
                with_label=False,
                with_index=False,
                start_index=start_idx,
            )
            done += bs
            if done % progress_every < batch_size or done == count:
                print(f"  {name} [{done}/{count}]")
        return

    print(
        f"  {name}: {num_workers} воркеров, {len(tasks)} задач по ~{batch_size}"
    )
    done = 0

    with ProcessPoolExecutor(max_workers=num_workers) as pool:
        futures = {}
        for bs, seed, start_idx in tasks:
            fut = pool.submit(
                _worker_generate_batch,
                batch_size=bs,
                fonts_dir=fonts_dir,
                seed=seed,
                save_yolo=yolo,
                img_dir=str(img_dir),
                lbl_dir=str(lbl_dir) if lbl_dir else None,
                with_label=False,
                with_index=False,
                start_index=start_idx,
            )
            futures[fut] = bs

        for fut in as_completed(futures):
            try:
                n_done = fut.result()
            except Exception as e:
                print(f"  ⚠️ Ошибка в воркере: {e}")
                n_done = 0
            done += n_done
            if done % progress_every < batch_size or done >= count:
                print(f"  {name} [{done}/{count}]")


def generate_dataset(
    total: int,
    output_dir: str | Path,
    *,
    mode: str = "prod",
    yolo: bool = False,
    split: float = DEFAULT_VAL_SPLIT,
    fonts_dir: str | Path = DEFAULT_FONTS_DIR,
    seed: int | None = None,
    progress_every: int = 500,
    num_workers: int | None = None,
) -> None:
    """
    Сгенерировать датасет.

    mode == "prod"  → структура train/ val/ (+ images/labels при yolo)
    mode == "test"  → плоская папка (+ images/labels при yolo)

    num_workers — количество процессов (None = автоматически по числу ядер).
    """
    output_dir = Path(output_dir)

    if num_workers is not None:
        GENERATOR_CONFIG["num_workers"] = num_workers

    if mode == "prod":
        n_val = int(total * split)
        n_train = total - n_val

        train_img = (
            (output_dir / "train" / "images")
            if yolo
            else (output_dir / "train")
        )
        val_img = (
            (output_dir / "val" / "images") if yolo else (output_dir / "val")
        )
        train_lbl = (output_dir / "train" / "labels") if yolo else None
        val_lbl = (output_dir / "val" / "labels") if yolo else None

        for d in filter(None, [train_img, val_img, train_lbl, val_lbl]):
            d.mkdir(parents=True, exist_ok=True)

        print(
            f"🚀 Генерация {total} изображений (train: {n_train}, val: {n_val}) → {output_dir}"
        )
        if yolo:
            print("   YOLO-аннотации включены.")

        _run_split_parallel(
            "train",
            n_train,
            str(fonts_dir),
            seed,
            train_img,
            train_lbl,
            yolo,
            progress_every,
        )
        _run_split_parallel(
            "val",
            n_val,
            str(fonts_dir),
            (seed + 999_999_999) if seed is not None else None,
            val_img,
            val_lbl,
            yolo,
            progress_every,
        )

        print(f"✅ Готово! Данные сохранены в {output_dir.absolute()}")
    else:
        img_dir = (output_dir / "images") if yolo else output_dir
        lbl_dir = (output_dir / "labels") if yolo else None
        img_dir.mkdir(parents=True, exist_ok=True)
        if lbl_dir:
            lbl_dir.mkdir(parents=True, exist_ok=True)

        print(
            f"🧪 Генерация {total} тестовых изображений → {output_dir}"
            + (" (YOLO)" if yolo else "")
        )

        # Тестовый режим: последовательно, с лейблами в именах
        gen = CaptchaGenerator(fonts_dir=fonts_dir, seed=seed)
        for i in range(total):
            sample = gen.generate(save_yolo=yolo)
            stem = _sample_stem(
                sample, index=i, with_label=True, with_index=True
            )
            _save_sample(sample, img_dir, lbl_dir, stem)
            print(f"  [{i + 1}/{total}] {stem}.png")
        print(f"✅ Готово! → {output_dir.absolute()}")
