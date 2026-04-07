import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw
import os
from data_config import save_settings, load_settings, THUMB_SIZE

class SetupWindow(tk.Toplevel):
    def __init__(self, parent, on_success):
        super().__init__(parent)
        self.on_success = on_success
        self.title("Настройка путей")
        self.geometry("650x480")
        self.lift(); self.attributes("-topmost", True); self.grab_set()
        
        saved = load_settings() or {}
        self.paths = {k: tk.StringVar(value=saved.get(k, "")) 
                     for k in ["source"] + [f"dest{i}" for i in range(1, 7)]}

        for k, txt in [("source", "ИСТОЧНИК:")] + [(f"dest{i}", f"Папка {i}:") for i in range(1, 7)]:
            f = tk.Frame(self); f.pack(fill=tk.X, padx=15, pady=6)
            tk.Label(f, text=txt, width=15, anchor="w", font=("Arial", 9, "bold")).pack(side=tk.LEFT)
            tk.Entry(f, textvariable=self.paths[k], bg="#f9f9f9").pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
            tk.Button(f, text="Обзор", command=lambda x=k: self.paths[x].set(filedialog.askdirectory())).pack(side=tk.RIGHT)
        
        tk.Button(self, text="СОХРАНИТЬ И ЗАПУСТИТЬ", bg="#2e7d32", fg="white", font=("Arial", 11, "bold"), command=self.finish).pack(pady=20)

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
        self.start_idx = 0
        self.last_clicked_idx = 0
        self.selected_indices = set()
        self.current_img_obj = None
        self.resize_timer = None
        
        self._init_ui()
        self._bind_keys()
        self.refresh()

    def _init_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.root.rowconfigure(1, minsize=THUMB_SIZE + 20)

        self.main_label = tk.Label(self.root, bg="#121212")
        self.main_label.grid(row=0, column=0, sticky="nsew")
        
        self.thumb_frame = tk.Frame(self.root, height=THUMB_SIZE+20, bg="#1e1e1e")
        self.thumb_frame.grid(row=1, column=0, sticky="ew")
        self.thumb_frame.pack_propagate(False)
        
        self.t_widgets = []
        for _ in range(45):
            c = tk.Frame(self.thumb_frame, width=THUMB_SIZE+6, height=THUMB_SIZE+6, bg="#1e1e1e")
            c.pack(side=tk.LEFT, padx=2, pady=5); c.pack_propagate(False)
            l = tk.Label(c, bg="#1e1e1e")
            l.place(relx=0.5, rely=0.5, anchor="center")
            self.t_widgets.append((c, l))

        self.ctrl = tk.Frame(self.root, bg="#eeeeee", pady=10)
        self.ctrl.grid(row=2, column=0, sticky="ew")
        self.btn_l = tk.Frame(self.ctrl, bg="#eeeeee"); self.btn_l.pack(side=tk.LEFT, padx=10)
        self.btn_r = tk.Frame(self.ctrl, bg="#eeeeee"); self.btn_r.pack(side=tk.RIGHT, padx=10)

    def _init_buttons(self):
        # ОЧИСТКА ОБЕИХ ПАНЕЛЕЙ (чтобы кнопки не множились)
        for w in self.btn_l.winfo_children(): w.destroy()
        for w in self.btn_r.winfo_children(): w.destroy()

        # Левая панель: Сортировка
        for i in range(1, 7):
            p = self.config.get(f'dest{i}')
            if p:
                name = os.path.basename(p) or f"P{i}"
                btn = tk.Button(self.btn_l, text=name, command=lambda x=p: self.move(x), relief="groove", padx=10)
                btn.pack(side=tk.LEFT, padx=2)
                self.root.bind(str(i), lambda e, x=p: self.move(x))
        
        tk.Button(self.btn_l, text="Undo", bg="#bbdefb", command=self.undo, padx=10).pack(side=tk.LEFT, padx=15)
        
        # Правая панель: Инструменты
        self.count_lbl = tk.Label(self.btn_r, text="", bg="#eeeeee", font=("Arial", 10, "bold"))
        self.count_lbl.pack(side=tk.LEFT, padx=10)

        tk.Button(self.btn_r, text="Повернуть ⟳", bg="#c8e6c9", command=self.rotate_batch, padx=8).pack(side=tk.LEFT, padx=5)
        tk.Button(self.btn_r, text="Удалить", bg="#ffcdd2", fg="#b71c1c", command=self.delete_files, padx=10).pack(side=tk.LEFT, padx=5)
        tk.Button(self.btn_r, text="⚙", command=self.reconfig, padx=8).pack(side=tk.LEFT, padx=5)

    def refresh(self):
        self.files = self.engine.get_file_list(self.config['source'])
        self._init_buttons()
        self.root.after(200, self._initial_draw)

    def _initial_draw(self):
        self.show_current()
        self.update_strip()

    def show_current(self):
        if not self.files:
            self.main_label.config(image='', text="ПАПКА ПУСТА", fg="white")
            if hasattr(self, 'count_lbl'): self.count_lbl.config(text="0 / 0")
            return
        path = os.path.join(self.config['source'], self.files[self.current_idx])
        try:
            self.current_img_obj = Image.open(path)
            self.render()
        except:
            self.main_label.config(image='', text=f"ОШИБКА:\n{self.files[self.current_idx]}", fg="red")
        
        if hasattr(self, 'count_lbl'):
            self.count_lbl.config(text=f"{self.current_idx + 1} / {len(self.files)}")

    def render(self):
        if not self.current_img_obj: return
        self.root.update_idletasks()
        w, h = self.main_label.winfo_width(), self.main_label.winfo_height()
        if w < 50: w = self.root.winfo_width() - 40
        if h < 50: h = self.root.winfo_height() - (THUMB_SIZE + 150)

        img = self.current_img_obj.copy()
        img.thumbnail((max(w, 100), max(h, 100)), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(img)
        self.main_label.config(image=self.photo, text="")

    def rotate_batch(self):
        idx_list = sorted(list(self.selected_indices) if self.selected_indices else [self.current_idx])
        if not self.files: return

        for idx in idx_list:
            fname = self.files[idx]
            path = os.path.join(self.config['source'], fname)
            try:
                with Image.open(path) as img:
                    rotated = img.rotate(-90, expand=True)
                    rotated.save(path, quality=95, subsampling=0)
                self.engine.thumb_cache.pop(fname, None)
            except Exception as e:
                print(f"Ошибка поворота {fname}: {e}")
        
        self.show_current()
        self.update_strip()

    def delete_files(self):
        dest = os.path.join(self.config['source'], "_DELETED")
        if not os.path.exists(dest): os.makedirs(dest)
        self.move(dest)

    def move(self, dest):
        if not self.files: return
        idx_list = sorted(list(self.selected_indices) if self.selected_indices else [self.current_idx], reverse=True)
        files_to_move = [self.files[i] for i in idx_list]
        
        self.engine.move_files(files_to_move, self.config['source'], dest)
        self.selected_indices.clear()
        
        if self.current_idx >= len(self.files) - len(files_to_move):
            self.current_idx = max(0, len(self.files) - len(files_to_move) - 1)
        
        self.refresh()

    def undo(self): 
        if self.engine.undo_last(): self.refresh()

    def update_strip(self):
        win_w = self.root.winfo_width()
        num_v = min(len(self.t_widgets), max(1, win_w // (THUMB_SIZE + 10)))
        if self.current_idx >= self.start_idx + num_v: self.start_idx = self.current_idx - num_v + 1
        elif self.current_idx < self.start_idx: self.start_idx = self.current_idx

        for i, (c, l) in enumerate(self.t_widgets):
            idx = self.start_idx + i
            if i < num_v and idx < len(self.files):
                img = self.engine.get_thumb(self.config['source'], self.files[idx])
                l.config(image=img)
                l.bind("<Button-1>", lambda e, x=idx: self.handle_click(x, e.state))
                color = "#1e1e1e"
                if idx == self.current_idx: color = "#00e5ff"
                if idx in self.selected_indices: color = "#ffea00"
                c.config(bg=color)
            else:
                l.config(image=''); c.config(bg="#1e1e1e")

    def handle_click(self, idx, state):
        if state & 0x0001: # Shift
            low, high = sorted([self.last_clicked_idx, idx])
            for i in range(low, high + 1): self.selected_indices.add(i)
        elif state & 0x0004: # Ctrl
            if idx in self.selected_indices: self.selected_indices.remove(idx)
            else: self.selected_indices.add(idx)
        else:
            self.selected_indices.clear()
            self.current_idx = idx
        self.last_clicked_idx = idx
        self.show_current(); self.update_strip()

    def _nav(self, d):
        if 0 <= self.current_idx + d < len(self.files):
            self.current_idx += d
            self.selected_indices.clear()
            self.show_current(); self.update_strip()

    def _bind_keys(self):
        self.root.bind("<Right>", lambda e: self._nav(1))
        self.root.bind("<Left>", lambda e: self._nav(-1))
        self.root.bind("r", lambda e: self.rotate_batch())
        self.root.bind("<Delete>", lambda e: self.delete_files())
        self.root.bind("<Control-z>", lambda e: self.undo())
        self.root.bind("<Configure>", self.on_resize)
        self.root.bind("<Escape>", lambda e: [self.selected_indices.clear(), self.update_strip()])

    def on_resize(self, event):
        if event.widget == self.root:
            if self.resize_timer: self.root.after_cancel(self.resize_timer)
            self.resize_timer = self.root.after(150, self.render)

    def reconfig(self):
        SetupWindow(self.root, self.relaunch)

    def relaunch(self, config):
        self.config = config
        self.refresh()
