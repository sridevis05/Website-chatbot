# RAG-Powered Website Chatbot

A production-ready, modular Retrieval-Augmented Generation (RAG) chatbot designed to recursively crawl websites, parse HTML text, extract table layouts, fetch and scrape PDFs, store content as embeddings, and allow contextual chatting using Gemini models via OpenRouter. 

The application is self-contained and serves a premium HTML/CSS/JS frontend interface directly from the FastAPI server.

---

## Technical Stack
* **Backend**: FastAPI (Python), Playwright (async JS rendering), Trafilatura (clean body extraction), PyPDF (PDF text reader)
* **Vector Store**: ChromaDB (local persistence)
* **Embeddings**: SentenceTransformers (`all-MiniLM-L6-v2` running locally)
* **LLM**: Gemini (`google/gemini-2.5-flash` or custom overrides) accessed through the OpenRouter API
* **Frontend**: Custom single-page HTML/CSS/JS chat interface served at the root `/` endpoint of the FastAPI server

---

## Directory Structure
```
RAG website chatbot/
├── requirements.txt           # Dependency configurations
├── .env                       # Environment credentials
├── packages/                  # Local packages folder (resolves MAX_PATH on Windows)
├── backend/
│   ├── __init__.py
│   ├── main.py                # FastAPI entry point
│   ├── config.py              # Application configurations
│   ├── static/
│   │   └── index.html         # Premium HTML/CSS/JS chat UI
│   ├── crawler/
│   │   └── crawler.py         # Playwright-based crawler & link discovery
│   ├── extractor/
│   │   └── extractor.py       # Trafilatura + PDF + Table parser (with BS4 fallback)
│   ├── embeddings/
│   │   └── embedder.py        # SentenceTransformers cache layer
│   ├── vectorstore/
│   │   └── database.py        # ChromaDB persistent database layer
│   ├── rag/
│   │   └── engine.py          # QA prompt context assembler & OpenAI Client
│   ├── api/
│   │   └── routes.py          # FastAPI endpoint controllers
│   └── models/
│       └── schemas.py         # Request/Response Pydantic validation
├── chroma_db/                 # ChromaDB vector store directory (auto-created)
├── cache_dir/                 # Caching folder for crawling & embeddings (auto-created)
├── Dockerfile                 # Container configurations
└── README.md                  # Setup documentation
```

---

## Installation & Setup

### 1. Configuration
Create a `.env` file in the root directory and add your OpenRouter Gemini key:
```env
GEMINI_API_KEY=your-openrouter-api-key-here
```

### 2. Dependency Installation
Install python dependencies:
```bash
pip install -r requirements.txt
```
*Note: If you run into Windows path limits (`MAX_PATH OSError`), use the target-based installation pattern which locates dependencies under the `./packages` folder inside the workspace:*
```bash
pip install --target="packages" -r requirements.txt
```

### 3. Playwright Initialization
Playwright requires browser binaries to crawl sites. Initialize Chromium:
```bash
playwright install chromium
```

---

## How to Run

### Startup the FastAPI Server
Start the uvicorn server:
```bash
python -m uvicorn backend.main:app --port 8000
```
*Note: If dependencies are installed locally in `./packages`, run: *
```bash
# Windows PowerShell
$env:PYTHONPATH="packages"; python -m uvicorn backend.main:app --port 8000
```

Once started, open **`http://localhost:8000/`** in your browser to access the premium HTML chatbot interface. You can view the automatic Swagger API documentation at `http://localhost:8000/docs`.

---

## API Endpoints

* **`POST /api/crawl`**: Triggers a background recursive crawl job for a website.
  * Request Body: `{"url": "https://example.com", "max_pages": 15, "max_depth": 2}`
* **`GET /api/crawl-status/{job_id}`**: Retrieves progress logs and statistics for a specific crawl job.
* **`POST /api/chat`**: Queries the indexed website database.
  * Request Body: `{"query": "User question", "website_url": "https://example.com", "chat_history": []}`
* **`GET /api/websites`**: Lists indexed websites, page count, and metadata.
* **`DELETE /api/websites`**: Deletes a specific website URL from the index database.

---

## Running with Docker
Build and run the application in a single container (which handles FastAPI, HTML UI, and Playwright system dependencies automatically):

```bash
# Build image
docker build -t website-rag-chatbot .

# Run container (Forwarding backend port)
docker run -p 8000:8000 --env-file .env website-rag-chatbot
```
Once run, access the chat interface at `http://localhost:8000/`.
