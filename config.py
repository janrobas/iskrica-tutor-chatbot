import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    #DEFAULT_LLAMA_MODEL = os.getenv("DEFAULT_LLAMA_MODEL", "deepseek-r1:32b")
    DEFAULT_LLAMA_MODEL = os.getenv("DEFAULT_LLAMA_MODEL", "gemma3:27b")
    DEFAULT_COLLECTION_NAME = os.getenv("DEFAULT_COLLECTION_NAME", "test_collection_1")

