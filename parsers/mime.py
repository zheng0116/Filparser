from enum import Enum


class Mime(Enum):
    Pdf = "application/pdf"
    Docx = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    Csv = "text/csv"
    Excel = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
    )
    Txt = "text/plain"
    Md = ("text/markdown", "text/x-markdown", "application/octet-stream")

    @classmethod
    def from_str(cls, mime_str):
        for mime in cls:
            if isinstance(mime.value, str) and mime.value == mime_str:
                return mime
            elif isinstance(mime.value, tuple) and mime_str in mime.value:
                return mime
        return None
