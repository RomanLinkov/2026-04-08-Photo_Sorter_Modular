import tkinter as tk
from app_ui import SetupWindow, PhotoSorterApp
from core_engine import PhotoEngine
from data_config import load_settings

import sys
import os

# Корректная работа путей внутри EXE
if getattr(sys, 'frozen', False):
    basedir = sys._MEIPASS
else:
    basedir = os.path.dirname(__file__)
sys.path.append(basedir)



def start_main(config):
    for w in root.winfo_children():
        w.destroy()
    PhotoSorterApp(root, config, engine)
    root.deiconify()

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Photo Sorter Pro")
    
    # Сразу разворачиваем на весь экран
    try:
        root.state('zoomed') 
    except:
        root.geometry("1200x800")

    engine = PhotoEngine()
    config = load_settings()

    if not config or not config.get("source"):
        root.withdraw()
        SetupWindow(root, start_main)
    else:
        start_main(config)

    root.mainloop()
