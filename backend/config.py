import os
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

class Settings:
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    LLM_MODEL: str = "google/gemini-2.5-flash"
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"
    CHROMA_DB_DIR: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "chroma_db"))
    CACHE_DIR: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "cache_dir"))
    
    # API Settings
    HOST: str = "0.0.0.0"
    PORT: int = int(os.getenv("PORT", 8000))

settings = Settings()

# Ensure directories exist
os.makedirs(settings.CHROMA_DB_DIR, exist_ok=True)
os.makedirs(settings.CACHE_DIR, exist_ok=True)
