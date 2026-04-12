"""Проверка лицензии и окно активации (HWID + ключ)."""
import base64
import hashlib
import json
import os
import subprocess
import sys
import webbrowser
import tkinter as tk
from tkinter import messagebox

from PIL import Image, ImageTk


def _crypt_value(val):
    # Простейшая маскировка: число -> строка -> байты -> base64
    s = f"secret_prefix_{val}_suffix"
    return base64.b64encode(s.encode()).decode()

def _decrypt_value(crypt_str):
    try:
        decoded = base64.b64decode(crypt_str.encode()).decode()
        # Извлекаем число между префиксами
        return int(decoded.split("_")[2])
    except:
        return 0

def get_trial_actions_used():
    path = _trial_state_path()
    if not os.path.exists(path): return 0
    try:
        with open(path, "r") as f:
            data = json.load(f)
            return _decrypt_value(data.get("token", ""))
    except:
        return 0

def add_trial_actions(n):
    path = _trial_state_path()
    used = get_trial_actions_used() + n
    try:
        with open(path, "w") as f:
            # Сохраняем замаскированное значение
            json.dump({"token": _crypt_value(used)}, f)
    except OSError:
        pass
    return used


def check_license_gui(*, trial_expired=False):
    current_hwid = get_hwid()
    valid_key = generate_key(current_hwid)
    license_path, static_path = _license_paths()
    status = {"activated": False, "continue_trial": False} # Добавляем флаг продолжения

    def verify_and_save():
        # ... (код верификации остается прежним из PDF стр. 13)
        if entered_key == valid_key:
            # ... сохранение ...
            status["activated"] = True
            act_win.destroy()

    def continue_free():
        status["continue_trial"] = True
        act_win.destroy()

    # --- Создание окна ---
    act_win = tk.Tk()
    # ... (настройки окна из PDF стр. 14) ...

    # КНОПКА ПРОДОЛЖИТЬ (показываем, только если лимит не исчерпан)
    used = get_trial_actions_used()
    if used < FREE_ACTION_LIMIT:
        remains = FREE_ACTION_LIMIT - used
        btn_trial = tk.Button(
            act_win, 
            text=f"ПРОДОЛЖИТЬ ПРОБНЫЙ ПЕРИОД\n(осталось {remains} действий)", 
            command=continue_free,
            bg="#333333", fg="#00e5ff", font=("Arial", 11, "bold"), pady=10
        )
        btn_trial.pack(pady=10, padx=50, fill="x")
    
    # КНОПКА АКТИВАЦИИ (основная)
    tk.Button(act_win, text="АКТИВИРОВАТЬ ПРОГРАММУ", command=verify_and_save,
              bg="#1a5a1a", fg="white", font=("Arial", 11, "bold"), relief="flat").pack(
              pady=10, padx=50, fill="x")

    act_win.mainloop()
    return status["activated"] or status["continue_trial"]


# Сколько фото можно переместить/удалить без ключа, затем требуется активация
FREE_ACTION_LIMIT = 1000
_TRIAL_STATE_NAME = "photo_sorter_trial.json"


def get_encoded_salt():
    return base64.b64decode("TVlfU1VQRVJfU0VDUkVUX1BST0pFQ1RfMjAyNA==").decode()


def get_hwid():
    """ID процессора: wmic, при сбое — Get-CimInstance (без устаревшего wmic в новых Windows)."""
    _no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        output = subprocess.check_output(
            ["wmic", "cpu", "get", "processorid"],
            stderr=subprocess.DEVNULL,
            timeout=20,
            creationflags=_no_window,
        ).decode(errors="replace")
        hwid = output.replace("ProcessorId", "").replace("\r", "").strip()
        if hwid:
            return hwid
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pass
    if sys.platform == "win32":
        try:
            out = subprocess.check_output(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "(Get-CimInstance Win32_Processor).ProcessorId",
                ],
                stderr=subprocess.DEVNULL,
                timeout=25,
                creationflags=_no_window,
            ).decode(errors="replace").strip()
            if out:
                return out
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass
    return "UNKNOWN_DEVICE"


def generate_key(hwid):
    secret_salt = get_encoded_salt()
    raw_string = f"{hwid}-{secret_salt}"
    return hashlib.sha256(raw_string.encode()).hexdigest()


def _base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _license_paths():
    base_path = _base_dir()
    if getattr(sys, "frozen", False):
        static_path = sys._MEIPASS
    else:
        static_path = base_path
    license_path = os.path.join(base_path, "license.txt")
    return license_path, static_path


