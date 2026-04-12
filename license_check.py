"""Проверка лицензии и окно активации (HWID + ключ)."""
import base64
import hashlib
import os
import subprocess
import sys
import webbrowser
import tkinter as tk
from tkinter import messagebox

from PIL import Image, ImageTk


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


def _license_paths():
    if getattr(sys, "frozen", False):
        base_path = os.path.dirname(sys.executable)
        static_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
        static_path = base_path
    license_path = os.path.join(base_path, "license.txt")
    return license_path, static_path


def check_license_gui():
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

    act_win = tk.Tk()
    act_win.title("Активация Photo Sorter Pro")
    act_win.geometry("550x850")
    act_win.configure(bg="#1e1e1e")
    act_win.resizable(False, False)

    tk.Label(act_win, text="ЛИЦЕНЗИЯ НЕ НАЙДЕНА", fg="#ff5555", bg="#1e1e1e",
             font=("Arial", 18, "bold")).pack(pady=20)

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
