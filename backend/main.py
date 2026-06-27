import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.routes import router as api_router
from backend.config import settings

app = FastAPI(
    title="RAG Website Chatbot API",
    description="Backend API for crawling websites, parsing pages, indexing text into ChromaDB, and running RAG queries using Gemini via OpenRouter.",
    version="1.0.0"
)

# Set up CORS middleware to allow Streamlit to make API calls if run on different ports
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to Streamlit's URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import os
from fastapi.responses import HTMLResponse

# Include routes
app.include_router(api_router, prefix="/api")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """
    Serves the custom HTML/CSS/JS frontend.
    """
    static_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    with open(static_path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/health")


async def health_check():
    """
    Health check endpoint.
    """
    return {"status": "healthy", "service": "RAG Website Chatbot API"}

if __name__ == "__main__":
    # Note: On Windows, running with reload=True forces the SelectorEventLoop,
    # which does not support the subprocesses required by Playwright.
    uvicorn.run("backend.main:app", host=settings.HOST, port=settings.PORT, reload=True)
