# Photo Sorter Pro v2.0 (Modular)

Высокопроизводительное модульное приложение на Python (Tkinter + Pillow) для эффективной сортировки фотоархивов.

## 🏗 Архитектура
- `app_entrypoint.py`: Инициализация и жизненный цикл.
- `app_ui.py`: Интерфейс, горячие клавиши и стек Undo.
- `core_engine.py`: Многопоточный движок обработки (Pillow, ThreadPoolExecutor).
- `app_filmstrip.py`: Виджет ленты миниатюр.
- `data_config.py`: Конфигурация и системные пути.

## ⚡ Оптимизация производительности
Приложение использует систему **двухуровневого кэширования**:
1. **RAM Cache**: Объекты PhotoImage хранятся в памяти для мгновенного отклика UI.
2. **Disk Cache (`.photo_cache/`)**: Миниатюры (160px) сохраняются на диск. Это избавляет от необходимости повторного декодирования тяжелых JPEG при перезапуске, снижая нагрузку на CPU в 10-15 раз.

## 🛠 Сборка
```bash
pip install Pillow pyinstaller
pyinstaller --noconfirm --onefile --windowed --icon="icon.ico" --name "PhotoSorterPro_2.0" --clean app_entrypoint.py
