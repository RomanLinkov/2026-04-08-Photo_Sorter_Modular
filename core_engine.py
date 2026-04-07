import os
import shutil
from PIL import Image, ImageTk
from data_config import THUMB_SIZE, EXTENSIONS

class PhotoEngine:
    def __init__(self):
        self.thumb_cache = {}
        self.last_actions = [] # Для Undo

    def get_file_list(self, source_dir):
        if not source_dir or not os.path.exists(source_dir): 
            return []
        return sorted([f for f in os.listdir(source_dir) if f.lower().endswith(EXTENSIONS)])

    def get_thumb(self, source_dir, fname):
        if fname not in self.thumb_cache:
            try:
                full_path = os.path.join(source_dir, fname)
                img = Image.open(full_path)
                img.thumbnail((THUMB_SIZE, THUMB_SIZE))
                self.thumb_cache[fname] = ImageTk.PhotoImage(img)
            except Exception as e: 
                print(f"Ошибка превью для {fname}: {e}")
                return None
        return self.thumb_cache[fname]

    def move_files(self, filenames, src_dir, dst_dir):
        batch = []
        for f in filenames:
            src = os.path.join(src_dir, f)
            dst = os.path.join(dst_dir, f)
            try:
                shutil.move(src, dst)
                batch.append((dst, src))
            except Exception as e:
                print(f"Ошибка перемещения {f}: {e}")
                continue
        if batch: 
            self.last_actions.append(batch)

    def undo_last(self):
        if not self.last_actions: 
            return False
        for curr, orig in self.last_actions.pop():
            try: 
                shutil.move(curr, orig)
            except: 
                continue
        return True
