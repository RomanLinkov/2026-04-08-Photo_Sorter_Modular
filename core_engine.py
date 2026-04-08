import os
import threading
import queue
import hashlib
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageTk, ImageOps
from data_config import THUMB_SIZE, EXTENSIONS, MAX_WORKERS, CACHE_DIR, ensure_dirs

class PhotoEngine:
    def __init__(self):
        self.thumb_cache = {}
        self.current_source = ""
        self.lock = threading.Lock()
        self.result_queue = queue.Queue()
        self.executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
        self.rotation_map = {}  # Храним углы поворота {имя_файла: угол}
        ensure_dirs() # Создаем .photo_cache и .photo_trash

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
        """Загрузка превью с защитой от перегрузки очереди"""
        current_load = self.get_queue_size()
        
        # Если в очереди уже больше 60 задач, новые пока не принимаем
        if current_load < 60:
            self.executor.submit(self._proc_thumb, fname)


    def precache_all(self, files):
        """Закидывает всю папку в очередь на фоновую загрузку миниатюр"""
        for fname in files:
            # Проверяем, нет ли уже этого файла в RAM-кэше
            with self.lock:
                if fname in self.thumb_cache:
                    continue
            # Постепенно наполняем пул потоков
            self.executor.submit(self._proc_thumb, fname)



    def _proc_thumb(self, fname):
        with self.lock:
            if fname in self.thumb_cache:
                self.result_queue.put(fname)
                return

        cache_path = self._get_cache_path(fname)
        path = os.path.join(self.current_source, fname)
        img_to_show = None
        
        try:
            # Пытаемся открыть из кэша
            if os.path.exists(cache_path):
                try:
                    with Image.open(cache_path) as cached_img:
                        img_to_show = cached_img.copy() # Копируем в память и СРАЗУ закрываем файл
                        img_to_show.load()
                except:
                    img_to_show = None
                    try: os.remove(cache_path)
                    except: pass # Если файл занят, просто пропустим удаление в этот раз

            # Если кэша нет - создаем
            if img_to_show is None:
                with Image.open(path) as original:
                    original.draft('RGB', (THUMB_SIZE, THUMB_SIZE))
                    img_to_show = ImageOps.exif_transpose(original)
                    img_to_show.thumbnail((THUMB_SIZE, THUMB_SIZE), Image.Resampling.LANCZOS)
                    img_to_show.save(cache_path, "PNG")
            
            # Поворот в памяти
            angle = self.rotation_map.get(fname, 0)
            if angle != 0:
                img_to_show = img_to_show.rotate(angle, expand=True)

            photo = ImageTk.PhotoImage(img_to_show)
            with self.lock:
                self.thumb_cache[fname] = photo
            self.result_queue.put(fname)

        except Exception as e:
            print(f"Ошибка миниатюры {fname}: {e}")


    def rotate_in_memory(self, fname):
        """Мгновенный поворот в памяти"""
        current_angle = self.rotation_map.get(fname, 0)
        new_angle = (current_angle - 90) % 360
        self.rotation_map[fname] = new_angle
        with self.lock:
            self.thumb_cache.pop(fname, None)
        return new_angle

    def save_rotation_to_disk(self, fname):
        """Физическая запись на диск. Вызывается в фоне."""
        angle = self.rotation_map.pop(fname, 0)
        if angle == 0: return 
        
        path = os.path.join(self.current_source, fname)
        try:
            # Небольшая пауза, чтобы файл освободился GUI-потоком
            import time
            time.sleep(0.1)
            
            with Image.open(path) as img:
                img = ImageOps.exif_transpose(img)
                rotated = img.rotate(angle, expand=True)
                rotated.save(path, quality=95, subsampling=0)
            
            cache_path = self._get_cache_path(fname)
            if os.path.exists(cache_path): 
                try: os.remove(cache_path)
                except: pass
        except Exception as e:
            print(f"Ошибка сохранения {fname}: {e}")

    def clear_cache(self, filenames=None):
        with self.lock:
            if filenames:
                for f in filenames: self.thumb_cache.pop(f, None)
            else:
                self.thumb_cache.clear()

    def get_queue_size(self):
        """Возвращает количество задач в очереди пула потоков"""
        try:
            # Обращаемся к внутренней очереди исполнителя
            return self.executor._work_queue.qsize()
        except:
            return 0
