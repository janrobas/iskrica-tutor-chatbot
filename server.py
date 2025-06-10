from chainlit.utils import mount_chainlit
import asyncio
from asyncio.log import logger
import json
from typing import Union
import uuid
from cryptography.fernet import Fernet
from fastapi import FastAPI, HTTPException
#from fastapi.concurrency import asynccontextmanager
from contextlib import asynccontextmanager
from fastapi.responses import StreamingResponse
import httpx
import hashlib
import secrets
import time
from pydantic import BaseModel
import os
import hashlib
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from passlib.hash import bcrypt
from auth import authenticate_user
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from threading import Lock

conversations = {}
conversations_lock = Lock()

# Your existing cleanup function
async def cleanup_sessions():
    """Periodically remove expired sessions"""
    while True:
        try:
            now = time.time()
            expired = [k for k, v in conversations.items() 
                      if now - v['timestamp'] > 3600]
            for k in expired:
                del conversations[k]
            await asyncio.sleep(300)  # Check every 5 minutes
        except asyncio.CancelledError:
            # Handle graceful shutdown
            print("Session cleanup task cancelled")
            break

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    cleanup_task = asyncio.create_task(cleanup_sessions())
    
    yield  # App runs here
    
    # Shutdown logic
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass

app = FastAPI(lifespan=lifespan)

app.mount("/public", StaticFiles(directory="public"), name="public")
salts = []

def remove_old_salts():
    current_time = int(time.time())
    salts[:] = [salt for salt in salts if current_time - salt.timestamp <= 5]

@app.get("/", response_class=RedirectResponse, status_code=302)
async def redirect_pydantic():
    return "chat"

OLLAMA_URL = "http://localhost:11434/api/generate"

class OllamaRequest(BaseModel):
    prompt: str
    model: str = "llama3.1"
    session_id: str = None  # Make sure this matches client input
    #token: str = None
    user: str = None
    password: str = None
    temperature: float = None
    num_ctx: float = None
    num_predict: float = None
    top_k: float = None
    top_p: float = None
    repeat_last_n: float = None
    repeat_penalty: float = None

def add_optional_parameters(request: OllamaRequest, ollama_payload):
    options = {}
    
    if request.temperature is not None:
        options["temperature"] = request.temperature
    if request.num_ctx is not None:
        options["num_ctx"] = request.num_ctx
    if request.num_predict is not None:
        options["num_predict"] = request.num_predict
    if request.top_k is not None:
        options["top_k"] = request.top_k
    if request.top_p is not None:
        options["top_p"] = request.top_p
    if request.repeat_last_n is not None:
        options["repeat_last_n"] = request.repeat_last_n
    if request.repeat_penalty is not None:
        options["repeat_penalty"] = request.repeat_penalty
    # if request.seed is not None:
    #     options["seed"] = request.seed
    # if request.stop is not None:
    #     options["stop"] = request.stop
    # if request.tfs_z is not None:
    #     options["tfs_z"] = request.tfs_z
    # if request.num_gpu is not None:
    #     options["num_gpu"] = request.num_gpu

    ollama_payload["options"] = options


@app.post("/prompt")
async def ask_ollama(request: OllamaRequest):
    #if request.token == None or not use_token(request.token):
    #    return {"error": "invalid token"}
    # Session ID handling

    if (not authenticate_user(request.user, request.password)):
        return { "error": "Auth epic fail" }

    session_id = str(uuid.uuid4())
    session_from_request = False

    if request.session_id != None and request.session_id != "":
        session_id = request.session_id
        session_from_request = True
    context = None
    
    with conversations_lock:
        if session_from_request:
            # Validate existing session
            session_data = conversations.get(session_id)
            if not session_data:
                raise HTTPException(status_code=404, detail="Invalid session ID")
            context = session_data['context']
    async def generate():
        nonlocal context
        try:
            ollama_payload = {
                "model": request.model,
                "prompt": request.prompt,
                "stream": True,
                "context": context,
                "options": {}  # Initialize options object
            }
            
            add_optional_parameters(request, ollama_payload)
            
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    OLLAMA_URL,
                    json=ollama_payload
                ) as response:
                    final_context = None
                    
                    async for chunk in response.aiter_bytes():
                        try:
                            chunk_json = json.loads(chunk)
                            if chunk_json.get('done', False):
                                final_context = chunk_json.get('context')
                        except json.JSONDecodeError:
                            pass
                        
                        yield chunk + b"\n"  # Windows line ending
                    
                    # Update context after successful completion
                    with conversations_lock:
                        conversations[session_id] = {
                            "context": final_context,
                            "timestamp": time.time()
                        }
        
        except Exception as e:
            yield json.dumps({"error": str(e)}).encode() + b"\n"

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={"X-Session-ID": session_id}
    )

@app.post("/prompt-simple")
async def ask_ollama_simple(request: OllamaRequest):
    if not authenticate_user(request.user, request.password):
        return {"error": "Authentication failed"}
    
    session_id = request.session_id or str(uuid.uuid4())
    context = None
    
    if request.session_id:
        with conversations_lock:
            session_data = conversations.get(request.session_id)
            if session_data:
                context = session_data['context']
    
    payload = {
        "model": request.model,
        "prompt": request.prompt,
        "stream": False,
        "context": context,
        "options": {}  # Initialize options object
    }
    
    add_optional_parameters(request, payload)
    
    # Make request to Ollama
    async with httpx.AsyncClient() as client:
        response = await client.post(
            OLLAMA_URL,
            json=payload,
            timeout=60.0  # Increase timeout for full response
        )
        response.raise_for_status()
        ollama_response = response.json()
    
    # Update context
    final_context = ollama_response.get('context')
    if final_context:
        with conversations_lock:
            conversations[session_id] = {
                "context": final_context,
                "timestamp": time.time()
            }
    
    # Return final response
    return {
        "response": ollama_response.get('response', ''),
        "session_id": session_id
    }

@app.get("/items/{item_id}")
def read_item(item_id: int, q: Union[str, None] = None):
    return {"item_id": item_id, "q": q}

# @app.get("/app")
# def read_main():
#     return {"message": "Hello World from main app"}

mount_chainlit(app=app, target="klepetalnik.py", path="/chat")