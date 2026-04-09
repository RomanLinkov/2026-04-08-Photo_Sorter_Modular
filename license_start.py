import subprocess
import hashlib
import sys

def get_hwid():
    """Достаем уникальный ID процессора"""
    try:
        cmd = "wmic cpu get processorid"
        # Выполняем команду и очищаем результат от лишних пробелов
        hwid = subprocess.check_output(cmd, shell=True).decode().split()
        return hwid[1] if len(hwid) > 1 else "UNKNOWN_DEVICE"
    except Exception:
        return "UNKNOWN_DEVICE"

def generate_key(hwid):
    """Шифруем ID в лицензионный ключ"""
    secret_salt = "MY_SUPER_SECRET_PROJECT_2024" # Твоя секретная соль
    raw_string = f"{hwid}-{secret_salt}"
    return hashlib.sha256(raw_string.encode()).hexdigest()

def check_license():
    current_hwid = get_hwid()
    valid_key = generate_key(current_hwid)
    
    print(f"--- СИСТЕМА ЛИЦЕНЗИРОВАНИЯ ---")
    print(f"Ваш HWID: {current_hwid}")

    try:
        with open("license.txt", "r") as f:
            user_key = f.read().strip()
    except FileNotFoundError:
        user_key = ""

    if user_key == valid_key:
        print("✅ СТАТУС: Лицензия активна!")
        print("Запуск основного модуля Photo Sorter...")
        return True
    else:
        print("❌ СТАТУС: Лицензия не найдена или неверна.")
        print(f"Для активации создайте файл license.txt и вставьте туда ключ.")
        print(f"Ваш ключ для этого ПК: {valid_key}") # Выводим его, чтобы ты мог сам его скопировать
        return False

if __name__ == "__main__":
    if check_license():
        # Тут будет вызов твоей основной функции из главного файла
        print("\n[Программа работает...]")
    else:
        print("\n[Программа остановлена]")
        # sys.exit() # Раскомментируй, когда будешь делать .exe
