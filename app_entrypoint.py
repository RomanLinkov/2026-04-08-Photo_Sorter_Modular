import hashlib
import subprocess
import tkinter as tk
from tkinter import messagebox  # Добавим для вывода ошибки юзеру
import sys
import os
from pillow_heif import register_heif_opener

# --- БЛОК ЗАЩИТЫ (вставляем сюда) ---

def get_hwid():
    """Достаем уникальный ID процессора"""
    try:
        cmd = "wmic cpu get processorid"
        hwid = subprocess.check_output(cmd, shell=True).decode().split()
        return hwid[1] if len(hwid) > 1 else "UNKNOWN_DEVICE"
    except Exception:
        return "UNKNOWN_DEVICE"

def generate_key(hwid):
    """Шифруем ID в лицензионный ключ"""
    secret_salt = "MY_SUPER_SECRET_PROJECT_2024"  # Твоя секретная соль
    raw_string = f"{hwid}-{secret_salt}"
    return hashlib.sha256(raw_string.encode()).hexdigest()

def check_license_gui():
    """Проверка лицензии с выводом окна ошибки, если что не так"""
    current_hwid = get_hwid()
    valid_key = generate_key(current_hwid)
    
    # Путь к файлу лицензии рядом с EXE или скриптом
    license_path = os.path.join(os.path.abspath(os.path.dirname(sys.argv[0])), "license.txt")

    try:
        with open(license_path, "r") as f:
            user_key = f.read().strip()
    except FileNotFoundError:
        user_key = ""

    if user_key != valid_key:
        # Если лицензия не совпала, создаем невидимое окно для вывода сообщения
        temp_root = tk.Tk()
        temp_root.withdraw()
        messagebox.showerror(
            "Лицензия не найдена", 
            f"Программа не активирована для данного ПК.\n\n"
            f"Ваш ID: {current_hwid}\n\n"
            f"Пришлите этот ID разработчику для получения ключа."
        )
        temp_root.destroy()
        return False
    return True

# --- КОНЕЦ БЛОКА ЗАЩИТЫ ---

# Регистрируем поддержку HEIC для Pillow
register_heif_opener()

# Корректная работа путей внутри EXE
if getattr(sys, 'frozen', False):
    basedir = sys._MEIPASS
else:
    basedir = os.path.dirname(__file__)
sys.path.append(basedir)

# Импорты наших модулей
from app_ui import SetupWindow, PhotoSorterApp
from core_engine import PhotoEngine
from data_config import load_settings, ensure_dirs

def start_main(config):
    """Запуск основного приложения после настройки"""
    for w in root.winfo_children():
        w.destroy()
    
    root.deiconify()
    try:
        root.state('zoomed')
    except:
        root.geometry("1200x800")
    
    root.update()
    PhotoSorterApp(root, config, engine)

if __name__ == "__main__":
    # 1. ПЕРВЫМ ДЕЛОМ ПРОВЕРЯЕМ ЛИЦЕНЗИЮ
    if not check_license_gui():
        sys.exit() # Закрываем всё, если лицензии нет

    # Дальше твой обычный код запуска
    from data_config import ensure_dirs, cleanup_cache_smart
    ensure_dirs()
    cleanup_cache_smart(days_limit=7, max_gb=0.5)
    
    root = tk.Tk()
    root.title("Photo Sorter Pro")
    root.configure(bg="#121212")

    engine = PhotoEngine()
    config = load_settings()

    if not config or not config.get("source") or not os.path.exists(config.get("source")):
        root.withdraw()
        SetupWindow(root, start_main)
    else:
        start_main(config)

    root.mainloop()
