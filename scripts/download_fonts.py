"""
Умный загрузчик шрифтов Google Fonts.
Автоматически находит пути к файлам, перебирая возможные структуры репозитория.
Сохраняет отчет о доступных файлах при ошибках.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from urllib.request import Request, urlopen

# Константы для поиска
GITHUB_RAW = "https://raw.githubusercontent.com/google/fonts"
GITHUB_API = "https://api.github.com/repos/google/fonts/contents"

# Список шрифтов: (Имя файла для сохранения, Семья в репозитории, Желаемое имя в репозитории)
# Имена файлов с [] нужно URL-кодировать: [ -> %5B, ] -> %5D, , -> %2C
FONTS_TO_GET = [
    # Roboto — вариативный, нет static-версии; wdth=100,wght=400 => Regular, wght=700 => Bold
    ("Roboto-Regular.ttf", "roboto", "Roboto%5Bwdth%2Cwght%5D.ttf"),
    (
        "Roboto-Bold.ttf",
        "roboto",
        "Roboto%5Bwdth%2Cwght%5D.ttf",
    ),  # тот же файл, variable font
    ("RobotoMono-Regular.ttf", "robotomono", "RobotoMono%5Bwght%5D.ttf"),
    ("OpenSans-Regular.ttf", "opensans", "OpenSans%5Bwdth%2Cwght%5D.ttf"),
    ("Lato-Regular.ttf", "lato", "Lato-Regular.ttf"),
    ("Lato-Bold.ttf", "lato", "Lato-Bold.ttf"),
    ("Montserrat-Regular.ttf", "montserrat", "Montserrat%5Bwght%5D.ttf"),
    ("Poppins-Regular.ttf", "poppins", "Poppins-Regular.ttf"),
    ("Poppins-Bold.ttf", "poppins", "Poppins-Bold.ttf"),
    ("Inter-Regular.ttf", "inter", "Inter%5Bopsz%2Cwght%5D.ttf"),
    ("Ubuntu-Regular.ttf", "ubuntu", "Ubuntu-Regular.ttf"),
    ("PTSans-Regular.ttf", "ptsans", "PT_Sans-Web-Regular.ttf"),
    (
        "Merriweather-Regular.ttf",
        "merriweather",
        "Merriweather%5Bopsz%2Cwdth%2Cwght%5D.ttf",
    ),
    (
        "Merriweather-Bold.ttf",
        "merriweather",
        "Merriweather%5Bopsz%2Cwdth%2Cwght%5D.ttf",
    ),  # тот же файл
    ("PTSerif-Regular.ttf", "ptserif", "PT_Serif-Web-Regular.ttf"),
    (
        "LibreBaskerville-Regular.ttf",
        "librebaskerville",
        "LibreBaskerville%5Bwght%5D.ttf",
    ),
    ("CrimsonText-Regular.ttf", "crimsontext", "CrimsonText-Regular.ttf"),
    ("Arvo-Regular.ttf", "arvo", "Arvo-Regular.ttf"),
    ("Oswald-Regular.ttf", "oswald", "Oswald%5Bwght%5D.ttf"),
    ("Anton-Regular.ttf", "anton", "Anton-Regular.ttf"),
    ("BebasNeue-Regular.ttf", "bebasneue", "BebasNeue-Regular.ttf"),
    ("SpaceMono-Regular.ttf", "spacemono", "SpaceMono-Regular.ttf"),
    (
        "Inconsolata-Regular.ttf",
        "inconsolata",
        "Inconsolata%5Bwdth%2Cwght%5D.ttf",
    ),
]


def get_directory_listing(family_path: str) -> list[str]:
    """Пытается получить список файлов в папке через API GitHub."""
    url = f"{GITHUB_API}/{family_path}"
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return [item["name"] for item in data]
    except:
        return []


def download_file(url: str) -> bytes | None:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(req, timeout=15) as resp:
            return resp.read()
    except:
        return None


def smart_find_and_download(
    family: str, filename: str
) -> tuple[bytes | None, str]:
    """Пробует разные комбинации путей для поиска шрифта."""
    branches = ["main", "master"]
    licenses = ["ofl", "apache", "ufl"]
    subdirs = ["static", ""]  # Сначала ищем в static, потом в корне

    for branch in branches:
        for lic in licenses:
            for subdir in subdirs:
                path_parts = [lic, family]
                if subdir:
                    path_parts.append(subdir)

                path = "/".join(path_parts)
                url = f"{GITHUB_RAW}/{branch}/{path}/{filename}"

                data = download_file(url)
                if data and len(data) > 2000:
                    return data, url

    return None, ""


def main(argv: list[str] | None = None) -> int:
    """
    Main entry point. Accepts optional argv for programmatic use.

    Args:
        argv: List of command-line arguments (like sys.argv[1:]).
              If None, uses sys.argv[1:] automatically.

    Returns:
        Exit code: 0 on success, 1 on failure.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--dest", default="fonts")
    args = parser.parse_args(
        argv
    )  # Accept explicit argv for notebook compatibility

    dest_dir = Path(args.dest)
    dest_dir.mkdir(parents=True, exist_ok=True)

    log_file = Path("available_files_log.txt")
    with open(log_file, "w", encoding="utf-8") as f:
        f.write("=== ОТЧЕТ ПО ПОИСКУ ШРИФТОВ ===\n\n")

    print(f"Начинаю умную загрузку в {dest_dir.absolute()}")

    success = 0
    failed = []

    for i, (save_name, family, remote_name) in enumerate(FONTS_TO_GET, 1):
        print(
            f"[{i}/{len(FONTS_TO_GET)}] Поиск {family} ({save_name})...",
            end="",
            flush=True,
        )

        target = dest_dir / save_name

        # Если файл уже существует (например, Bold — та же variable font что и Regular) — не качаем повторно
        if target.exists() and target.stat().st_size > 2000:
            print(" ⏭ Уже есть (пропуск)")
            success += 1
            continue

        data, found_url = smart_find_and_download(family, remote_name)

        if data:
            target.write_bytes(data)
            print(f" ✅ Найдено! ({found_url})")
            success += 1
        else:
            print(" ❌ НЕ НАЙДЕНО")
            failed.append(save_name)
            # Пытаемся понять, что там вообще есть
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"--- Ошибка: {save_name} (семья: {family}) ---\n")
                f.write(f"Пробовал искать: {remote_name}\n")
                for lic in ["ofl", "apache"]:
                    listing = get_directory_listing(f"{lic}/{family}")
                    if listing:
                        f.write(
                            f"Содержимое {lic}/{family}: {", ".join(listing)}\n"
                        )
                f.write("\n")

    print("\n" + "=" * 40)
    print(f"✅ Успешно скачано: {success}")
    if failed:
        print(f"❌ Не удалось найти: {len(failed)}")
        for name in failed:
            print(f"   - {name}")
        print(
            f"Список доступных файлов в проблемных папках сохранен в: {log_file.absolute()}"
        )
    else:
        print("Все шрифты загружены успешно!")

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
