import os
import re
import io
import cv2 as cv
import numpy as np
import pytesseract

from tqdm import tqdm
from typing import Dict
from textwrap import wrap
from dotenv import load_dotenv
from yandexgptlite import YandexGPTLite

from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen.canvas import Canvas
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4, letter

from pdf2image import convert_from_bytes
from PyPDF2 import PdfWriter, PdfReader, Transformation


class Image2Text:
    def __init__(self, path_to_tessdata="/usr/local/share/tessdata/", config=r'--oem 3 --psm 6 --dpi 300'):
        load_dotenv()
        if path_to_tessdata is None:
            self.path_to_tessdata = os.environ["TESSDATA_PREFIX"]
        self.path_to_tessdata = path_to_tessdata
        self.config = config

    def infer(self, pdf: bytes, meta: Dict[str, str | int] | None, output_path: str = "output.pdf"):
        images = convert_from_bytes(pdf, 300)
        os.environ["TESSDATA_PREFIX"] = self.path_to_tessdata
        if meta["toc_type"] == "doc_type":
            return False, False
        if meta["toc_type"] == "page_type":
            index = meta["toc_start_page_num"]
            if index == -2:
                index = 1
            for image in self._preproc(images[index:index + 1]):
                text = pytesseract.image_to_string(image, lang='rus', config=self.config)
            trb = self._postproc(text, index)
            file = self._save_to_pdf_io(pdf, trb)
            return trb, file

        if meta["toc_type"] is None:
            trb = ""
            for index, image in enumerate(self._preproc(images)):
                trb += f"\n\n======= Страница {index} ======= \n"
                trb += pytesseract.image_to_string(image, lang='rus', config=self.config)
            system_prompt = """
                На вход к тебе отправляет транскрибация pdf файла. Создай оглавление размером не больше 200 слов. Результат верни строго в виде текста
            """
            response_from_gpt = self._promt_to_gpt(system_prompt, trb)
            response_from_gpt = response_from_gpt.replace("*", "")
            file = self._save_to_pdf_after_gpt_io(pdf, response_from_gpt)
            return response_from_gpt, file

    def _preproc(self, images):
        for i, page in tqdm(enumerate(images)):
            page_array = cv.cvtColor(np.array(page), cv.COLOR_RGB2BGR)
            gray_image = cv.cvtColor(page_array, cv.COLOR_BGR2GRAY)
            denoised_image = cv.bilateralFilter(gray_image, 11, 15, 15)
            _, binary_image = cv.threshold(denoised_image, 0, 255, cv.THRESH_BINARY + cv.THRESH_OTSU)
            yield binary_image

    def _postproc(self, text, num_toc):
        text = text.replace("&", "8")
        text = text.replace("$", "8")
        text = text.replace("?", "7")
        text = text.split("\n")
        new_text = []
        for index, value in enumerate(text[::-1]):
            number = re.findall(r"\d+$|\d+\s*[страница.]*$", value)
            if len(number) > 0:
                page_num = number[-1]
                new_text.append([int(page_num), value])
            if len(number) == 0 and len(new_text) != 0:
                new_text[-1][1] = f"{value} {new_text[-1][1]}"
        if new_text[-1][1][0] in "0123456789":
            new_text.pop(-1)
        if new_text[0][1][0] in "0123456789":
            new_text.pop(0)
        for index, value in enumerate(new_text):
            if "оглавление" in new_text[index][1].lower():
                idx = new_text[index][1].lower().index("оглавление")
                new_text[index][1] = new_text[index][1][:idx] + new_text[index][1][idx+len("оглавление "):]
                new_text.append([num_toc+1, "Оглавление"])
                break
            elif "содержание" in new_text[index][1].lower():
                idx = new_text[index][1].lower().index("содержание")
                new_text[index][1] = new_text[index][1][:idx] + new_text[index][1][idx+len("содержание "):]
                new_text.append([num_toc+1, "Содержание"])
                break

        return new_text[::-1]

    def _promt_to_gpt(self, system_prompt, user_prompt, temp=1):
        account = YandexGPTLite(os.environ["CODE_DIRECTORY"], os.environ["OAuthToken"])
        response = account.create_completion(user_prompt, temperature=temp, system_prompt=system_prompt, max_tokens=500)
        return response

    def _save_to_pdf_io(self, input_data: bytes, data):
        reader = PdfReader(io.BytesIO(input_data))
        writer = PdfWriter()

        for page_num in range(len(reader.pages)):
            writer.add_page(reader.pages[page_num])

        for key, value in data:
            writer.add_outline_item(value, key - 1)

        with io.BytesIO() as resp:
            writer.write(resp)
            return resp.getvalue()

    def save_to_pdf(self, input_path, data, output_path="output_path.pdf"):
        reader = PdfReader(input_path)
        writer = PdfWriter(output_path)

        for page_num in range(len(reader.pages)):
            writer.add_page(reader.pages[page_num])

        for key, value in data:
            writer.add_outline_item(value, key-1)

        with open(output_path, "wb") as output_pdf:
            writer.write(output_pdf)

    def _save_to_pdf_after_gpt_io(self, input_data: bytes, data):
        input_pdf_bytes = io.BytesIO(input_data)
        text_page_bytes = self._create_text_page(data)
        output_pdf_bytes = self._insert_page_in_pdf(input_pdf_bytes, text_page_bytes)
        return output_pdf_bytes

    def save_to_pdf_after_gpt(self, input_path, data, output_path="output_path.pdf"): # Пока что не закончил
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)
        can.drawString(10, 100, data)
        can.save()
        packet.seek(0)
        new_pdf = PdfReader(packet)
        existing_pdf = PdfReader(open(input_path, "rb"))
        output = PdfWriter()
        existing_pdf.pages.insert(1, new_pdf)

        output_stream = open(output_path, "wb")
        existing_pdf.write(output_stream)
        output_stream.close()

    def _create_text_page(self, text):
        pdfmetrics.registerFont(TTFont('DejaVuSans', 'fonts/DejaVuSans.ttf'))

        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        c.setFont('DejaVuSans', 8)
        width, height = A4
        margin = 100
        line_height = 14

        wrapped_text = text.split("\n")  # 90
        k = 0
        for i, line in enumerate(wrapped_text):
            wrap_lines = wrap(line, 90)
            for j, wrap_line in enumerate(wrap_lines):
                k += 1
                c.drawString(margin, height - 100 - k * line_height, wrap_line)
        c.showPage()
        c.save()
        buffer.seek(0)
        return buffer

    def _insert_page_in_pdf(self, input_pdf_bytes, text_page_bytes):
        reader = PdfReader(input_pdf_bytes)
        writer = PdfWriter()

        text_pdf_reader = PdfReader(text_page_bytes)
        text_page = text_pdf_reader.pages[0]

        writer.add_page(reader.pages[0])
        writer.add_page(text_page)

        for page_num in range(1, len(reader.pages)):
            writer.add_page(reader.pages[page_num])

        output_buffer = io.BytesIO()
        writer.write(output_buffer)
        output_buffer.seek(0)
        with io.BytesIO() as output_buffer:
            writer.write(output_buffer)
            return output_buffer.getvalue()