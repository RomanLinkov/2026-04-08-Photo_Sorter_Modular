import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageOps
import os
import shutil
from data_config import save_settings, load_settings, THUMB_SIZE
from app_filmstrip import PhotoFilmstrip

class SetupWindow(tk.Toplevel):
    def __init__(self, parent, on_success):
        super().__init__(parent)
        self.on_success = on_success
        self.title("Настройка путей")
        self.geometry("650x480")
        self.grab_set() 
        
        saved = load_settings() or {}
        self.paths = {k: tk.StringVar(value=saved.get(k, "")) 
                     for k in ["source"] + [f"dest{i}" for i in range(1, 7)]}

        for k, txt in [("source", "ИСТОЧНИК:")] + [(f"dest{i}", f"Папка {i}:") for i in range(1, 7)]:
            f = tk.Frame(self); f.pack(fill=tk.X, padx=15, pady=6)
            tk.Label(f, text=txt, width=15, anchor="w", font=("Arial", 9, "bold")).pack(side=tk.LEFT)
            tk.Entry(f, textvariable=self.paths[k], bg="#f9f9f9").pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
            tk.Button(f, text="Обзор", command=lambda x=k: self.browse(x)).pack(side=tk.RIGHT)
        
        tk.Button(self, text="СОХРАНИТЬ", bg="#2e7d32", fg="white", font=("Arial", 11, "bold"), command=self.finish).pack(pady=20)

    def browse(self, key):
        self.grab_release()
        path = filedialog.askdirectory(parent=self)
        if path: self.paths[key].set(path)
        self.grab_set()

    def finish(self):
        res = {k: v.get() for k, v in self.paths.items()}
        if res["source"]:
            save_settings(res)
            if self.on_success: self.on_success(res)
            self.destroy()

