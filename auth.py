import json
import os
import hashlib
from passlib.hash import bcrypt

JSON_FILE = "uporabniki.json"

def load_users():
    """Load users from JSON file"""
    if not os.path.exists(JSON_FILE):
        return []
    
    with open(JSON_FILE, "r") as f:
        return json.load(f)

def save_users(users):
    """Save users to JSON file"""
    with open(JSON_FILE, "w") as f:
        json.dump(users, f, indent=2)

def get_user(username: str):
    users = load_users()
    
    for user in users:
        if user["name"] == username:
            return user
    
    return False

def authenticate_user(username: str, password: str) -> bool:
    """Verify user credentials"""
    users = load_users()
    
    for user in users:
        if user["name"] == username:
            if user["clearpswd"] == password:
                return True
            # Verify password with stored salt
            salt = user.get("salt", "").encode()
            try:
                return bcrypt.verify(password + salt.decode(), user["pswd"])
            except:
                return False
    return False

def add_user(username: str, password: str):
    """Add new user with hashed password"""
    users = load_users()
    
    # Check if user exists
    if any(u["name"] == username for u in users):
        raise ValueError("User already exists")
    
    # Generate salt and hash
    salt = os.urandom(16).hex()  # 32-character hex string
    hashed = bcrypt.hash(password + salt)
    
    # Add new user
    users.append({
        "name": username,
        "pswd": hashed,
        "salt": salt
    })
    
    save_users(users)