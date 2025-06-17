import pytest
import os
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session
from fastapi_auth.main import app, get_session
from fastapi_auth.models import User, Note
from fastapi_auth.auth import get_password_hash


TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})

def get_test_session():
    with Session(engine) as session:
        yield session

app.dependency_overrides[get_session] = get_test_session

@pytest.fixture(scope="module")
def client():
    SQLModel.metadata.create_all(engine)
    yield TestClient(app)
    SQLModel.metadata.drop_all(engine)
    if os.path.exists("./test.db"):
        os.remove("./test.db")

@pytest.fixture(scope="module")
def test_user():
    with Session(engine) as session:
        user = User(username="testuser", password=get_password_hash("testpass"))
        session.add(user)
        session.commit()
        session.refresh(user)
        yield user
        
def test_register(client):
    response = client.post("/register", json={"username": "newuser", "password": "newpass"})
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "newuser"
    assert "id" in data
    
def test_register_duplicate(client, test_user):
    response = client.post("/register", json={"username": "testuser", "password": "any"})
    assert response.status_code == 400
    
def test_login_success(client, test_user):
    response = client.post("/login", data={"username": "testuser", "password": "testpass"})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    
def test_login_fail(client):
    response = client.post("/login", data={"username": "notexist", "password": "wrong"})
    assert response.status_code == 401
    
    
def test_users_me_auth(client, test_user):
    response = client.post("/login", data={"username": "testuser", "password": "testpass"})
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/users/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    
def test_users_me_no_auth(client):
    response = client.get("/users/me")
    assert response.status_code == 401
    
def get_auth_headers(client, username, password):
    response = client.post("/login", data={"username": username, "password": password})
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def test_create_note(client, test_user):
    headers = get_auth_headers(client, "testuser", "testpass")
    response = client.post("/notes", json={"title": "Note1", "content": "Content1"}, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Note1"
    
def test_get_notes(client, test_user):
    headers = get_auth_headers(client, "testuser", "testpass")
    client.post("/notes", json={"title": "Note2", "content": "Content2"}, headers=headers)
    response = client.get("/notes", headers=headers)
    assert response.status_code == 200
    notes = response.json()
    assert isinstance(notes, list)
    assert any(note["title"] == "Note2" for note in notes)
    
def test_get_note_not_owner(client, test_user):
    with Session(engine) as session:
        other_user = User(username="other", password=get_password_hash("pass"))
        session.add(other_user)
        session.commit()
        session.refresh(other_user)
        note = Note(title="OtherNote", content="OtherContent", owner_id=other_user.id)
        session.add(note)
        session.commit()
        session.refresh(note)
        other_note_id = note.id
    headers = get_auth_headers(client, "testuser", "testpass")
    response = client.get(f"/notes/{other_note_id}", headers=headers)
    assert response.status_code == 404
    
def test_delete_note(client, test_user):
    headers = get_auth_headers(client, "testuser", "testpass")
    response = client.post("/notes", json={"title": "ToDelete", "content": "DeleteMe"}, headers=headers)
    note_id = response.json()["id"]
    del_resp = client.delete(f"/notes/{note_id}", headers=headers)
    assert del_resp.status_code == 200
    assert del_resp.json() == {"detail": "Запись удалена"}
    
    get_resp = client.get(f"/notes/{note_id}", headers=headers)
    assert get_resp.status_code == 404