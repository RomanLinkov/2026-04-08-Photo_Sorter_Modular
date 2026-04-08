import json
import os
import multiprocessing
import time

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

def get_dir_size(path):
    """Считает размер папки в байтах"""
    total = 0
    try:
        with os.scandir(path) as it:
            for entry in it:
                if entry.is_file():
                    total += entry.stat().size
    except: pass
    return total

def cleanup_cache_smart(days_limit=7, max_gb=0.5):
    """
    Умная очистка кэша:
    1. Удаляет файлы, к которым не обращались более 7 дней.
    2. Если после этого кэш все еще больше 500МБ, удаляет самые старые до лимита.
    """
    if not os.path.exists(CACHE_DIR): return
    
    now = time.time()
    seconds_limit = days_limit * 24 * 60 * 60
    limit_bytes = max_gb * 1024 * 1024 * 1024
    
    files_data = []
    current_size = 0
    
    # Собираем данные о файлах
    try:
        for f in os.listdir(CACHE_DIR):
            p = os.path.join(CACHE_DIR, f)
            if os.path.isfile(p):
                stat = os.stat(p)
                # Используем st_atime (время последнего доступа)
                files_data.append({
                    'path': p,
                    'atime': stat.st_atime,
                    'size': stat.st_size
                })
                current_size += stat.st_size
    except: return

    # 1. Удаляем файлы старше лимита по дням
    deleted_count = 0
    remaining_files = []
    
    for item in files_data:
        if (now - item['atime']) > seconds_limit:
            try:
                os.remove(item['path'])
                current_size -= item['size']
                deleted_count += 1
            except: pass
        else:
            remaining_files.append(item)

    # 2. Если кэш все еще слишком большой, чистим по объему (самые старые сначала)
    if current_size > limit_bytes:
        remaining_files.sort(key=lambda x: x['atime'])
        
        target_size = limit_bytes * 0.7
        for item in remaining_files:
            try:
                os.remove(item['path'])
                current_size -= item['size']
                deleted_count += 1
            except: pass
            
            if current_size <= target_size:
                break

    if deleted_count > 0:
        print(f"Очистка кэша: удалено {deleted_count} файлов. Текущий размер: {current_size // 1024 // 1024} МБ")
