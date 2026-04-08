import tkinter as tk
import sys
import os

# Корректная работа путей внутри EXE
if getattr(sys, 'frozen', False):
    basedir = sys._MEIPASS
else:
    basedir = os.path.dirname(__file__)
sys.path.append(basedir)

# Импорты наших модулей
from app_ui import SetupWindow, PhotoSorterApp
from core_engine import PhotoEngine
from data_config import load_settings, ensure_cache_dir

def start_main(config):
    """Запуск основного приложения после настройки"""
    # Очищаем временные виджеты
    for w in root.winfo_children():
        w.destroy()
    
    # Разворачиваем окно
    root.deiconify()
    try:
        root.state('zoomed')
    except:
        root.geometry("1200x800")
    
    root.update()
    
    # Запускаем приложение
    PhotoSorterApp(root, config, engine)

if __name__ == "__main__":
    # Создаем папку кэша перед стартом
    ensure_cache_dir()
    
    root = tk.Tk()
    root.title("Photo Sorter Pro")
    root.configure(bg="#121212")

    engine = PhotoEngine()
    config = load_settings()

    # Если настроек нет или путь к источнику пуст — открываем Setup
    if not config or not config.get("source") or not os.path.exists(config.get("source")):
        root.withdraw()
        SetupWindow(root, start_main)
    else:
        start_main(config)

    root.mainloop()
