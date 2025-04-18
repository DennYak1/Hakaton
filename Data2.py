import os
import re
import json
import warnings
import traceback
import logging

logging.basicConfig(level=logging.INFO)

import docx
import pytesseract
import pandas as pd
from PIL import Image
from PyPDF2 import PdfReader, PdfWriter
from pdfminer.high_level import extract_text as pdfminer_extract
from pdf2image import convert_from_path


POPPLER_PATH = r"C:\Users\User\Downloads\poppler-24.08.0\Library\bin"
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

DATA_DIR = r"C:\Users\User\PycharmProjects\Hakaton\hackaton"
OUTPUT_JSON = "data.json"


def fix_cropbox(file_path):
    reader = PdfReader(file_path)
    writer = PdfWriter()

    for page in reader.pages:
        if '/CropBox' not in page:
            page.cropbox = page.mediabox
        writer.add_page(page)

    fixed_path = os.path.join(os.path.dirname(file_path), os.path.basename(file_path))

    with open(fixed_path, 'wb') as f:
        writer.write(f)
    return fixed_path


def pdf_to_text(file_path):
    try:
        fixed_path = fix_cropbox(file_path)
        text = pdfminer_extract(fixed_path)

        if not text.strip():
            logging.info("Текст пустой, значит запускается OCR")
            return pdf_to_text_ocr(fixed_path)
        return text

    except Exception as e:
        logging.warning(f"Ошибка PDF: {e}")
        return ""


def pdf_to_text_ocr(file_path):
    try:
        images = convert_from_path(
            file_path,
            dpi=300,
            poppler_path=POPPLER_PATH,
            grayscale=True,
            thread_count=4
        )
        text = ""

        for i, img in enumerate(images):
            try:
                page_text = pytesseract.image_to_string(img, lang='rus+eng')
                text += page_text + "\n"

            except Exception as ocr_error:
                logging.warning(f"OCR ошибка на странице {i + 1}: {ocr_error}")
        return text

    except Exception as e:
        logging.warning(f"Ошибка при OCR PDF: {e}")
        return ""


def doc_to_text(file_path):
    try:
        logging.info(f"Конвертация из DOC в DOCX: {file_path}")
        tmp_dir = os.path.join(os.environ['TEMP'], "doc_conversion")
        os.makedirs(tmp_dir, exist_ok=True)
        os.system(f"libreoffice --headless --convert-to docx --outdir {tmp_dir} {file_path}")

        new_path = os.path.join(
            tmp_dir,
            os.path.splitext(os.path.basename(file_path))[0] + ".docx"
        )
        if not os.path.exists(new_path):
            logging.warning(f"Не удалось создать: {new_path}")
            return ""
        return docx_to_text(new_path)

    except Exception as e:
        logging.warning(f"Ошибка при чтении DOC: {e}")
        return ""


def docx_to_text(file_path):
    try:
        d = docx.Document(file_path)
        return "\n".join([p.text for p in d.paragraphs])

    except Exception as e:
        logging.warning(f"Ошибка при чтении DOCX: {e}")
        return ""


def excel_to_text(file_path):
    try:
        text = ""
        dfs = pd.read_excel(file_path, sheet_name=None)

        for sheet_name, df in dfs.items():
            df = df.fillna('')
            text += f"Лист: {sheet_name}\n{df.to_string(index=False)}\n\n"
        return text

    except Exception as e:
        logging.warning(f"Ошибка при чтении Excel: {e}")
        return ""


def clean_text(text):
    return re.sub(r'\s+', ' ', text).strip()


def extract_text_from_file(file_path):

    ext = file_path.lower()
    if ext.endswith('.pdf'):
        return pdf_to_text(file_path)
    elif ext.endswith('.docx'):
        return docx_to_text(file_path)
    elif ext.endswith('.doc'):
        return doc_to_text(file_path)
    elif ext.endswith('.xlsx'):
        return excel_to_text(file_path)
    else:
        logging.info(f"Неизвестный формат файла: {file_path}") # на будущее
        return ""


def main():

    file_paths = [
        os.path.join(DATA_DIR, f)
        for f in os.listdir(DATA_DIR)
        if f.lower().endswith(('.pdf', '.docx', '.doc', '.xlsx'))
    ]

    if not file_paths:
        print("В указанной папке нет файлов поддерживаемых форматов.")
        return

    print(f"\nНайдено {len(file_paths)} файлов для обработки в папке {DATA_DIR}:")

    for i, fp in enumerate(file_paths, 1):
        print(f"{i}. {os.path.basename(fp)}")

    documents = []


    if os.path.exists(OUTPUT_JSON):
        with open(OUTPUT_JSON, 'r', encoding='utf-8') as f:
            try:
                documents = json.load(f)
            except:
                documents = []
    else:
        documents = []


    existing_docs_map = {doc['name']: doc for doc in documents}

    for file_path in file_paths:
        filename = os.path.basename(file_path)
        print(f"\nОбработка файла: {filename}")

        if filename in existing_docs_map and existing_docs_map[filename].get('text'):
            print("Файл уже обработан ранее, пропускаем.")
            continue


        try:
            text = extract_text_from_file(file_path)
            cleaned = clean_text(text)
            preview = cleaned[:100] + ('...' if len(cleaned) > 100 else '')
            doc_dict = {
                'name': filename,
                'text': cleaned,
                'preview': preview
            }
            existing_docs_map[filename] = doc_dict
            print(f"Успешно извлечено. Превью: {preview}")

        except Exception as e:
            print(f"Ошибка обработки файла {filename}: {e}")
            traceback.print_exc()

            existing_docs_map[filename] = {
                'name': filename,
                'text': '',
                'preview': f'Ошибка: {str(e)}'
            }


    documents = list(existing_docs_map.values())
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(documents, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 50)
    print("Готово. Полные результаты сохранены в", OUTPUT_JSON)
    for doc in documents:
        print(f"\nФайл: {doc['name']}")
        print(f"Превью (первые 100 символов): {doc['preview']}")
        print("-" * 50)


if __name__ == "__main__":
    main()