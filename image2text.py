import os
import re
import cv2 as cv
import numpy as np
import pytesseract

from tqdm import tqdm
from PIL import Image
from pdf2image import convert_from_path
from PyPDF2 import PdfReader, PdfWriter
from typing import List, Dict, Generator

class Image2Text:
    def __init__(self, path_to_tessdata="/usr/local/share/tessdata/", config=r'--oem 3 --psm 6 --dpi 300'):
        self.path_to_tessdata = path_to_tessdata
        self.config = config

    def infer(self, path_to_pdf: str, meta: Dict[str, str | int] | None, output_path: str = "output.pdf"):
        images = convert_from_path(path_to_pdf, 300)

        if meta["toc_type"] == "doc_type":
            return False
        if meta["toc_type"] == "page_type":
            os.environ["TESSDATA_PREFIX"] = self.path_to_tessdata
            index = meta["toc_start_page_num"]
            for image in self._preproc(images[index:index + 1]):
                text = pytesseract.image_to_string(image, lang='rus', config=self.config)
            text = self._postproc(text, index)
            return text
        if meta is None:
            pass

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

        return new_text[::-1]

    def save_to_pdf(self, input_path, data, output_path="output_path.pdf"):
        reader = PdfReader(input_path)
        writer = PdfWriter(output_path)

        for page_num in range(len(reader.pages)):
            writer.add_page(reader.pages[page_num])

        for key, value in data:
            writer.add_outline_item(value, key-1)

        with open(output_path, "wb") as output_pdf:
            writer.write(output_pdf)
