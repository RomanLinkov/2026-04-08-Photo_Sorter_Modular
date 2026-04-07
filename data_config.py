import json
import os

SETTINGS_FILE = "photo_sorter_settings.json"
THUMB_SIZE = 160
EXTENSIONS = ('.jpg', '.jpeg', '.png', '.bmp', '.webp')

def save_settings(settings):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=4)

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return None
    return None
