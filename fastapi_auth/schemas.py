from pydantic import BaseModel, Field
from typing import Optional

class NoteCreate(BaseModel):
    title: str = Field(..., description="Заголовок заметки", example="Первая заметка")
    content: str = Field(..., description="Содержимое заметки", example="Я учу FASTAPI")
    
class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    
class NoteOut(BaseModel):
    id: int = Field(..., description="ID заметки")
    title: str
    content: str
    
    class Config:
        orm_model = True

class UserCreate(BaseModel):
    username: str
    password: str
    
class UserLogin(BaseModel):
    username: str
    password: str