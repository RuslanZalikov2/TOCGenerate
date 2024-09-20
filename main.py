from image2text import Image2Text
from schemas import Input, Output

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/predict", response_model=Output)
async def predict(inp: Input):
    pdf_file = inp.file.encode('latin-1')
    i2t = Image2Text()
    meta = {
        "toc_type": inp.toc_type,
        "toc_start_page_num": inp.toc_start_page_num
    }
    response, file = i2t.infer(pdf_file, meta)
    if isinstance(file, bytes):
        file = file.decode('latin-1')
    return {"message": file}