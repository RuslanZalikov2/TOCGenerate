from pydantic import BaseModel


class Input(BaseModel):
    toc_type: str | None
    toc_start_page_num: int
    file: str


class Output(BaseModel):
    message: bytes