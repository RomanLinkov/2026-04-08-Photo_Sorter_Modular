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

# Сколько фото можно переместить/удалить без ключа, затем требуется активация
FREE_ACTION_LIMIT = 1000
_REG_VENDOR = "PhotoSorterPro"
_REG_APP = "PhotoSorterPro"
_REG_VALUE_ACTIONS_USED = "ActionsUsed"


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
        hwid = output.replace("ProcessorId", "").replace("\r", "")
        for line in hwid.splitlines():
            s = line.strip()
            if s:
                return s
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
            ).decode(errors="replace")
            for line in out.splitlines():
                s = line.strip()
                if s:
                    return s
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


def _trial_reg_key_path():
    # Стандартный путь для пользовательских настроек/состояния приложения в Windows.
    return rf"Software\{_REG_VENDOR}\{_REG_APP}"


def _try_read_trial_actions_from_registry() -> int | None:
    if sys.platform != "win32":
        return None
    try:
        import winreg  # type: ignore

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _trial_reg_key_path(), 0, winreg.KEY_READ) as k:
            val, reg_type = winreg.QueryValueEx(k, _REG_VALUE_ACTIONS_USED)
        if reg_type not in (winreg.REG_DWORD, winreg.REG_QWORD, winreg.REG_SZ):
            return 0
        try:
            return int(val)
        except (TypeError, ValueError):
            return 0
    except FileNotFoundError:
        return None
    except OSError:
        return None


def _try_write_trial_actions_to_registry(n: int) -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg  # type: ignore

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _trial_reg_key_path()) as k:
            winreg.SetValueEx(k, _REG_VALUE_ACTIONS_USED, 0, winreg.REG_DWORD, int(n))
        return True
    except OSError:
        return False


def _license_paths():
    base_path = _base_dir()
    if getattr(sys, "frozen", False):
        static_path = sys._MEIPASS
    else:
        static_path = base_path
    license_path = os.path.join(base_path, "license.txt")
    return license_path, static_path


def _read_saved_license_key(license_path):
    try:
        with open(license_path, "r", encoding="utf-8-sig") as f:
            return f.read().strip()
    except (OSError, UnicodeDecodeError):
        return ""


def is_license_valid():
    license_path, _ = _license_paths()
    current_hwid = get_hwid()
    valid_key = generate_key(current_hwid)
    if os.path.exists(license_path):
        return _read_saved_license_key(license_path) == valid_key
    return False


def get_trial_actions_used():
    # Храним только в реестре (Windows HKCU). Никаких файлов рядом с exe.
    reg_val = _try_read_trial_actions_from_registry()
    if reg_val is None:
        return 0
    return max(0, int(reg_val))


def add_trial_actions(n):
    """Учитывает успешно перемещённые/удалённые фото (без лицензии)."""
    if n <= 0 or is_license_valid():
        return get_trial_actions_used()
    used = get_trial_actions_used() + n

    # Windows: пишем в реестр.
    _try_write_trial_actions_to_registry(used)
    return used


def startup_license_gate():
    """Перед главным окном: лицензия или триал < лимита, иначе окно активации."""
    if is_license_valid():
        return True
    if get_trial_actions_used() < FREE_ACTION_LIMIT:
        return True
    return check_license_gui(trial_expired=True, master=None)


def enforce_trial_before_action(*, master=None):
    """Перед перемещением/удалением: если лимит уже исчерпан — только активация."""
    if is_license_valid():
        return True
    if get_trial_actions_used() < FREE_ACTION_LIMIT:
        return True
    ok = check_license_gui(trial_expired=True, master=master)
    if not ok:
        os._exit(0)
    return True


def guard_after_photo_actions(committed_count, *, master=None):
    """После успешных move/delete: учёт триала; при достижении лимита — окно активации."""
    if committed_count <= 0:
        return
    if is_license_valid():
        return
    total = add_trial_actions(committed_count)
    if total >= FREE_ACTION_LIMIT:
        if not check_license_gui(trial_expired=True, master=master):
            os._exit(0)


