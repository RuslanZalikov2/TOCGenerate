FROM python:3.10-slim

WORKDIR /code

COPY requirements.txt .

RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libglib2.0-dev \
    libgl1-mesa-glx \
    poppler-utils \
    tesseract-ocr \
    libtesseract-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \

RUN pip install -r requirements.txt

COPY . .

CMD ["python3", "gradio-api.py"]