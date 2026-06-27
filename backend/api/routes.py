import uuid
import asyncio
import hashlib
from urllib.parse import urlparse
from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Dict, Any

from backend.models.schemas import (
    CrawlRequest,
    CrawlResponse,
    CrawlStatusResponse,
    ChatRequest,
    ChatResponse,
    WebsiteItem,
    Citation,
    Message
)
from backend.crawler.crawler import crawl_site, CRAWL_JOBS
from backend.extractor.extractor import recursive_split_text
from backend.embeddings.embedder import embedder
from backend.vectorstore.database import db_manager
from backend.rag.engine import run_rag_query

router = APIRouter()

async def run_crawl_background(job_id: str, url: str, max_pages: int, max_depth: int):
    """
    Background job that runs Playwright crawling, chunking, embedding, and vector insertion.
    """
    try:
        # 1. Run the scraper/crawler
        pages = await crawl_site(job_id, url, max_pages=max_pages, max_depth=max_depth)
        
        if not pages:
            CRAWL_JOBS[job_id]["status"] = "completed"
            CRAWL_JOBS[job_id]["progress"] = 100.0
            return
            
        # Parse the base URL to store website info
        parsed_base = urlparse(url)
        base_website = f"{parsed_base.scheme}://{parsed_base.netloc}"
        
        all_ids = []
        all_embeddings = []
        all_documents = []
        all_metadatas = []
        
        # 2. Extract and split content into chunks
        for page_idx, page in enumerate(pages):
            page_url = page["url"]
            title = page["title"]
            c_type = page["content_type"]
            text_content = page.get("text", "")
            table_content = page.get("tables", "")
            
            chunks = []
            metadata_templates = []
            
            if c_type == "pdf":
                # PDF content
                pdf_chunks = recursive_split_text(text_content, chunk_size=1000, chunk_overlap=150)
                for c in pdf_chunks:
                    chunks.append(c)
                    metadata_templates.append({
                        "source": page_url,
                        "title": title,
                        "content_type": "pdf",
                        "website": base_website
                    })
            else:
                # Text content
                if text_content:
                    text_chunks = recursive_split_text(text_content, chunk_size=1000, chunk_overlap=150)
                    for c in text_chunks:
                        chunks.append(c)
                        metadata_templates.append({
                            "source": page_url,
                            "title": title,
                            "content_type": "text",
                            "website": base_website
                        })
                # Table content
                if table_content:
                    table_chunks = recursive_split_text(table_content, chunk_size=800, chunk_overlap=0)
                    for c in table_chunks:
                        chunks.append(c)
                        metadata_templates.append({
                            "source": page_url,
                            "title": title,
                            "content_type": "table",
                            "website": base_website
                        })
                        
            if not chunks:
                continue
                
            # 3. Generate embeddings
            embeddings = embedder.embed_texts(chunks)
            
            # 4. Compile vector packages
            for chunk_idx, (chunk, emb, meta) in enumerate(zip(chunks, embeddings, metadata_templates)):
                # Deterministic ID using url + content_type + index to prevent duplicates
                unique_str = f"{page_url}_{meta['content_type']}_{chunk_idx}"
                chunk_id = hashlib.sha256(unique_str.encode("utf-8")).hexdigest()
                
                all_ids.append(chunk_id)
                all_embeddings.append(emb)
                all_documents.append(chunk)
                all_metadatas.append(meta)
                
        # 5. Load chunks into database
        if all_ids:
            db_manager.add_chunks(
                ids=all_ids,
                embeddings=all_embeddings,
                documents=all_documents,
                metadatas=all_metadatas
            )
            
        CRAWL_JOBS[job_id]["status"] = "completed"
        CRAWL_JOBS[job_id]["progress"] = 100.0
        
    except Exception as e:
        err_msg = f"Error in background crawl task: {str(e)}"
        print(err_msg)
        CRAWL_JOBS[job_id]["status"] = "failed"
        CRAWL_JOBS[job_id]["errors"].append(err_msg)

@router.post("/crawl", response_model=CrawlResponse)
async def start_crawl(request: CrawlRequest, background_tasks: BackgroundTasks):
    """
    Initializes a website crawl background task. Returns job_id.
    """
    url = request.url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid URL scheme. Must start with http:// or https://")
        
    job_id = str(uuid.uuid4())
    CRAWL_JOBS[job_id] = {
        "status": "pending",
        "progress": 0.0,
        "crawled_count": 0,
        "crawled_pages": [],
        "errors": []
    }
    
    # Run the crawler in the background using FastAPI's background tasks
    background_tasks.add_task(
        run_crawl_background,
        job_id,
        url,
        request.max_pages,
        request.max_depth
    )
    
    return CrawlResponse(job_id=job_id, status="pending")

@router.get("/crawl-status/{job_id}", response_model=CrawlStatusResponse)
async def get_crawl_status(job_id: str):
    """
    Polls status for a crawling job.
    """
    if job_id not in CRAWL_JOBS:
        raise HTTPException(status_code=404, detail="Job ID not found.")
        
    job = CRAWL_JOBS[job_id]
    return CrawlStatusResponse(
        job_id=job_id,
        status=job["status"],
        progress=job["progress"],
        crawled_count=job["crawled_count"],
        crawled_pages=job["crawled_pages"],
        errors=job["errors"]
    )

@router.post("/chat", response_model=ChatResponse)
async def chat_query(request: ChatRequest):
    """
    Executes a RAG query on context database matching selection website.
    """
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
        
    response_data = run_rag_query(
        query=query,
        website_url=request.website_url,
        chat_history=request.chat_history,
        model_name=request.model_override
    )
    
    citations = [
        Citation(
            source=s["source"],
            title=s["title"],
            content_type=s["content_type"],
            score=s["score"]
        ) for s in response_data.get("sources", [])
    ]
    
    return ChatResponse(
        answer=response_data.get("answer", ""),
        sources=citations
    )

@router.get("/websites", response_model=List[WebsiteItem])
async def list_websites():
    """
    Returns lists of base websites indexed in database.
    """
    results = db_manager.get_indexed_websites()
    return [
        WebsiteItem(
            url=r["url"],
            title=r["title"],
            pages_count=r["pages_count"]
        ) for r in results
    ]

@router.delete("/websites")
async def delete_website(website_url: str):
    """
    Removes a website from database.
    """
    db_manager.delete_website(website_url)
    return {"message": f"Successfully deleted website {website_url} from vector database."}
