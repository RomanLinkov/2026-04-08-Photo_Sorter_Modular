# Photo Sorter Pro v2.4.6 (Modular)

![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue)
![Pillow](https://img.shields.io/badge/Pillow-10+-green)

**Photo Sorter Pro** — инструмент для сортировки, просмотра и базовой обработки фотоархивов. Рассчитан на работу с большими папками.

---

## Ключевые возможности

* **HEIC/HEIF**: поддержка форматов Apple через `pillow-heif`.
* **Фоновый precache**: при открытии папки запускается фоновая генерация миниатюр.
* **LOAD: N**: счётчик задач в очереди обработки.
* **Кэш**: удаление неиспользуемого кэша (7 дней) и ограничение объёма (~500 МБ).
* **Undo**: отмена перемещений и удалений через локальную корзину `.photo_trash`.
* **Чистый выход**: остановка фоновых потоков при закрытии окна.
* **Без лицензии**: можно перемещать и удалять до **1000** фотографий (счётчик в панели «Бесплатно: N/1000»), затем запрашивается активация. Файл учёта: `photo_sorter_trial.json` рядом с программой.

---

## Управление (горячие клавиши)

| Действие | Клавиша | Описание |
| :--- | :--- | :--- |
| Навигация | `←` / `→` | Листать фотографии |
| Сортировка | `1` – `6` | Переместить в соответствующую папку |
| Поворот | `R` / `К` | Физический поворот файла (разные раскладки) |
| Удаление | `Delete` | В корзину `.photo_trash` |
| Отмена | `Ctrl` + физическая **Z** | Undo (работает при любой раскладке клавиатуры) |

---

## Архитектура

- `app_entrypoint.py` — точка входа, HEIC, кэш при старте.
- `license_check.py` — HWID, окно активации, `license.txt`.
- `app_ui.py` — интерфейс, навигация, Undo.
- `core_engine.py` — пул потоков, миниатюры.
- `app_filmstrip.py` — лента превью.
- `data_config.py` — настройки, пути, очистка кэша.

---

## Установка и сборка

### Зависимости

```bash
pip install -r requirements.txt
```

### Сборка EXE (Windows): PyArmor + PyInstaller

Нужны файлы в **корне репозитория**: `icon.ico`, `tg_qr.png` (QR для Telegram в окне активации — кладётся внутрь exe через `--add-data`). Команды ниже выполняйте из этого каталога.

**1. Зависимости для сборки**

```bash
pip install -r requirements.txt
pip install pyarmor pyinstaller
```

**2. Обфускация исходников (все модули приложения одним набором)**

В PyArmor **8.x** обычно используют `gen`; в **7.x** — `obfuscate` (см. справку вашей версии: `pyarmor --help`).

```bash
pyarmor gen -O armored app_entrypoint.py license_check.py app_ui.py app_filmstrip.py core_engine.py data_config.py
```

В каталоге `armored/` появятся обфусцированные `.py` и папка **`pyarmor_runtime_…`** (суффикс может отличаться от `000000` — смотрите фактическое имя).

**Зачем отдельная папка `armored/`, а не сразу `dist/`:** в `dist/` PyInstaller кладёт готовый exe; смешивать туда же обфусцированные скрипты можно, но неудобно. Если у вас привычный процесс «всё в `dist/`», замените в командах ниже `armored` на `dist` и пути к `app_entrypoint.py` / рантайму — смысл тот же.

**3. PyInstaller: полная команда (иконка, QR, рантайм PyArmor, tkinter, явные импорты)**

Ниже — эквивалент вашей старой длинной команды, но с учётом текущего кода:

- **`--add-data "tg_qr.png;."`** — QR в окне активации (корень `_MEIPASS`).
- **`--add-data "armored\pyarmor_runtime_000000;pyarmor_runtime_000000"`** — подложить рантайм PyArmor внутрь сборки (имя папки **подставьте своё**, как после `pyarmor gen`).
- **`--collect-submodules "tkinter"`** и **`--hidden-import tkinter.messagebox`** — как у вас, чтобы не терять части Tk.
- **`--hidden-import`** для модулей приложения и Pillow — как у вас, плюс **`license_check`** и **`app_filmstrip`** (в старой строке их не было; иначе обфускация/разрезание на файлы может не подтянуть цепочку).
- **`--add-data "dist\*.py;."`** из старой команды обычно **не нужен**, если точка входа — один `app_entrypoint.py` из `armored\` и перечислены `hidden-import`: PyInstaller сам тянет зависимости. Глоб `*.py` в CMD часто **не раскрывается**; если без него сборка падает — добавьте `--paths armored` или явные `--add-data` для конкретных файлов.

В `--add-data` на Windows разделитель **точка с запятой**: `исходник;папка_внутри_exe`.

**CMD (полная, многострочно):** подставьте **`pyarmor_runtime_…`** из своей папки `armored\`.

```bat
pyinstaller --noconfirm --onefile --windowed --clean ^
  --name PhotoSorterPro_2.4.6 ^
  --icon=icon.ico ^
  --add-data "tg_qr.png;." ^
  --add-data "armored\pyarmor_runtime_000000;pyarmor_runtime_000000" ^
  --collect-submodules "tkinter" ^
  --hidden-import "tkinter.messagebox" ^
  --hidden-import "license_check" ^
  --hidden-import "app_ui" ^
  --hidden-import "app_filmstrip" ^
  --hidden-import "core_engine" ^
  --hidden-import "data_config" ^
  --hidden-import "pillow_heif" ^
  --hidden-import "PIL" ^
  armored\app_entrypoint.py
```

**Одной строкой (после правки имени `pyarmor_runtime_*`):**

```bat
pyinstaller --noconfirm --onefile --windowed --clean --name PhotoSorterPro_2.4.6 --icon=icon.ico --add-data "tg_qr.png;." --add-data "armored\pyarmor_runtime_000000;pyarmor_runtime_000000" --collect-submodules "tkinter" --hidden-import "tkinter.messagebox" --hidden-import "license_check" --hidden-import "app_ui" --hidden-import "app_filmstrip" --hidden-import "core_engine" --hidden-import "data_config" --hidden-import "pillow_heif" --hidden-import "PIL" armored\app_entrypoint.py
```

Готовый файл: `dist\PhotoSorterPro_2.4.6.exe`.

**Сокращённый вариант** (если у вас PyInstaller сам подтягивает рантайм и модули — можно пробовать без `--add-data` рантайма и без части `hidden-import`; при ошибке импорта верните флаги по сообщению).

**Руководство пользователя:** `dist\USER_GUIDE.md` при релизе обычно **кладут рядом с exe** (отдельным файлом); приложение его из сборки не открывает.

Лицензия PyArmor и опции `pyarmor gen` — по [документации PyArmor](https://pyarmor.readthedocs.io/) под вашу версию.

---

### Сборка без PyArmor (только PyInstaller)

Для отладки можно собрать из исходников без обфускации:

```bat
pyinstaller --noconfirm --onefile --windowed --clean --icon=icon.ico --name PhotoSorterPro_2.4.6 --add-data "tg_qr.png;." app_entrypoint.py
```

Релизы удобнее выкладывать как вложения к тегу в Git, а не хранить крупный бинарник в истории коммитов.

### Тесты (опционально)

```bash
pip install -r requirements.txt
pytest -q
```
