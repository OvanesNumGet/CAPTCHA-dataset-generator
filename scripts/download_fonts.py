"""
Скачивает кураторскую подборку шрифтов Google Fonts в папку fonts/.

Использование:
    python scripts/download_fonts.py
    python scripts/download_fonts.py --dest fonts --force

Все шрифты — под свободными лицензиями (OFL / Apache), берутся из
официального репозитория https://github.com/google/fonts.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# ============================================================
# 📚 СПИСОК ШРИФТОВ
# Микс: читаемые sans/serif + характерные display + рукописные.
# Все ссылки — на master ветку google/fonts.
# ============================================================

GITHUB_RAW = "https://raw.githubusercontent.com/google/fonts/main"

FONTS: list[tuple[str, str]] = [
    # --- Классические sans (для фона читаемости) ---
    # ("Roboto-Regular.ttf", f"{GITHUB_RAW}/apache/roboto/static/Roboto-Regular.ttf"),
    # ("Roboto-Bold.ttf",    f"{GITHUB_RAW}/apache/roboto/static/Roboto-Bold.ttf"),
    (
        "OpenSans-Regular.ttf",
        f"{GITHUB_RAW}/ofl/opensans/OpenSans%5Bwdth%2Cwght%5D.ttf",
    ),
    ("Lato-Regular.ttf", f"{GITHUB_RAW}/ofl/lato/Lato-Regular.ttf"),
    ("Lato-Bold.ttf", f"{GITHUB_RAW}/ofl/lato/Lato-Bold.ttf"),
    (
        "Montserrat-Regular.ttf",
        f"{GITHUB_RAW}/ofl/montserrat/Montserrat%5Bwght%5D.ttf",
    ),
    ("Poppins-Regular.ttf", f"{GITHUB_RAW}/ofl/poppins/Poppins-Regular.ttf"),
    ("Poppins-Bold.ttf", f"{GITHUB_RAW}/ofl/poppins/Poppins-Bold.ttf"),
    (
        "Inter-Regular.ttf",
        f"{GITHUB_RAW}/ofl/inter/Inter%5Bopsz%2Cwght%5D.ttf",
    ),
    # --- Дополнительные качественные Sans-Serif ---
    ("Nunito-Regular.ttf", f"{GITHUB_RAW}/ofl/nunito/Nunito%5Bwght%5D.ttf"),
    # ("Ubuntu-Regular.ttf",    f"{GITHUB_RAW}/ofl/ubuntu/Ubuntu-Regular.ttf"),
    (
        "FiraSans-Regular.ttf",
        f"{GITHUB_RAW}/ofl/firasans/FiraSans-Regular.ttf",
    ),
    (
        "WorkSans-Regular.ttf",
        f"{GITHUB_RAW}/ofl/worksans/WorkSans%5Bwght%5D.ttf",
    ),
    (
        "NotoSans-Regular.ttf",
        f"{GITHUB_RAW}/ofl/notosans/NotoSans%5Bwdth%2Cwght%5D.ttf",
    ),
    # ("PTSans-Regular.ttf",    f"{GITHUB_RAW}/ofl/ptsans/PTSans-Regular.ttf"),
    (
        "SourceSans3-Regular.ttf",
        f"{GITHUB_RAW}/ofl/sourcesans3/SourceSans3%5Bwght%5D.ttf",
    ),
    # --- Serif ---
    (
        "PlayfairDisplay-Regular.ttf",
        f"{GITHUB_RAW}/ofl/playfairdisplay/PlayfairDisplay%5Bwght%5D.ttf",
    ),
    # ("Merriweather-Regular.ttf",    f"{GITHUB_RAW}/ofl/merriweather/Merriweather-Regular.ttf"),
    # ("Merriweather-Bold.ttf",       f"{GITHUB_RAW}/ofl/merriweather/Merriweather-Bold.ttf"),
    (
        "RobotoSlab-Regular.ttf",
        f"{GITHUB_RAW}/apache/robotoslab/RobotoSlab%5Bwght%5D.ttf",
    ),
    ("Lora-Regular.ttf", f"{GITHUB_RAW}/ofl/lora/Lora%5Bwght%5D.ttf"),
    # ("PTSerif-Regular.ttf",         f"{GITHUB_RAW}/ofl/ptserif/PTSerif-Regular.ttf"),
    # ("LibreBaskerville-Regular.ttf", f"{GITHUB_RAW}/ofl/librebaskerville/LibreBaskerville-Regular.ttf"),
    (
        "CrimsonText-Regular.ttf",
        f"{GITHUB_RAW}/ofl/crimsontext/CrimsonText-Regular.ttf",
    ),
    # --- Жирные и плотные (хорошо для filled) ---
    ("Oswald-Regular.ttf", f"{GITHUB_RAW}/ofl/oswald/Oswald%5Bwght%5D.ttf"),
    ("Anton-Regular.ttf", f"{GITHUB_RAW}/ofl/anton/Anton-Regular.ttf"),
    (
        "BebasNeue-Regular.ttf",
        f"{GITHUB_RAW}/ofl/bebasneue/BebasNeue-Regular.ttf",
    ),
    ("Bungee-Regular.ttf", f"{GITHUB_RAW}/ofl/bungee/Bungee-Regular.ttf"),
    # --- Характерные display ---
    ("Lobster-Regular.ttf", f"{GITHUB_RAW}/ofl/lobster/Lobster-Regular.ttf"),
    (
        "Righteous-Regular.ttf",
        f"{GITHUB_RAW}/ofl/righteous/Righteous-Regular.ttf",
    ),
    (
        "PressStart2P-Regular.ttf",
        f"{GITHUB_RAW}/ofl/pressstart2p/PressStart2P-Regular.ttf",
    ),
    ("Monoton-Regular.ttf", f"{GITHUB_RAW}/ofl/monoton/Monoton-Regular.ttf"),
    # --- Mono ---
    # ("RobotoMono-Regular.ttf", f"{GITHUB_RAW}/apache/robotomono/static/RobotoMono-Regular.ttf"),
    (
        "SpaceMono-Regular.ttf",
        f"{GITHUB_RAW}/ofl/spacemono/SpaceMono-Regular.ttf",
    ),
    # --- Рукописные / handwritten ---
    ("Caveat-Regular.ttf", f"{GITHUB_RAW}/ofl/caveat/Caveat%5Bwght%5D.ttf"),
    (
        "IndieFlower-Regular.ttf",
        f"{GITHUB_RAW}/ofl/indieflower/IndieFlower-Regular.ttf",
    ),
    (
        "PatrickHand-Regular.ttf",
        f"{GITHUB_RAW}/ofl/patrickhand/PatrickHand-Regular.ttf",
    ),
    (
        "ShadowsIntoLight-Regular.ttf",
        f"{GITHUB_RAW}/ofl/shadowsintolight/ShadowsIntoLight.ttf",
    ),
]


# ============================================================
# ⬇️ DOWNLOADER
# ============================================================


def _download_one(url: str, dest: Path, timeout: int = 30) -> bool:
    """Скачивает один файл. Возвращает True при успехе."""
    req = Request(
        url, headers={"User-Agent": "captcha-gen-font-downloader/1.0"}
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            data = resp.read()
    except (HTTPError, URLError, TimeoutError) as e:
        print(f"   ❌ ошибка: {e}")
        return False

    if len(data) < 2_000:
        print(f"   ❌ подозрительно маленький файл ({len(data)} байт)")
        return False

    dest.write_bytes(data)
    return True


def _verify_font(path: Path) -> bool:
    """Проверяем, что PIL может открыть шрифт."""
    try:
        from PIL import ImageFont

        ImageFont.truetype(str(path), 32)
        return True
    except Exception as e:
        print(f"   ⚠️ файл не открывается как шрифт: {e}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Скачивание подборки шрифтов Google Fonts для генератора капч."
    )
    parser.add_argument(
        "--dest",
        default="fonts",
        help="Папка назначения (по умолчанию: fonts)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Перекачать даже если файл уже существует.",
    )
    args = parser.parse_args()

    dest_dir = Path(args.dest)
    dest_dir.mkdir(parents=True, exist_ok=True)

    print(f"📁 Папка назначения: {dest_dir.absolute()}")
    print(f"📦 Файлов к загрузке: {len(FONTS)}\n")

    ok = 0
    skipped = 0
    failed: list[str] = []

    for idx, (name, url) in enumerate(FONTS, start=1):
        target = dest_dir / name
        print(f"[{idx}/{len(FONTS)}] {name}")

        if target.exists() and not args.force:
            if _verify_font(target):
                print("   ✔ уже есть, пропускаю")
                skipped += 1
                continue
            print("   ⚠ битый файл, перекачиваю")
            target.unlink(missing_ok=True)

        if _download_one(url, target):
            if _verify_font(target):
                print(f"   ✅ {target.stat().st_size // 1024} КБ")
                ok += 1
            else:
                target.unlink(missing_ok=True)
                failed.append(name)
        else:
            failed.append(name)

    print("\n────────────────────────────────────")
    print(f"✅ Скачано: {ok}")
    print(f"⏭  Пропущено (уже было): {skipped}")
    if failed:
        print(f"❌ Не удалось: {len(failed)}")
        for name in failed:
            print(f"   • {name}")
        print(
            "\nПодсказка: если что-то из Google Fonts переехало, "
            "посмотрите актуальный путь в репозитории "
            "https://github.com/google/fonts и поправьте список."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
