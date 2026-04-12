import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageOps
import os
import shutil
from data_config import APP_VERSION, save_settings, load_settings, THUMB_SIZE, TRASH_DIR

# Физическая клавиша Z + Ctrl (любая раскладка): VK на Windows, типичные коды на macOS / X11
if sys.platform == "darwin":
    _UNDO_PHYS_KEYCODES = frozenset({6})
elif sys.platform == "win32":
    _UNDO_PHYS_KEYCODES = frozenset({90})
else:
    _UNDO_PHYS_KEYCODES = frozenset({52, 90, 6})
from app_filmstrip import PhotoFilmstrip

class SetupWindow(tk.Toplevel):
    def __init__(self, parent, on_success):
        super().__init__(parent)
        self.on_success = on_success
        self.title("Настройка путей")
        self.geometry("650x480")
        self.grab_set()

        # --- ДОБАВЛЕНО: Принудительный выход при закрытии на крестик ---
        self.protocol("WM_DELETE_WINDOW", self.force_close_app)
        
        saved = load_settings() or {}
        self.paths = {k: tk.StringVar(value=saved.get(k, ""))
                      for k in ["source"] + [f"dest{i}" for i in range(1, 7)]}

        for k, txt in [("source", "ИСТОЧНИК:")] + [(f"dest{i}", f"Папка {i}:") for i in range(1, 7)]:
            f = tk.Frame(self); f.pack(fill=tk.X, padx=15, pady=6)
            tk.Label(f, text=txt, width=15, anchor="w", font=("Arial", 9, "bold")).pack(side=tk.LEFT)
            tk.Entry(f, textvariable=self.paths[k], bg="#f9f9f9").pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
            tk.Button(f, text="Обзор", command=lambda x=k: self.browse(x)).pack(side=tk.RIGHT)

        tk.Button(self, text="СОХРАНИТЬ", bg="#2e7d32", fg="white", 
                  font=("Arial", 11, "bold"), command=self.finish).pack(pady=20)

    # Функция для полной остановки процесса
    def force_close_app(self):
        self.destroy()
        os._exit(0) # Гарантированно убивает процесс со всеми потоками

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
        self.history = []
        self.last_nav_time = 0  # Для умной задержки

        
        self.engine.current_source = self.config.get('source', '')
        
        self._init_ui()
        self._bind_keys()
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_app_closing)
        
        threading.Thread(target=self._async_load_files, daemon=True).start()
        self._check_queue()

    def _init_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        # ВЕРХНЯЯ ИНФО-ПАНЕЛЬ
        self.info_panel = tk.Frame(self.root, bg="#1a1a1a", height=30)
        self.info_panel.grid(row=0, column=0, sticky="ew")
        self.info_panel.pack_propagate(False)
        
        self.fname_label = tk.Label(self.info_panel, text="", fg="#00e5ff", bg="#1a1a1a", 
                                    font=("Consolas", 10, "bold"))
        self.fname_label.pack(side=tk.LEFT, padx=10)

        self.cache_stat = tk.Label(self.info_panel, text="✓ READY", fg="#00e5ff", 
                                   bg="#1a1a1a", font=("Consolas", 9, "bold"), width=15)
        self.cache_stat.pack(side=tk.RIGHT, padx=10)

        # Главная область просмотра
        self.main_label = tk.Label(self.root, bg="#121212", text="") # Добавили text=""
        self.main_label.grid(row=1, column=0, sticky="nsew")


        # Полоска прогресса
        self.prog_frame = tk.Frame(self.root, height=2, bg="#222222")
        self.prog_frame.grid(row=2, column=0, sticky="ew")
        self.prog_bar = tk.Frame(self.prog_frame, bg="#00e5ff", width=0, height=2)
        self.prog_bar.place(x=0, y=0)
        
        self.filmstrip = PhotoFilmstrip(self.root, self.engine, self.on_thumb_click)

        # Панель управления
        self.ctrl = tk.Frame(self.root, bg="#eeeeee", pady=5)
        self.ctrl.grid(row=4, column=0, sticky="ew")
        
        self.btn_l = tk.Frame(self.ctrl, bg="#eeeeee")
        self.btn_l.pack(side=tk.LEFT, padx=10)
        
        tk.Button(self.btn_l, text="⚙", command=self.open_settings).pack(side=tk.LEFT, padx=2)
        tk.Button(self.btn_l, text="⤺ Undo", command=self.undo_last_action).pack(side=tk.LEFT, padx=2)
        tk.Button(self.btn_l, text="◀", command=lambda: self.navigate(-1)).pack(side=tk.LEFT, padx=2)
        tk.Button(self.btn_l, text="▶", command=lambda: self.navigate(1)).pack(side=tk.LEFT, padx=2)
        tk.Button(self.btn_l, text="↩ Поворот (R)", command=self.rotate_current).pack(side=tk.LEFT, padx=10)
        tk.Button(self.btn_l, text="🗑 Удалить", fg="red", command=self.delete_files).pack(side=tk.LEFT, padx=2)

        self.btn_r = tk.Frame(self.ctrl, bg="#eeeeee")
        self.btn_r.pack(side=tk.RIGHT, padx=10)
        self.btns_container = tk.Frame(self.btn_r, bg="#eeeeee")
        self.btns_container.pack(side=tk.LEFT)
        self.refresh_buttons()

    def _bind_keys(self):
        self.root.bind("<Left>", lambda e: self.navigate(-1))
        self.root.bind("<Right>", lambda e: self.navigate(1))
        self.root.bind("<Delete>", lambda e: self.delete_files())
        self.root.bind("<Control-KeyPress>", self._undo_ctrl_keypress)
        self.root.bind("r", lambda e: self.rotate_current())
        self.root.bind("R", lambda e: self.rotate_current())
        self.root.bind("к", lambda e: self.rotate_current())
        self.root.bind("К", lambda e: self.rotate_current())
        for i in range(1, 7):
            self.root.bind(str(i), lambda e, x=i: self.move_action(x))
        self.root.bind("<Configure>", lambda e: self.root.after(100, self.refresh_ui) if e.widget == self.root else None)

    def _undo_ctrl_keypress(self, event):
        if not (event.state & 0x0004):
            return
        if event.keycode in _UNDO_PHYS_KEYCODES:
            self.undo_last_action()
            return "break"

    def _async_load_files(self):
        try:
            source = self.config.get('source', '')
            files = self.engine.get_file_list(source)
            self.root.after(0, self._on_files_loaded, files)
        except Exception:
            self.root.after(0, self._on_files_loaded, [])

    def _on_files_loaded(self, files):
        """Вызывается в главном потоке, когда список файлов готов"""
        self.files = files
        
        if not self.files:
            # Если папка пуста
            self.main_label.config(text="Папка пуста или не содержит фото", image="")
            self.fname_label.config(text="")
            self.filmstrip._clear_all()
        else:
            # 1. Устанавливаем начальные индексы
            self.current_idx = 0
            self.selected_indices = {0}
            
            # 2. ЗАПУСКАЕМ ФОНОВОЕ КЭШИРОВАНИЕ ВСЕЙ ПАПКИ
            # Мы запускаем это в отдельном потоке, чтобы само создание очереди задач 
            # не подтормаживало интерфейс при очень больших списках (1000+ фото)
            threading.Thread(
                target=self.engine.precache_all, 
                args=(self.files,), 
                daemon=True
            ).start()
            
            # 3. Обновляем интерфейс (показываем первое фото и ленту)
            self.refresh_ui()
            
            # Принудительно проталкиваем обновление заголовка и текста
            display_text = f"[{self.current_idx + 1} / {len(self.files)}] {self.files[self.current_idx]}"
            self.fname_label.config(text=display_text)
            self.root.title(f"Photo Sorter Pro {APP_VERSION} | {display_text}")

        # Убираем возможные "зависшие" надписи
        self.root.update_idletasks()



    def undo_last_action(self):
        if not self.history: return
        action = self.history.pop()
        restored = []
        for old_path, new_path, fname in action['items']:
            try:
                if os.path.exists(new_path):
                    shutil.move(new_path, old_path)
                    restored.append(fname)
            except OSError:
                pass
        if restored:
            self.files.extend(restored)
            self.files.sort()
            self.current_idx = self.files.index(restored[0])
            self.selected_indices = {self.current_idx}
            self._after_file_list_change()

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
        
        # 1. Мгновенно обновляем текст и заголовок
        display_text = f"[{self.current_idx + 1} / {len(self.files)}] — {self.files[self.current_idx]}"
        self.fname_label.config(text=display_text)
        self.root.title(f"Photo Sorter Pro {APP_VERSION} | {display_text}")

        # 2. Обновляем ленту
        self.filmstrip.refresh(self.files, self.current_idx, self.selected_indices, self.root.winfo_width())

        # 3. АНТИ-ФРИЗ: Большое фото грузим ТОЛЬКО после паузы в 150мс
        if hasattr(self, '_nav_after_id'):
            self.root.after_cancel(self._nav_after_id)
        
        # Если "летим", main_label не трогаем, чтобы не вешать поток
        self._nav_after_id = self.root.after(150, self.show_current)





    def _check_queue(self):
        # 1. Получаем нагрузку
        q_size = self.engine.get_queue_size()
        
        # 2. Мгновенно обновляем текст счётчика
        if q_size > 0:
            self.cache_stat.config(text=f"⚙ LOAD: {q_size}", fg="#ff9800")
        else:
            self.cache_stat.config(text="✓ READY", fg="#00e5ff")
        
        # ПРИНУДИТЕЛЬНОЕ ОБНОВЛЕНИЕ ЭКРАНА (чтобы счётчик не замерзал)
        self.cache_stat.update_idletasks()

        # 3. Обработка готовых миниатюр
        updated = False
        while not self.engine.result_queue.empty():
            try:
                self.engine.result_queue.get_nowait()
                updated = True
            except queue.Empty:
                break
        
        if updated: 
            self.filmstrip.refresh(self.files, self.current_idx, self.selected_indices, self.root.winfo_width())
        
        # 4. Прогресс-бар
        if self.files and self.root.winfo_width() > 10:
            progress = (self.current_idx + 1) / len(self.files)
            try:
                self.prog_bar.config(width=int(self.root.winfo_width() * progress))
            except tk.TclError:
                pass

        # Ставим интервал 50мс для максимальной отзывчивости
        self.root.after(50, self._check_queue)



    def on_thumb_click(self, idx, state):
        self._save_previous_rotations()
        if state & 0x0001: 
            start, end = min(self.current_idx, idx), max(self.current_idx, idx)
            for i in range(start, end + 1): self.selected_indices.add(i)
        elif state & 0x0004: 
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
        
        # Инфо-текст (номер и имя)
        display_text = f"[{self.current_idx + 1} / {len(self.files)}] — {fname}"
        
        # Выводим инфо ТОЛЬКО в черную панель над фото
        self.fname_label.config(text=display_text)
        
        # Заголовок окна теперь всегда чистый и статичный
        self.root.title(f"Photo Sorter Pro {APP_VERSION}")
        
        # Очищаем текст в центре (чтобы не было дублей)
        self.main_label.config(text="") 

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
                    
                    # Устанавливаем фото, текст принудительно пустой
                    self.main_label.config(image=self.current_photo_tk, text="")
            except Exception:
                self.main_label.config(text="Ошибка загрузки", image="")
        
        threading.Thread(target=load_full, daemon=True).start()




    def move_action(self, folder_num):
        dest_path = self.config.get(f"dest{folder_num}")
        if not dest_path or not self.files: return
        to_move = [self.files[i] for i in sorted(self.selected_indices, reverse=True) if i < len(self.files)]
        history_item = {'type': 'move', 'items': []}
        for fname in to_move:
            src = os.path.join(self.config['source'], fname)
            dst = os.path.join(dest_path, fname)
            try:
                self.engine.save_rotation_to_disk(fname)
                shutil.move(src, dst)
                history_item['items'].append((src, dst, fname))
                self.files.remove(fname)
            except OSError:
                pass
        if history_item['items']: self.history.append(history_item)
        self._after_file_list_change()

    def delete_files(self):
        if not self.selected_indices or not self.files: return
        if not messagebox.askyesno("Удаление", "Удалить выбранные?"): return
        to_delete = [self.files[i] for i in sorted(self.selected_indices, reverse=True) if i < len(self.files)]
        trash_path = os.path.abspath(TRASH_DIR)
        if not os.path.exists(trash_path): os.makedirs(trash_path)
        history_item = {'type': 'delete', 'items': []}
        for fname in to_delete:
            src = os.path.join(self.config['source'], fname)
            dst = os.path.join(trash_path, fname)
            try:
                self.engine.clear_cache([fname])
                shutil.move(src, dst)
                history_item['items'].append((src, dst, fname))
                self.files.remove(fname)
            except OSError:
                pass
        if history_item['items']: self.history.append(history_item)
        self._after_file_list_change()

    def _after_file_list_change(self):
        self.filmstrip._clear_all()
        self.selected_indices = set()
        if not self.files:
            self.current_idx = 0
            self.main_label.config(image="", text="Папка пуста")
            self.fname_label.config(text="")
        else:
            if self.current_idx >= len(self.files): self.current_idx = len(self.files) - 1
            self.selected_indices = {self.current_idx}
        self.refresh_ui()

    def open_settings(self):
        SetupWindow(self.root, self.on_settings_changed)

    def on_settings_changed(self, new_config):
        self.config = new_config
        self.engine.current_source = self.config.get('source', '')
        self.current_idx, self.files, self.history = 0, [], []
        self.engine.clear_cache()
        self.filmstrip._clear_all()
        self.root.update_idletasks()
        self.refresh_buttons()
        threading.Thread(target=self._async_load_files, daemon=True).start()

    def refresh_buttons(self):
        for widget in self.btns_container.winfo_children(): widget.destroy()
        if any(self.config.get(f"dest{i}") for i in range(1, 7)):
            tk.Label(self.btns_container, text="В папку:", bg="#eeeeee", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
            for i in range(1, 7):
                path = self.config.get(f"dest{i}", "")
                if path:
                    name = os.path.basename(path.rstrip(os.sep))
                    btn = tk.Button(self.btns_container, text=f"{i}: {name}", padx=8,
                                    command=lambda x=i: self.move_action(x), font=("Arial", 9, "bold"),
                                    bg="#ffffff", relief=tk.GROOVE)
                    btn.pack(side=tk.LEFT, padx=2)

    def refresh_ui(self):
        if not self.files: return
        self.show_current()
        self.filmstrip.refresh(self.files, self.current_idx, self.selected_indices, self.root.winfo_width())

    def on_app_closing(self):
        """Экстренное и полное завершение всех процессов"""
        try:
            # 1. Останавливаем движок
            self.engine.stop_engine()
            
            # 2. Сохраняем последние повороты (быстро)
            fnames = list(self.engine.rotation_map.keys())
            for f in fnames:
                self.engine.save_rotation_to_disk(f)
        except Exception:
            pass
        finally:
            # 3. Убиваем окно
            self.root.destroy()
            # 4. САМОЕ ВАЖНОЕ: Полный выход из Python
            # Это мгновенно прибьет все зависшие фоновые потоки
            os._exit(0) 
