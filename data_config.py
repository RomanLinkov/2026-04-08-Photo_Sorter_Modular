import json
import os
import multiprocessing

SETTINGS_FILE = "photo_sorter_settings.json"
CACHE_DIR = ".photo_cache"
TRASH_DIR = ".photo_trash" # Папка для временного хранения удаленных фото
THUMB_SIZE = 160
EXTENSIONS = ('.jpg', '.jpeg', '.png', '.bmp', '.webp', '.heic', '.heif')

# Оптимальное кол-во потоков
MAX_WORKERS = multiprocessing.cpu_count() + 2

def save_settings(settings):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=4)

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: 
            return None
    return None

def ensure_dirs():
    """Создает все системные папки при запуске"""
    for d in [CACHE_DIR, TRASH_DIR]:
        if not os.path.exists(d):
            try:
                os.makedirs(d)
            except:
                pass
