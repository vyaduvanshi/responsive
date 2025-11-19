import requests

# BACKEND_URL = "http://localhost:8000"
BACKEND_URL = "http://backend:8000"


def upload_file(file):
    files = {"file": (file.name, file, file.type)}
    r = requests.post(f"{BACKEND_URL}/upload", files=files)
    return r.json()

def list_sessions():
    r = requests.get(f"{BACKEND_URL}/sessions/")
    return r.json()

def delete_session(session_id: str):
    r = requests.delete(f"{BACKEND_URL}/sessions/{session_id}")
    return r.json()

def get_history(session_id: str):
    r = requests.get(f"{BACKEND_URL}/sessions/{session_id}/history")
    return r.json()