import os
import asyncio
import hashlib
import pickle
import httpx
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from typing import List, Dict, Any, Tuple, Set, Optional
from backend.config import settings
from backend.extractor.extractor import (
    extract_text_from_html,
    extract_tables_from_html,
    extract_text_from_pdf
)

# Global status dictionary for tracking async crawling jobs
CRAWL_JOBS: Dict[str, Dict[str, Any]] = {}

class CrawlerCache:
    def __init__(self):
        self.cache_path = os.path.join(settings.CACHE_DIR, "crawler_cache.pkl")
        self.cache = {}
        self._load_cache()

    def _load_cache(self):
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "rb") as f:
                    self.cache = pickle.load(f)
                print(f"Loaded {len(self.cache)} crawled pages from crawler cache.")
            except Exception as e:
                print(f"Error loading crawler cache: {e}")
                self.cache = {}

    def _save_cache(self):
        try:
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            with open(self.cache_path, "wb") as f:
                pickle.dump(self.cache, f)
        except Exception as e:
            print(f"Error saving crawler cache: {e}")

    def get(self, url: str) -> Optional[Dict[str, Any]]:
        return self.cache.get(url)

    def set(self, url: str, data: Dict[str, Any]):
        self.cache[url] = data
        self._save_cache()

crawler_cache = CrawlerCache()


def is_pdf_url(url: str) -> bool:
    """
    Checks if the URL likely points to a PDF file.
    """
    parsed = urlparse(url)
    return parsed.path.lower().endswith('.pdf')


async def download_and_extract_pdf(url: str) -> str:
    """
    Downloads a PDF and extracts its text.
    """
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            headers = {"User-Agent": "Mozilla/5.0"}
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            
            if "application/pdf" in response.headers.get("content-type", "").lower() or is_pdf_url(url):
                return extract_text_from_pdf(response.content)
    except Exception as e:
        print(f"Failed to fetch/parse PDF from {url}: {e}")
    return ""


async def crawl_site(
    job_id: str,
    base_url: str,
    max_pages: int = 10,
    max_depth: int = 2
) -> List[Dict[str, Any]]:
    """
    Asynchronously crawls a website recursively using Playwright.
    Updates CRAWL_JOBS with current status and progress.
    """
    job = CRAWL_JOBS[job_id]
    job["status"] = "processing"
    job["progress"] = 0.0
    job["crawled_count"] = 0
    job["crawled_pages"] = []
    job["errors"] = []
    
    parsed_base = urlparse(base_url)
    base_domain = parsed_base.netloc
    
    # Store results (url, title, text, tables, content_type)
    crawled_results = []
    visited: Set[str] = set()
    queue: List[Tuple[str, int]] = [(base_url, 0)]  # (url, depth)
    
    print(f"Starting crawl for {base_url} (Max pages: {max_pages}, Max depth: {max_depth})")
    
    # Initialize Playwright outside loop
    pw = None
    browser = None
    
    try:
        pw = await async_playwright().start()
        # Launch headless browser
        browser = await pw.chromium.launch(headless=True)
        # Create single context to share cookie states
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        while queue and len(visited) < max_pages:
            url, depth = queue.pop(0)
            
            # Normalize URL (remove fragments and trailing slash)
            parsed_url = urlparse(url)
            normalized_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path.rstrip('/')}"
            
            if normalized_url in visited:
                continue
                
            visited.add(normalized_url)
            
            # Update progress
            job["progress"] = round((len(visited) / max_pages) * 100, 1)
            
            # 1. Check Crawler Cache
            cached_data = crawler_cache.get(normalized_url)
            if cached_data:
                print(f"[CACHE HIT] Loaded: {normalized_url}")
                crawled_results.append(cached_data)
                job["crawled_count"] += 1
                job["crawled_pages"].append(normalized_url)
                
                # Still extract links from cached HTML to continue recursion
                if depth < max_depth:
                    try:
                        soup = BeautifulSoup(cached_data.get("html_content", ""), "html.parser")
                        for link in soup.find_all("a", href=True):
                            href = link.get("href")
                            full_url = urljoin(url, href)
                            parsed_full = urlparse(full_url)
                            if parsed_full.netloc == base_domain:
                                queue.append((full_url, depth + 1))
                    except Exception:
                        pass
                continue
                
            # 2. Check if PDF
            if is_pdf_url(normalized_url):
                print(f"Downloading PDF: {normalized_url}")
                pdf_text = await download_and_extract_pdf(normalized_url)
                if pdf_text:
                    pdf_data = {
                        "url": normalized_url,
                        "title": normalized_url.split("/")[-1],
                        "text": pdf_text,
                        "tables": "",
                        "html_content": "",
                        "content_type": "pdf",
                        "website": f"{parsed_base.scheme}://{parsed_base.netloc}"
                    }
                    crawled_results.append(pdf_data)
                    crawler_cache.set(normalized_url, pdf_data)
                    job["crawled_count"] += 1
                    job["crawled_pages"].append(normalized_url)
                continue
                
            # 3. Standard page scrape via Playwright
            page = None
            try:
                print(f"Crawl {len(visited)}/{max_pages}: {normalized_url}")
                page = await context.new_page()
                
                # Navigate with timeout
                await page.goto(normalized_url, timeout=15000, wait_until="load")
                # Wait for elements to load (give Javascript some time to render)
                await asyncio.sleep(1.0)
                
                # Get details
                html = await page.content()
                title = await page.title()
                if not title:
                    title = "Untitled Page"
                    
                # Extractor functions
                text = extract_text_from_html(html)
                tables = extract_tables_from_html(html)
                
                page_data = {
                    "url": normalized_url,
                    "title": title.strip(),
                    "text": text,
                    "tables": tables,
                    "html_content": html, # Store HTML in cache to re-extract links if needed
                    "content_type": "text",
                    "website": f"{parsed_base.scheme}://{parsed_base.netloc}"
                }
                
                crawled_results.append(page_data)
                crawler_cache.set(normalized_url, page_data)
                job["crawled_count"] += 1
                job["crawled_pages"].append(normalized_url)
                
                # Extract internal links for next depth
                if depth < max_depth:
                    soup = BeautifulSoup(html, "html.parser")
                    for link in soup.find_all("a", href=True):
                        href = link.get("href")
                        full_url = urljoin(normalized_url, href)
                        parsed_full = urlparse(full_url)
                        
                        # Only follow link if it's the same domain
                        if parsed_full.netloc == base_domain:
                            queue.append((full_url, depth + 1))
                            
            except Exception as page_err:
                err_msg = f"Failed to scrape {normalized_url}: {str(page_err)}"
                print(err_msg)
                job["errors"].append(err_msg)
            finally:
                if page:
                    await page.close()
                    
        # Successfully crawled
        job["status"] = "completed"
        job["progress"] = 100.0
        print(f"Completed crawling {base_url}. Total pages crawled: {len(crawled_results)}")
        return crawled_results
        
    except Exception as err:
        
        error_msg = f"Crawl job failed: {str(err)}"
        print(error_msg)
        job["status"] = "failed"
        job["errors"].append(error_msg)
        return crawled_results

        
    finally:
        if browser:
            await browser.close()
        if pw:
            await pw.stop()
