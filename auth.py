import json
import os
import hashlib
from passlib.hash import bcrypt

JSON_FILE = "kode.json"

def load_codes():
    """Load codes from JSON file"""
    if not os.path.exists(JSON_FILE):
        return []
    
    with open(JSON_FILE, "r") as f:
        return json.load(f)

def get_code(code: str):
    entries = load_codes()
    
    for entry in entries:
        if entry["code"] == code:
            return entry
    
    return False

def authenticate(username: str, code: str) -> bool:
    """Verify code"""
    entry = get_code(code)

    if entry != False:
        return True

    return False

# def add_user(username: str, password: str):
#     """Add new user with hashed password"""
#     users = load_users()
    
#     # Check if user exists
#     if any(u["name"] == username for u in users):
#         raise ValueError("User already exists")
    
#     # Generate salt and hash
#     salt = os.urandom(16).hex()  # 32-character hex string
#     hashed = bcrypt.hash(password + salt)
    
#     # Add new user
#     users.append({
#         "name": username,
#         "pswd": hashed,
#         "salt": salt
#     })
    
#     save_users(users)