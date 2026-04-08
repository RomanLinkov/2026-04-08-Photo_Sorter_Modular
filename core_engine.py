import os
import threading
import queue
import hashlib
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageTk, ImageOps
from data_config import THUMB_SIZE, EXTENSIONS, MAX_WORKERS, CACHE_DIR, ensure_cache_dir

class PhotoEngine:
    def __init__(self):
        self.thumb_cache = {}
        self.current_source = ""
        self.lock = threading.Lock()
        self.result_queue = queue.Queue()
        self.executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
        self.rotation_map = {}  # Храним углы поворота {имя_файла: угол}
        ensure_cache_dir()

    def get_file_list(self, source_dir):
        if not source_dir or not os.path.exists(source_dir): 
            return []
        self.current_source = os.path.abspath(source_dir)
        try:
            return sorted([f for f in os.listdir(self.current_source) 
                          if f.lower().endswith(EXTENSIONS)])
        except:
            return []

    def _get_cache_path(self, fname):
        hash_name = hashlib.md5(fname.encode()).hexdigest()
        return os.path.join(CACHE_DIR, f"{hash_name}.png")

    def get_thumb(self, fname):
        with self.lock:
            return self.thumb_cache.get(fname)

    def request_thumb(self, fname):
        self.executor.submit(self._proc_thumb, fname)

    def _proc_thumb(self, fname):
        with self.lock:
            if fname in self.thumb_cache:
                self.result_queue.put(fname)
                return

        cache_path = self._get_cache_path(fname)
        path = os.path.join(self.current_source, fname)
        img = None
        
        try:
            if os.path.exists(cache_path):
                try:
                    img = Image.open(cache_path)
                    img.load()
                except:
                    img = None
                    if os.path.exists(cache_path): os.remove(cache_path)

            if img is None:
                with Image.open(path) as original:
                    original.draft('RGB', (THUMB_SIZE, THUMB_SIZE))
                    img = ImageOps.exif_transpose(original)
                    img.thumbnail((THUMB_SIZE, THUMB_SIZE), Image.Resampling.LANCZOS)
                    img.save(cache_path, "PNG")
            
            # ПРИМЕНЯЕМ ПОВОРОТ ИЗ ПАМЯТИ
            angle = self.rotation_map.get(fname, 0)
            if angle != 0:
                img = img.rotate(angle, expand=True)

            photo = ImageTk.PhotoImage(img)
            with self.lock:
                self.thumb_cache[fname] = photo
            self.result_queue.put(fname)

        except Exception as e:
            print(f"Ошибка миниатюры {fname}: {e}")
        finally:
            if img: img.close()

    def rotate_in_memory(self, fname):
        """Меняет угол поворота только в памяти для мгновенного отклика"""
        current_angle = self.rotation_map.get(fname, 0)
        new_angle = (current_angle - 90) % 360
        self.rotation_map[fname] = new_angle
        with self.lock:
            self.thumb_cache.pop(fname, None)
        return new_angle

    def save_rotation_to_disk(self, fname):
        """Физическое сохранение на диск. Вызываем через executor."""
        # Получаем угол и СРАЗУ удаляем из карты, чтобы не сохранять дважды
        angle = self.rotation_map.pop(fname, 0)
        if angle == 0: return 
        
        path = os.path.join(self.current_source, fname)
        try:
            # Даем файлу 0.1 сек "отдохнуть" (на случай если он еще читается)
            import time
            time.sleep(0.1)
            
            with Image.open(path) as img:
                img = ImageOps.exif_transpose(img)
                rotated = img.rotate(angle, expand=True)
                rotated.save(path, quality=95, subsampling=0)
            
            # Чистим кэш превью
            cache_path = self._get_cache_path(fname)
            if os.path.exists(cache_path): 
                try: os.remove(cache_path)
                except: pass
            print(f"Файл {fname} успешно сохранен с поворотом {angle}")
        except Exception as e:
            print(f"Ошибка физического сохранения {fname}: {e}")



    def clear_cache(self, filenames=None):
        with self.lock:
            if filenames:
                for f in filenames: self.thumb_cache.pop(f, None)
            else:
                self.thumb_cache.clear()
