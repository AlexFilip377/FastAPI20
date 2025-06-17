from fastapi import FastAPI, Depends, HTTPException, status, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi_auth.connection_manager import ConnectionManager
from sqlmodel import Session, select
from fastapi_auth.models import User, Note
from fastapi_auth.schemas import UserCreate, UserLogin, NoteCreate, NoteOut, NoteUpdate
from fastapi_auth.database import create_db_and_tables, get_session
from fastapi_auth.auth import create_access_token, get_password_hash, verify_password, get_current_user, require_role
from typing import List
from fastapi_auth.worker import send_email_task
from pydantic import BaseModel
from fastapi_auth.cache import get_redis
from fastapi_auth.config import get_settings
from fastapi_auth.logging_config import setup_loging
from prometheus_fastapi_instrumentator import Instrumentator
from fastapi_auth.middleware.rate_limiter import RateLimiterMiddleware
import json
import logging


app = FastAPI(
    title="Notes API",
    description="Сервис для управления заметками, пользователями и взаимодействия в реальном времени",
    version="1.0"
)
manager = ConnectionManager()
app.add_middleware(RateLimiterMiddleware, redis_url="redis://redis:6379")

settings = get_settings()
setup_loging()
logger = logging.getLogger(__name__)
instrumentator = Instrumentator()
instrumentator.instrument(app).expose(app)

DATABASE_URL = settings.DATABASE_URL
SECRET_KEY = settings.SECRET_KEY
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

class EmailRequest(BaseModel):
    email: str
    
async def invalidate_notes_cache(user_id: int):
    redis = await get_redis()
    keys = await redis.keys(f"notes:{user_id}:*")
    if keys:
        await redis.delete(*keys)

@app.on_event("startup")
def on_startup():
    create_db_and_tables()
    
@app.get("/ping")
async def ping():
    logger.info("Pinging")
    return {"ping": "pong"}

@app.get("/health")
async def health():
    return {"status": "ok"}
 
@app.post("/register")
def register(user_data: UserCreate, session: Session = Depends(get_session)):
    user_exists = session.exec(select(User).where(User.username == user_data.username)).first()
    if user_exists:
        raise HTTPException(status_code=400, detail="Пользователь уже существует")
    
    hashed_password = get_password_hash(user_data.password)
    new_user = User(username=user_data.username, password=hashed_password, role="user")
    session.add(new_user)
    session.commit()
    session.refresh(new_user)
    return {"id": new_user.id, "username": new_user.username}

@app.post("/login")
def login(user_data: UserLogin, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.username == user_data.username)).first()
    if not user or not verify_password(user_data.password, user.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Некорректные данные")
    
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/send_email/")
def send_email(email: str):
    task = send_email_task.delay(email)
    return {"message": "Отправка", "task_id": task.id}

@app.get("/users/me")
def read_user_me(current_user: User = Depends(get_current_user)):
    print("check")
    return {
        "id": current_user.id,
        "username": current_user.username
    }
    
@app.get("/admin/users")
def get_all_users(
    current_user: User = Depends(require_role("admin")),
    session: Session = Depends(get_session)
):
    users = session.exec(select(User)).all()
    return [{"id": u.id, "username": u.username, "role": u.role} for u in users]


@app.post(
    "/notes",
    response_model=NoteOut,
    status_code=201,
    summary="Создать заметку",
    description="Создает заметку",
    responses={
        201: {"description": "Заметка создана успешно"},
        400: {"description": "Неверные данные"},
    })
async def create_note(note_in: NoteCreate, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    note = Note(**note_in.dict(), owner_id=current_user.id)
    session.add(note)
    session.commit()
    session.refresh(note)
    await invalidate_notes_cache(current_user.id)
    return note

@app.get("/notes", response_model=List[NoteOut])
async def get_notes(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1),
    search: str = Query(None, min_length=1)
):
    redis = await get_redis()
    cache_key = f"notes:{current_user.id}:{skip}:{limit}:{search or ''}"

    cached_data = await redis.get(cache_key)
    if cached_data:
        return json.loads(cached_data)

    query = select(Note).where(Note.owner_id == current_user.id)
    if search:
        query = query.where(
            (Note.title.ilike(f"%{search}%")) | (Note.content.ilike(f"%{search}%"))
        )

    notes = session.exec(query.offset(skip).limit(limit)).all()
    result = [note.dict() for note in notes]

    await redis.set(cache_key, json.dumps(result), ex=60)  # TTL: 60 сек
    return result


@app.get("/notes/{note_id}", response_model=NoteOut)
def get_note(note_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    note = session.get(Note, note_id)
    if not note or note.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Не найдено")
    return note

@app.put("/notes/{note_id}", response_model=NoteOut)
async def update_note(note_id: int, note_update: NoteUpdate, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    note = session.get(Note, note_id)
    if not note or note.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Не найдено")
    note_data = note_update.dict(exclude_unset=True)
    for key, value in note_data.items():
        setattr(note, key, value)
    session.add(note)
    session.commit()
    session.refresh(note)
    await invalidate_notes_cache(current_user.id)
    return note 

@app.delete("/notes/{note_id}")
async def delete_note(note_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    note = session.get(Note, note_id)
    if not note or note.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Не найдено")
    session.delete(note)
    session.commit()
    await invalidate_notes_cache(current_user.id)
    return {"detail": "Запись удалена"}

@app.get("/")
async def get():
    with open("templates/chat.html") as f:
        return HTMLResponse(f.read())
    
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(f"Client says: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast("A client disconnected.")