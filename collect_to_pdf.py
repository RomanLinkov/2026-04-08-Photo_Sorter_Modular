import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

def collect_project():
    files_to_include = [
        'app_entrypoint.py', 'app_ui.py', 'core_engine.py', 
        'app_filmstrip.py', 'data_config.py', 'requirements.txt', 'readme.md'
    ]
    md_output = "full_project.md"
    pdf_output = "full_project.pdf"

    # 1. Сначала создаем MD (на всякий случай)
    with open(md_output, 'w', encoding='utf-8') as md_file:
        for f_name in files_to_include:
            if os.path.exists(f_name):
                md_file.write(f"## File: {f_name}\n```python\n")
                with open(f_name, 'r', encoding='utf-8', errors='replace') as src:
                    md_file.write(src.read())
                md_file.write("\n```\n\n")

    # 2. Генерируем PDF
    c = canvas.Canvas(pdf_output, pagesize=letter)
    width, height = letter
    y = height - 50
    margin = 50

    # Регистрируем шрифт с поддержкой кириллицы
    font_path = "C:/Windows/Fonts/arial.ttf" # Путь для Windows
    if os.path.exists(font_path):
        pdfmetrics.registerFont(TTFont('Arial', font_path))
        font_main = 'Arial'
    else:
        font_main = 'Helvetica' # Без Arial кириллица может не отобразиться

    c.setFont(font_main, 10)

    for f_name in files_to_include:
        if not os.path.exists(f_name): continue
        
        # Заголовок файла в PDF
        c.setFont(font_main, 14)
        c.drawString(margin, y, f"FILE: {f_name}")
        y -= 25
        c.setFont(font_main, 8)

        with open(f_name, 'r', encoding='utf-8', errors='replace') as f:
            for line in f.read().splitlines():
                if y < 50:
                    c.showPage()
                    y = height - 50
                    c.setFont(font_main, 8)
                
                clean_line = line.replace('\t', '    ')
                wrapped = simpleSplit(clean_line, font_main, 8, width - 2*margin)
                for w_line in wrapped:
                    c.drawString(margin, y, w_line)
                    y -= 10
        y -= 20 # Отступ перед следующим файлом

    c.save()
    print(f"Готово!\nСоздан MD: {md_output}\nСоздан PDF: {pdf_output}")

if __name__ == "__main__":
    collect_project()