def _trial_state_path():
    return os.path.join(_base_dir(), _TRIAL_STATE_NAME)


def is_license_valid():
    license_path, _ = _license_paths()
    current_hwid = get_hwid()
    valid_key = generate_key(current_hwid)
    try:
        if os.path.exists(license_path):
            with open(license_path, "r", encoding="utf-8") as f:
                if f.read().strip() == valid_key:
                    return True
    except (OSError, UnicodeDecodeError):
        pass
    return False


def get_trial_actions_used():
    path = _trial_state_path()
    if not os.path.exists(path):
        return 0
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return int(data.get("actions_used", 0))
    except (OSError, ValueError, json.JSONDecodeError, TypeError):
        return 0


def add_trial_actions(n):
    """Учитывает успешно перемещённые/удалённые фото (без лицензии)."""
    if n <= 0 or is_license_valid():
        return get_trial_actions_used()
    path = _trial_state_path()
    used = get_trial_actions_used() + n
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"actions_used": used}, f, ensure_ascii=False, indent=2)
    except OSError:
        pass
    return used


def startup_license_gate():
    """Перед главным окном: лицензия или триал < лимита, иначе окно активации."""
    if is_license_valid():
        return True
    if get_trial_actions_used() < FREE_ACTION_LIMIT:
        return True
    return check_license_gui(trial_expired=False)



def enforce_trial_before_action():
    """Перед перемещением/удалением: если лимит уже исчерпан — только активация."""
    if is_license_valid():
        return True
    if get_trial_actions_used() < FREE_ACTION_LIMIT:
        return True
    ok = check_license_gui(trial_expired=True)
    if not ok:
        os._exit(0)
    return True


def guard_after_photo_actions(committed_count):
    """После успешных move/delete: учёт триала; при достижении лимита — окно активации."""
    if committed_count <= 0:
        return
    if is_license_valid():
        return
    total = add_trial_actions(committed_count)
    if total >= FREE_ACTION_LIMIT:
        if not check_license_gui(trial_expired=True):
            os._exit(0)


