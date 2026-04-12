import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

def collect_py_to_pdf():
    md_output = "full_project_code.md"
    pdf_output = "full_project_code.pdf"
    
    # 1. Ищем все .py файлы (кроме самого этого скрипта)
    current_script = os.path.basename(__file__)
    files_to_include = [f for f in os.listdir('.') if f.endswith('.py') and f != current_script]
    
    if not files_to_include:
        print("Python файлы не найдены!")
        return

    # 2. Создаем MD с блоками кода ```python
    with open(md_output, 'w', encoding='utf-8') as md_file:
        for f_name in files_to_include:
            md_file.write(f"## File: {f_name}\n```python\n")
            with open(f_name, 'r', encoding='utf-8', errors='replace') as src:
                md_file.write(src.read())
            md_file.write("\n```\n\n")

    # 3. Генерируем PDF
    c = canvas.Canvas(pdf_output, pagesize=letter)
    width, height = letter
    margin = 50
    y = height - margin

    # Шрифт (Arial для кириллицы в комментариях)
    font_path = "C:/Windows/Fonts/arial.ttf"
    font_main = 'Arial' if os.path.exists(font_path) else 'Helvetica'
    if font_main == 'Arial':
        pdfmetrics.registerFont(TTFont('Arial', font_path))

    for f_name in files_to_include:
        # Заголовок файла в PDF (крупно)
        if y < 100:
            c.showPage()
            y = height - margin
            
        c.setFont(font_main, 14)
        c.drawString(margin, y, f"FILE: {f_name}")
        y -= 25
        
        # Контент файла (мелко, как код)
        c.setFont(font_main, 8)
        with open(f_name, 'r', encoding='utf-8', errors='replace') as f:
            for line in f.read().splitlines():
                # Заменяем табы на пробелы, чтобы верстка не ехала
                clean_line = line.replace('\t', '    ')
                # Разбиваем длинные строки кода
                wrapped = simpleSplit(clean_line, font_main, 8, width - 2*margin)
                
                for w_line in wrapped:
                    if y < 40:
                        c.showPage()
                        y = height - margin
                        c.setFont(font_main, 8)
                    
                    c.drawString(margin, y, w_line)
                    y -= 10
        y -= 20 # Отступ перед следующим файлом

    c.save()
    print(f"Готово! Собрано {len(files_to_include)} .py файлов.")
    print(f"Файлы: {md_output} и {pdf_output}")

if __name__ == "__main__":
    collect_py_to_pdf()
