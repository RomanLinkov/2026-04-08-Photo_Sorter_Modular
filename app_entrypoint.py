import os
import sys
import tkinter as tk
from pillow_heif import register_heif_opener

from license_check import startup_license_gate

register_heif_opener()

if getattr(sys, "frozen", False):
    basedir = sys._MEIPASS
else:
    basedir = os.path.dirname(__file__)
sys.path.append(basedir)

try:
    from app_ui import SetupWindow, PhotoSorterApp
    from core_engine import PhotoEngine
    from data_config import APP_VERSION, load_settings, ensure_dirs, cleanup_cache_smart
except ImportError as e:
    print(f"Ошибка импорта: {e}")


def start_main(config, root, engine):
    for w in root.winfo_children():
        w.destroy()
    root.deiconify()
    try:
        root.state("zoomed")
    except tk.TclError:
        root.geometry("1200x800")
    root.update()
    PhotoSorterApp(root, config, engine)


if __name__ == "__main__":
    if not startup_license_gate():
        os._exit(0)

    ensure_dirs()
    cleanup_cache_smart(days_limit=7, max_gb=0.5)

    root = tk.Tk()
    root.title(f"Photo Sorter Pro {APP_VERSION}")
    root.configure(bg="#121212")

    def force_exit():
        try:
            root.destroy()
        except tk.TclError:
            pass
        os._exit(0)

    root.protocol("WM_DELETE_WINDOW", force_exit)

    engine = PhotoEngine()
    config = load_settings()

    if not config or not config.get("source") or not os.path.exists(config.get("source")):
        root.withdraw()
        SetupWindow(root, lambda cfg: start_main(cfg, root, engine))
    else:
        start_main(config, root, engine)

    root.mainloop()
