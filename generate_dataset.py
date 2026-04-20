"""
Точка входа для генерации датасета капч.

Вся логика вынесена в пакет captcha_gen/.
См. captcha_gen/cli.py для деталей команд.
"""

from captcha_gen.cli import main

if __name__ == "__main__":
    main()