def check_license_gui(*, trial_expired=False):
    current_hwid = get_hwid()
    valid_key = generate_key(current_hwid)
    license_path, static_path = _license_paths()
    status = {"activated": False}

    def verify_and_save():
        entered_key = key_entry.get().strip()
        if entered_key == valid_key:
            try:
                with open(license_path, "w", encoding="utf-8") as f:
                    f.write(entered_key)
                status["activated"] = True
                act_win.destroy()
            except OSError as e:
                messagebox.showerror("Ошибка", f"Не удалось сохранить лицензию: {e}")
        else:
            messagebox.showerror("Ошибка", "Неверный ключ лицензии! Проверьте ID.")

    def do_copy_id():
        act_win.clipboard_clear()
        act_win.clipboard_append(current_hwid)
        btn_copy_id.config(text="✅ ID СКОПИРОВАН", fg="#55ff55")

    def do_clear_key():
        key_entry.delete(0, tk.END)
        btn_paste.config(text="📋 ВСТАВИТЬ", fg="white")

    def do_paste_key():
        try:
            content = act_win.clipboard_get().strip()
            key_entry.delete(0, tk.END)
            key_entry.insert(0, content)
            btn_paste.config(text="✅", fg="#55ff55")
        except tk.TclError:
            messagebox.showerror("Ошибка", "Буфер обмена пуст!")

    def do_copy_email():
        act_win.clipboard_clear()
        act_win.clipboard_append("roman.linkov@vk.com")
        btn_copy_mail.config(text="✅", fg="#55ff55")

    try:
        if os.path.exists(license_path):
            with open(license_path, "r", encoding="utf-8") as f:
                if f.read().strip() == valid_key:
                    return True
    except (OSError, UnicodeDecodeError):
        pass

    headline = (
        "ЛИМИТ БЕСПЛАТНОЙ ОБРАБОТКИ ИСЧЕРПАН"
        if trial_expired
        else "ЛИЦЕНЗИЯ НЕ НАЙДЕНА"
    )
    sub = (
        f"Обработано без ключа: {FREE_ACTION_LIMIT} фото. Введите ключ или купите лицензию."
        if trial_expired
        else ""
    )

    act_win = tk.Tk()
    act_win.title("Активация Photo Sorter Pro")
    act_win.geometry("550x850")
    act_win.configure(bg="#1e1e1e")
    act_win.resizable(False, False)

    tk.Label(act_win, text=headline, fg="#ff5555", bg="#1e1e1e",
             font=("Arial", 16, "bold"), wraplength=500).pack(pady=20)
    if sub:
        tk.Label(act_win, text=sub, fg="#cccccc", bg="#1e1e1e",
                 font=("Arial", 10), justify="center", wraplength=500).pack(pady=(0, 10))

    tk.Label(act_win, text="Ваш ID оборудования:", fg="#aaaaaa", bg="#1e1e1e").pack()
    id_entry = tk.Entry(act_win, justify="center", font=("Consolas", 14, "bold"),
                        fg="#ffff00", bg="black", readonlybackground="black", relief="flat")
    id_entry.insert(0, current_hwid)
    id_entry.config(state="readonly")
    id_entry.pack(pady=5, padx=50, fill="x")

    btn_copy_id = tk.Button(act_win, text="КОПИРОВАТЬ ID", command=do_copy_id,
                            bg="#333333", fg="white", font=("Arial", 11, "bold"), relief="flat")
    btn_copy_id.pack(pady=5, padx=50, fill="x")

    tk.Frame(act_win, height=1, bg="#444444").pack(fill="x", padx=50, pady=20)

    tk.Label(
        act_win,
        text="Чтобы получить ключ активации, скопируйте ID оборудования\n"
        "(указан выше) и отправьте его автору удобным для вас способом:",
        fg="white",
        bg="#1e1e1e",
        font=("Arial", 11),
        justify="center",
    ).pack(pady=10)

    tk.Button(act_win, text="Telegram: @ROMAN_LINKOV95", fg="#55aaff", bg="#1e1e1e",
              font=("Arial", 12, "underline"), relief="flat", cursor="hand2",
              command=lambda: webbrowser.open("https://t.me")).pack()

    tk.Button(act_win, text="VK: roman.linkov", fg="#55aaff", bg="#1e1e1e",
              font=("Arial", 12, "underline"), relief="flat", cursor="hand2",
              command=lambda: webbrowser.open("https://vk.com")).pack()

    email_frame = tk.Frame(act_win, bg="#1e1e1e")
    email_frame.pack(pady=10)
    tk.Label(email_frame, text="Email: roman.linkov@vk.com", fg="#aaaaaa", bg="#1e1e1e",
             font=("Arial", 11)).pack(side="left")
    btn_copy_mail = tk.Button(email_frame, text="📋", command=do_copy_email, bg="#333333",
                              fg="white", relief="flat", font=("Arial", 8))
    btn_copy_mail.pack(side="left", padx=10)

    try:
        qr_path = os.path.join(static_path, "tg_qr.png")
        if os.path.exists(qr_path):
            img = Image.open(qr_path)
            img.thumbnail((180, 180), Image.Resampling.LANCZOS)
            qr_img = ImageTk.PhotoImage(img)
            qr_label = tk.Label(act_win, image=qr_img, bg="#1e1e1e")
            qr_label.image = qr_img
            qr_label.pack(pady=15)
    except Exception:
        pass

    tk.Frame(act_win, height=1, bg="#444444").pack(fill="x", padx=50, pady=15)

    tk.Label(act_win, text="Введите ключ активации:", fg="#55ff55", bg="#1e1e1e",
             font=("Arial", 11, "bold")).pack(pady=5)

    key_frame = tk.Frame(act_win, bg="#1e1e1e")
    key_frame.pack(pady=5, padx=50, fill="x")

    key_entry = tk.Entry(key_frame, justify="center", font=("Consolas", 10), fg="white",
                         bg="#333333", relief="flat")
    key_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

    btn_paste = tk.Button(key_frame, text="📋 ВСТАВИТЬ", command=do_paste_key, bg="#444444",
                          fg="white", font=("Arial", 8, "bold"), relief="flat", padx=10)
    btn_paste.pack(side="right")

    tk.Button(act_win, text="АКТИВИРОВАТЬ ПРОГРАММУ", command=verify_and_save,
              bg="#1a5a1a", fg="white", font=("Arial", 11, "bold"), relief="flat").pack(
        pady=10, padx=50, fill="x")

    act_win.update_idletasks()
    x = (act_win.winfo_screenwidth() // 2) - (act_win.winfo_width() // 2)
    y = (act_win.winfo_screenheight() // 2) - (act_win.winfo_height() // 2)
    act_win.geometry(f"+{x}+{y}")

    act_win.protocol("WM_DELETE_WINDOW", lambda: os._exit(0))
    act_win.mainloop()
    return status["activated"]
