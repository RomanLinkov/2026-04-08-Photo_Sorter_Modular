import tkinter as tk
from data_config import THUMB_SIZE

class PhotoFilmstrip:
    def __init__(self, parent, engine, on_click_callback):
        self.engine = engine
        self.on_click_callback = on_click_callback
        self.start_idx = 0
        self.t_widgets = []
        
        # Храним последнее состояние, чтобы не перерисовывать лишнее
        self.last_state = {} 
        
        # Контейнер ленты
        self.frame = tk.Frame(parent, height=THUMB_SIZE + 20, bg="#1e1e1e")
        self.frame.grid(row=2, column=0, sticky="ew")
        self.frame.pack_propagate(False)
        
        # Создаем 45 постоянных слотов (пул виджетов)
        for _ in range(45):
            c = tk.Frame(self.frame, width=THUMB_SIZE + 6, height=THUMB_SIZE + 6, bg="#1e1e1e")
            c.pack(side=tk.LEFT, padx=2, pady=5)
            c.pack_propagate(False)
            l = tk.Label(c, bg="#1e1e1e")
            l.place(relx=0.5, rely=0.5, anchor="center")
            self.t_widgets.append((c, l))

    def refresh(self, files, current_idx, selected_indices, win_width):
        """Оптимизированная отрисовка ленты"""
        if not files or current_idx >= len(files): # Добавлена проверка индекса
            self._clear_all()
            return
        if current_idx >= len(files):
            return 

        # 1. Расчет видимого диапазона (сколько влезет в ширину окна)
        num_vis = min(len(self.t_widgets), max(1, win_width // (THUMB_SIZE + 10)))
        
        # Автоматическая прокрутка ленты за курсором
        if current_idx >= self.start_idx + num_vis:
            self.start_idx = current_idx - num_vis + 1
        elif current_idx < self.start_idx:
            self.start_idx = current_idx
            
        if self.start_idx + num_vis > len(files):
            self.start_idx = max(0, len(files) - num_vis)

        # 2. Обновление только изменившихся виджетов
        for i, (frame, label) in enumerate(self.t_widgets):
            idx = self.start_idx + i
            if idx < len(files):
                fname = files[idx]
                is_active = (idx == current_idx or idx in selected_indices)
                bg_color = "#ffd600" if is_active else "#1e1e1e"
                
                # Обновляем цвет только если он изменился
                if frame.cget("bg") != bg_color:
                    frame.config(bg=bg_color)
                    label.config(bg=bg_color)

                thumb = self.engine.get_thumb(fname)
                # Обновляем картинку только если она появилась в кэше
                # и не совпадает с тем, что уже установлено в Label
                if thumb:
                    if label.cget("image") != str(thumb):
                        label.config(image=thumb)
                else:
                    label.config(image="")
                    self.engine.request_thumb(fname)

                # Перепривязываем события (необходимо для актуального индекса)
                cb = lambda e, x=idx: self.on_click_callback(x, e.state)
                label.bind("<Button-1>", cb)
                frame.bind("<Button-1>", cb)
            else:
                self._clear_slot(frame, label)

    def _clear_slot(self, frame, label):
        if label.cget("image") or frame.cget("bg") != "#1e1e1e":
            label.config(image="", bg="#1e1e1e")
            frame.config(bg="#1e1e1e")
            label.unbind("<Button-1>")
            frame.unbind("<Button-1>")

    def _clear_all(self):
        for c, l in self.t_widgets:
            self._clear_slot(c, l)