def dev_set_trial_actions_used_for_testing(count: int = 999) -> bool:
    """Временно: счётчик триала для проверки блокировки. Только PHOTOSORTER_DEV=1."""
    if os.environ.get("PHOTOSORTER_DEV", "").strip() != "1":
        return False
    try:
        n = int(count)
    except (TypeError, ValueError):
        return False
    n = max(0, min(n, FREE_ACTION_LIMIT))
    return _try_write_trial_actions_to_registry(n)


def maybe_show_trial_offer_dialog(master, *, on_after_activation=None):
    if is_license_valid():
        return
    if get_trial_actions_used() >= FREE_ACTION_LIMIT:
        return
    show_trial_offer_dialog(master, on_after_activation=on_after_activation)


def show_trial_offer_dialog(master, *, on_after_activation=None):
    """Пробный режим: купить/активировать или продолжить бесплатный лимит."""
    current_hwid = get_hwid()
    _, static_path = _license_paths()
    used = get_trial_actions_used()
    remains = max(0, FREE_ACTION_LIMIT - used)

    win = tk.Toplevel(master)
    win.title("Photo Sorter Pro — пробный режим")
    win.configure(bg="#1e1e1e")
    win.resizable(False, False)
    win.transient(master)
    win.grab_set()

    tk.Label(
        win,
        text="Пробная версия",
        fg="#00e5ff",
        bg="#1e1e1e",
        font=("Arial", 18, "bold"),
    ).pack(pady=(16, 8))

    tk.Label(
        win,
        text=(
            f"Без ключа можно обработать до {FREE_ACTION_LIMIT} фотографий "
            f"(перенос и удаление). Сейчас осталось: {remains}.\n\n"
            "Можно сразу купить лицензию и получить ключ — или продолжить "
            "бесплатно до исчерпания лимита."
        ),
        fg="#cccccc",
        bg="#1e1e1e",
        font=("Arial", 10),
        justify="center",
        wraplength=480,
    ).pack(pady=(0, 12), padx=24)

    tk.Frame(win, height=1, bg="#444444").pack(fill="x", padx=40, pady=8)

    tk.Label(
        win,
        text="Купить лицензию — свяжитесь с автором",
        fg="#ffffff",
        bg="#1e1e1e",
        font=("Arial", 11, "bold"),
    ).pack(pady=(4, 6))

    tk.Label(win, text="Ваш ID оборудования (для ключа):", fg="#aaaaaa", bg="#1e1e1e").pack()
    id_entry = tk.Entry(
        win,
        justify="center",
        font=("Consolas", 11, "bold"),
        fg="#ffff00",
        bg="black",
        readonlybackground="black",
        relief="flat",
    )
    id_entry.insert(0, current_hwid)
    id_entry.config(state="readonly")
    id_entry.pack(pady=4, padx=40, fill="x")

    def copy_id():
        win.clipboard_clear()
        win.clipboard_append(current_hwid)
        btn_copy_id.config(text="✅ Скопировано", fg="#55ff55")

    btn_copy_id = tk.Button(
        win,
        text="КОПИРОВАТЬ ID",
        command=copy_id,
        bg="#333333",
        fg="white",
        font=("Arial", 10, "bold"),
        relief="flat",
    )
    btn_copy_id.pack(pady=4, padx=40, fill="x")

    tk.Button(
        win,
        text="Telegram: @ROMAN_LINKOV95",
        fg="#55aaff",
        bg="#1e1e1e",
        font=("Arial", 11, "underline"),
        relief="flat",
        cursor="hand2",
        command=lambda: webbrowser.open("https://t.me"),
    ).pack(pady=2)

    tk.Button(
        win,
        text="VK: roman.linkov",
        fg="#55aaff",
        bg="#1e1e1e",
        font=("Arial", 11, "underline"),
        relief="flat",
        cursor="hand2",
        command=lambda: webbrowser.open("https://vk.com"),
    ).pack(pady=2)

    def copy_mail():
        win.clipboard_clear()
        win.clipboard_append("roman.linkov@vk.com")
        btn_mail.config(text="✅ Email скопирован", fg="#55ff55")

    email_row = tk.Frame(win, bg="#1e1e1e")
    email_row.pack(pady=6)
    tk.Label(
        email_row,
        text="Email: roman.linkov@vk.com",
        fg="#aaaaaa",
        bg="#1e1e1e",
        font=("Arial", 10),
    ).pack(side=tk.LEFT)
    btn_mail = tk.Button(
        email_row,
        text="📋",
        command=copy_mail,
        bg="#333333",
        fg="white",
        relief="flat",
        font=("Arial", 8),
    )
    btn_mail.pack(side=tk.LEFT, padx=8)

    try:
        qr_path = os.path.join(static_path, "tg_qr.png")
        if os.path.exists(qr_path):
            img = Image.open(qr_path)
            img.thumbnail((140, 140), Image.Resampling.LANCZOS)
            qr_img = ImageTk.PhotoImage(img)
            qr_label = tk.Label(win, image=qr_img, bg="#1e1e1e")
            qr_label.image = qr_img
            qr_label.pack(pady=8)
    except Exception:
        pass

    tk.Frame(win, height=1, bg="#444444").pack(fill="x", padx=40, pady=10)

    def close_offer():
        win.grab_release()
        win.destroy()

    def open_activation():
        close_offer()
        master.update_idletasks()
        if check_license_gui(trial_expired=False, master=master):
            if on_after_activation:
                on_after_activation()

    tk.Button(
        win,
        text="Ввести ключ активации",
        command=open_activation,
        bg="#1a5a1a",
        fg="white",
        font=("Arial", 11, "bold"),
        relief="flat",
    ).pack(pady=6, padx=40, fill="x")

    tk.Button(
        win,
        text=f"Продолжить бесплатно (ещё {remains} фото)",
        command=close_offer,
        bg="#333333",
        fg="#00e5ff",
        font=("Arial", 11, "bold"),
        relief="flat",
    ).pack(pady=(4, 16), padx=40, fill="x")

    win.protocol("WM_DELETE_WINDOW", close_offer)

    win.update_idletasks()
    ww = max(520, win.winfo_reqwidth())
    hh = max(480, win.winfo_reqheight())
    win.geometry(f"{ww}x{hh}")
    win.update_idletasks()
    x = (win.winfo_screenwidth() // 2) - (win.winfo_width() // 2)
    y = (win.winfo_screenheight() // 2) - (win.winfo_height() // 2)
    win.geometry(f"{ww}x{hh}+{x}+{y}")
    win.lift()
    win.focus_force()
    master.wait_window(win)


def check_license_gui(*, trial_expired=False, master=None):
    current_hwid = get_hwid()
    valid_key = generate_key(current_hwid)
    license_path, static_path = _license_paths()
    status = {"activated": False}

    def verify_and_save():
        entered_key = key_entry.get().strip()
        if entered_key == valid_key:
            try:
                with open(license_path, "w", encoding="utf-8", newline="\n") as f:
                    f.write(entered_key)
                status["activated"] = True
                act_win.destroy()
            except OSError as e:
                messagebox.showerror(
                    "Ошибка", f"Не удалось сохранить лицензию: {e}", parent=act_win
                )
        else:
            messagebox.showerror(
                "Ошибка", "Неверный ключ лицензии! Проверьте ID.", parent=act_win
            )

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
            messagebox.showerror("Ошибка", "Буфер обмена пуст!", parent=act_win)

    def do_copy_email():
        act_win.clipboard_clear()
        act_win.clipboard_append("roman.linkov@vk.com")
        btn_copy_mail.config(text="✅", fg="#55ff55")

    if os.path.exists(license_path) and _read_saved_license_key(license_path) == valid_key:
        return True

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

    use_toplevel = master is not None
    if use_toplevel:
        act_win = tk.Toplevel(master)
        act_win.transient(master)
        act_win.grab_set()
    else:
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
    act_win.lift()
    act_win.focus_force()
    if use_toplevel:
        master.wait_window(act_win)
    else:
        act_win.mainloop()
    return status["activated"]
