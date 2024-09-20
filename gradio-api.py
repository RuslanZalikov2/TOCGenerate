import io

import gradio as gr
from gradio_pdf import PDF
from image2text import Image2Text
from PyPDF2 import PdfReader, PdfWriter

def test(input_file, radio, page_number):
    with open(input_file, "rb") as f:
        pdf_file = f.read()
    i2t = Image2Text()
    if radio == "Отсутствует":
        radio = None
    meta = {
        "toc_type": radio,
        "toc_start_page_num": page_number
    }
    response, file = i2t.infer(pdf_file, meta)
    with open("output.pdf", "wb") as f:
        f.write(file)
    return ("output.pdf", "output.pdf")

with gr.Blocks() as demo:
    pdf = PDF(label="Upload a PDF", interactive=True)

    radio = gr.Radio(
        choices=["doc_type", "page_type", "Отсутствует"],
        label="Выберите действие"
    )
    page_number = gr.Number(label="Страница с оглавлением, если присутствует. Иначе любое число", visible=True)

    output = PDF(label="Output")
    output_pdf = gr.File(label="Скачать файл")

    button = gr.Button("Обработать")
    button.click(test, inputs=[pdf, radio, page_number], outputs=[output, output_pdf])

demo.launch()