class PhotoSorterApp:
    def __init__(self, root, config, engine):
        self.root, self.config, self.engine = root, config, engine
        self.current_idx = 0
        self.selected_indices = {0}
        self.files = []
        self.current_photo_tk = None
        
        self.engine.current_source = self.config.get('source', '')
        
        self._init_ui()
        self._bind_keys()
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_app_closing)
        
        threading.Thread(target=self._async_load_files, daemon=True).start()
        self._check_queue()

    def _init_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        self.main_label = tk.Label(self.root, bg="#121212", text="Загрузка...", fg="white")
        self.main_label.grid(row=0, column=0, sticky="nsew")

        self.prog_frame = tk.Frame(self.root, height=3, bg="#222222")
        self.prog_frame.grid(row=1, column=0, sticky="ew")
        self.prog_bar = tk.Frame(self.prog_frame, bg="#00e5ff", width=0, height=3)
        self.prog_bar.place(x=0, y=0)
        
        self.filmstrip = PhotoFilmstrip(self.root, self.engine, self.on_thumb_click)
        
        self.ctrl = tk.Frame(self.root, bg="#eeeeee", pady=10)
        self.ctrl.grid(row=3, column=0, sticky="ew")
        
        self.btn_l = tk.Frame(self.ctrl, bg="#eeeeee")
        self.btn_l.pack(side=tk.LEFT, padx=10)
        
        tk.Button(self.btn_l, text="⚙", font=("Arial", 12), width=3, command=self.open_settings, bg="#e0e0e0").pack(side=tk.LEFT, padx=5)
        tk.Button(self.btn_l, text="◀", width=5, command=lambda: self.navigate(-1)).pack(side=tk.LEFT, padx=2)
        tk.Button(self.btn_l, text="▶", width=5, command=lambda: self.navigate(1)).pack(side=tk.LEFT, padx=2)
        tk.Button(self.btn_l, text="↩ Поворот (R)", command=self.rotate_current).pack(side=tk.LEFT, padx=10)
        tk.Button(self.btn_l, text="🗑 Удалить", fg="red", command=self.delete_files).pack(side=tk.LEFT, padx=2)

        self.btn_r = tk.Frame(self.ctrl, bg="#eeeeee")
        self.btn_r.pack(side=tk.RIGHT, padx=10)
        
        # Контейнер для динамических кнопок папок
        self.btns_container = tk.Frame(self.btn_r, bg="#eeeeee")
        self.btns_container.pack(side=tk.LEFT)
        
        self.refresh_buttons()

    def _bind_keys(self):
        self.root.bind("<Left>", lambda e: self.navigate(-1))
        self.root.bind("<Right>", lambda e: self.navigate(1))
        self.root.bind("<Delete>", lambda e: self.delete_files())
        self.root.bind("r", lambda e: self.rotate_current())
        self.root.bind("к", lambda e: self.rotate_current())
        for i in range(1, 7):
            self.root.bind(str(i), lambda e, x=i: self.move_action(x))
        self.root.bind("<Configure>", lambda e: self.root.after(100, self.refresh_ui) if e.widget == self.root else None)

    def _async_load_files(self):
        try:
            source = self.config.get('source', '')
            files = self.engine.get_file_list(source)
            self.root.after(0, self._on_files_loaded, files)
        except:
            self.root.after(0, self._on_files_loaded, [])

    def _on_files_loaded(self, files):
        self.files = files
        if not self.files:
            self.main_label.config(text="Папка пуста", image="")
        else:
            self.current_idx = 0
            self.selected_indices = {0}
            self.refresh_ui()

    def _save_previous_rotations(self):
        fnames = list(self.engine.rotation_map.keys())
        if not fnames: return
        current_fname = self.files[self.current_idx] if self.files else ""
        for f in fnames:
            if f != current_fname:
                self.engine.executor.submit(self.engine.save_rotation_to_disk, f)

    def navigate(self, step):
        if not self.files: return
        self._save_previous_rotations()
        self.current_idx = (self.current_idx + step) % len(self.files)
        self.selected_indices = {self.current_idx}
        self.refresh_ui()

    def on_thumb_click(self, idx, state):
        self._save_previous_rotations()
        if state & 0x0001: # Shift
            start, end = min(self.current_idx, idx), max(self.current_idx, idx)
            for i in range(start, end + 1): self.selected_indices.add(i)
        elif state & 0x0004: # Ctrl
            if idx in self.selected_indices: self.selected_indices.remove(idx)
            else: self.selected_indices.add(idx)
        else:
            self.selected_indices = {idx}
        self.current_idx = idx
        self.refresh_ui()

    def rotate_current(self):
        if not self.files: return
        for idx in self.selected_indices:
            if idx < len(self.files):
                self.engine.rotate_in_memory(self.files[idx])
        self.refresh_ui()

    def show_current(self):
        if not self.files or self.current_idx >= len(self.files): return
        fname = self.files[self.current_idx]
        path = os.path.join(self.config['source'], fname)
        
        def load_full():
            try:
                with Image.open(path) as img:
                    img = ImageOps.exif_transpose(img)
                    angle = self.engine.rotation_map.get(fname, 0)
                    if angle != 0:
                        img = img.rotate(angle, expand=True)
                    w, h = max(100, self.main_label.winfo_width()), max(100, self.main_label.winfo_height())
                    img.thumbnail((w, h), Image.Resampling.LANCZOS)
                    self.current_photo_tk = ImageTk.PhotoImage(img)
                    self.main_label.config(image=self.current_photo_tk, text="")
            except:
                self.main_label.config(text="Ошибка загрузки", image="")
        threading.Thread(target=load_full, daemon=True).start()

    def move_action(self, folder_num):
        dest_path = self.config.get(f"dest{folder_num}")
        if not dest_path or not self.files: return
        to_move = [self.files[i] for i in sorted(self.selected_indices, reverse=True) if i < len(self.files)]
        for fname in to_move:
            try:
                self.engine.save_rotation_to_disk(fname)
                shutil.move(os.path.join(self.config['source'], fname), os.path.join(dest_path, fname))
                self.files.remove(fname)
            except: pass
        self._after_file_list_change()

    def delete_files(self):
        if not self.selected_indices or not self.files: return
        if not messagebox.askyesno("Удаление", "Удалить выбранные?"): return
        to_delete = [self.files[i] for i in sorted(self.selected_indices, reverse=True) if i < len(self.files)]
        for fname in to_delete:
            try:
                self.engine.clear_cache([fname])
                os.remove(os.path.join(self.config['source'], fname))
                self.files.remove(fname)
            except: pass
        self._after_file_list_change()

    def _after_file_list_change(self):
        self.filmstrip._clear_all()
        self.selected_indices = set()
        if not self.files:
            self.current_idx = 0
            self.main_label.config(image="", text="Папка пуста")
        else:
            if self.current_idx >= len(self.files): self.current_idx = len(self.files) - 1
            self.selected_indices = {self.current_idx}
        self.refresh_ui()

    def open_settings(self):
        SetupWindow(self.root, self.on_settings_changed)

    def on_settings_changed(self, new_config):
        self.config = new_config
        self.engine.current_source = self.config.get('source', '')
        self.current_idx = 0
        self.files = []
        self.engine.clear_cache()
        self.filmstrip._clear_all()
        self.root.update_idletasks()
        self.refresh_buttons()
        threading.Thread(target=self._async_load_files, daemon=True).start()

    def refresh_buttons(self):
        for widget in self.btns_container.winfo_children():
            widget.destroy()
        
        has_paths = any(self.config.get(f"dest{i}") for i in range(1, 7))
        if has_paths:
            tk.Label(self.btns_container, text="В папку:", bg="#eeeeee", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
            for i in range(1, 7):
                path = self.config.get(f"dest{i}", "")
                if path:
                    folder_name = os.path.basename(path.rstrip(os.sep))
                    btn = tk.Button(self.btns_container, text=f"{i}: {folder_name}", padx=8,
                                    command=lambda x=i: self.move_action(x), font=("Arial", 9, "bold"),
                                    bg="#ffffff", relief=tk.GROOVE)
                    btn.pack(side=tk.LEFT, padx=2)

    def refresh_ui(self):
        if not self.files: return
        self.show_current()
        self.filmstrip.refresh(self.files, self.current_idx, self.selected_indices, self.root.winfo_width())

    def on_app_closing(self):
        fnames = list(self.engine.rotation_map.keys())
        for f in fnames:
            self.engine.save_rotation_to_disk(f)
        self.root.destroy()

    def _check_queue(self):
        updated = False
        while not self.engine.result_queue.empty():
            try:
                self.engine.result_queue.get_nowait()
                updated = True
            except: break
        if updated: self.filmstrip.refresh(self.files, self.current_idx, self.selected_indices, self.root.winfo_width())
        self.root.after(100, self._check_queue)
