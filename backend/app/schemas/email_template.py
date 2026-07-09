from pydantic import BaseModel


class EmailTemplateIn(BaseModel):
    subject: str
    body_html: str
    enabled: bool = True


class EmailTemplatePreviewIn(BaseModel):
    subject: str
    body_html: str
