import os
import re
from pdfminer.high_level import extract_text as pdfminer_extract
import pytesseract
from PIL import Image
import pandas as pd
import docx
import win32com.client as wc
from PyPDF2 import PdfReader
import warnings
from pdf2image import convert_from_path
from PyPDF2 import PdfReader, PdfWriter


data_dir = r"C:\Users\User\PycharmProjects\Hueton\hackaton\hackaton"

poppler_path = r"C:\Users\User\Downloads\poppler-24.08.0\Library\bin\pdftoppm.exe"
pytesseract.pytesseract.tesseract_cmd = r"C:\Users\User\Downloads\tesseract-ocr-w64-setup-5.5.0.20241111.exe"


def check_cropbox(file_path):
    with open(file_path, 'rb') as f:
        reader = PdfReader(f)

        for page in reader.pages:
            if '/CropBox' not in page:
                warnings.warn("CropBox missing, using MediaBox") # чекните
    return pdfminer_extract(file_path)


def fix_cropbox(file_path):
    reader = PdfReader(file_path)
    writer = PdfWriter()

    for page in reader.pages:
        if '/CropBox' not in page:
            page.cropbox = page.mediabox
        writer.add_page(page)

    fixed_path = os.path.join(os.path.dirname(file_path), "fixed_" + os.path.basename(file_path))
    with open(fixed_path, 'wb') as f:
        writer.write(f)
    return fixed_path


def pdf(file_path):
    try:
        fixed_path = fix_cropbox(file_path)
        text = pdfminer_extract(fixed_path)

        if not text.strip():
            print("Текст пустой, запускаем OCR...")
            return pdf_c_ocr(fixed_path)
        return text

    except Exception as e:
        print(f"Ошибка PDF: {e}")
        return ""


def pdf_c_ocr(file_path):
    try:
        images = convert_from_path(file_path, dpi=300, poppler_path=poppler_path)
        text = ""
        for i, img in enumerate(images):
            try:
                text += pytesseract.image_to_string(img, lang='rus+eng') + "\n"

            except Exception as ocr_error:
                print(f"OCR ошибка на странице {i + 1}: {ocr_error}")
        return text

    except Exception as e:
        print(f"Ошибка конвертации PDF в изображение: {e}")
        return ""


def doc(file_path):
    try:
        print(f"Извлечение из doc {file_path}")
        word = wc.Dispatch("Word.Application")
        doc = word.Documents.Open(file_path)
        new_path = os.path.splitext(file_path)[0] + ".docx"
        doc.SaveAs2(new_path, FileFormat=16) # 16 = docx формат
        doc.Close()
        word.Quit()
        return docx_text(new_path)

    except Exception as e:
        print(f"Ошибка конвертации doc: {e}")
        return ""


def docx_text(file_path):
    try:
        doc = docx.Document(file_path)
        return "\n".join([para.text for para in doc.paragraphs])

    except Exception as e:
        print(f"Ошибка чтения docx: {e}")
        return ""


def excel(file_path):
    try:
        text = ""
        dfs = pd.read_excel(file_path, sheet_name=None)

        for sheet, df in dfs.items():
            df = df.map(lambda x: '' if pd.isna(x) else x)
            text += f"Лист: {sheet}\n{df.to_string()}\n\n"
        return text

    except Exception as e:
        print(f"Excel ошибка: {e}")
        return ""


def all_text(file_path):
    if file_path.lower().endswith('.pdf'):
        return pdf(file_path)

    elif file_path.lower().endswith('.docx'):
        return docx_text(file_path)

    elif file_path.lower().endswith('.doc'):
        return doc(file_path)

    elif file_path.lower().endswith('.xlsx'):
        return excel(file_path)

    else:
        print(f"Неизвестный формат файла: {file_path}")
        return ""


def clean_text(text):
    return re.sub(r'\s+', ' ', text).strip()


def main():

    if not os.path.exists(data_dir):
        print(f"Ошибка: папки {data_dir} не существует!")
        return

    file_paths = [os.path.join(data_dir, f) for f in os.listdir(data_dir)
                  if f.lower().endswith(('.pdf', '.docx', '.doc', '.xlsx'))]

    if not file_paths:
        print("В указанной папке нет файлов поддерживаемых форматов")
        return

    print(f"\nНайдено {len(file_paths)} файлов для обработки в папке {data_dir}:")

    for i, fp in enumerate(file_paths, 1):
        print(f"{i}. {os.path.basename(fp)}")

    documents = []

    for file_path in file_paths:
        filename = os.path.basename(file_path)
        print(f"\nОбработка файла: {filename}")

        try:
            text = all_text(file_path)
            if text:
                cleaned = clean_text(text)
                preview = cleaned[:100] + ('...' if len(cleaned) > 100 else '')
                documents.append({
                    'name': filename,
                    'text': cleaned,
                    'preview': preview
                })
                print(f"Успешно извлечено. Превьюшка: {preview}")

            else:
                print("Не удалось извлечь текст")
                documents.append({
                    'name': filename,
                    'text': '',
                    'preview': 'Нет текста'
                })

        except Exception as e:
            print(f"Ошибка обработки: {e}")
            documents.append({
                'name': filename,
                'text': '',
                'preview': f'Ошибка обработки: {str(e)}'
            })

    # Вывод полных результатов
    print("\n" + "=" * 50)
    print("Полные результаты обработки:")

    for doc in documents:
        print(f"\nФайл: {doc['name']}")
        print(f"Превьюшенька (первые 100 символов): {doc['preview']}")
        print("-" * 50)

    # Поиск по ключевым словам
    while True:
        query = input("\nВведите ключевые слова для поиска (или 'q' для выхода): ").strip()
        if query.lower() == 'q':
            break

        if not query:
            continue

        keywords = re.sub(r'[^\w\s]', '', query).lower().split()
        results = [d for d in documents
                   if all(kw in d['text'].lower() for kw in keywords)]

        if results:
            print(f"\nНайдено {len(results)} совпадений:")
            for res in results:
                print(f"- {res['name']}")
                print(f"  Совпадение: {res['preview']}")
        else:
            print("Совпадений не найдено")

    print("\nПрограмма завершена.")


if __name__ == "__main__":
    main()