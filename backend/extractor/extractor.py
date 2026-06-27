import io
import re
import trafilatura
from bs4 import BeautifulSoup
from pypdf import PdfReader
from typing import List, Dict, Tuple

def extract_text_bs4(html_content: str) -> str:
    soup = BeautifulSoup(html_content, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
        tag.decompose()
    raw_text = soup.get_text(separator="\n")
    lines = []
    for line in raw_text.splitlines():
        line = line.strip()
        if line and len(line) > 1:
            lines.append(line)
    return "\n".join(lines)

def extract_text_from_html(html_content: str) -> str:
    """
    Extracts main body text from HTML using Trafilatura, with a robust BeautifulSoup fallback.
    """
    if not html_content:
        return ""
    
    # Use trafilatura to extract clean main text content
    text = trafilatura.extract(
        html_content, 
        include_comments=False, 
        include_tables=False, # We handle tables separately for better control
        no_fallback=False
    )
    
    # Fallback to BeautifulSoup if Trafilatura fails or returns insufficient content (< 1200 chars)
    if not text or len(text) < 1200:
        bs_text = extract_text_bs4(html_content)
        if len(bs_text) > (len(text) if text else 0):
            text = bs_text
        
    # Clean up whitespace
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    clean_text = "\n".join(chunk for chunk in chunks if chunk)
    return clean_text


def extract_tables_from_html(html_content: str) -> str:
    """
    Parses HTML tables and converts them to Markdown format for the RAG engine.
    """
    if not html_content:
        return ""
        
    soup = BeautifulSoup(html_content, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        return ""
        
    tables_markdown = []
    for idx, table in enumerate(tables):
        rows = []
        for tr in table.find_all("tr"):
            cells = [td.get_text().strip() for td in tr.find_all(["td", "th"])]
            if cells:
                # Remove extra internal newlines/spaces
                cleaned_cells = [re.sub(r'\s+', ' ', c) for c in cells]
                rows.append("| " + " | ".join(cleaned_cells) + " |")
        
        if rows:
            # Construct a basic markdown table
            markdown_repr = f"### Table {idx + 1}\n" + "\n".join(rows) + "\n"
            tables_markdown.append(markdown_repr)
            
    return "\n\n".join(tables_markdown)

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    Extracts text from PDF bytes using PyPDF.
    """
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                text += f"\n--- PDF Page {i+1} ---\n{page_text}\n"
        return text.strip()
    except Exception as e:
        print(f"Error parsing PDF content: {e}")
        return ""

def recursive_split_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 150) -> List[str]:
    """
    Splits text recursively by character separators to ensure natural chunks.
    """
    if not text:
        return []
        
    separators = ["\n\n", "\n", ". ", " ", ""]
    chunks = []
    
    def split_recursive(current_text: str, current_separator_idx: int):
        if len(current_text) <= chunk_size:
            chunks.append(current_text.strip())
            return
            
        separator = separators[current_separator_idx]
        if separator == "":
            # Hard limit chunking if no separator is found
            start = 0
            while start < len(current_text):
                end = min(start + chunk_size, len(current_text))
                chunks.append(current_text[start:end].strip())
                start += chunk_size - chunk_overlap
            return
            
        # Split by separator
        parts = current_text.split(separator)
        current_chunk = []
        current_length = 0
        
        for part in parts:
            part_len = len(part) + (len(separator) if current_chunk else 0)
            if current_length + part_len <= chunk_size:
                current_chunk.append(part)
                current_length += part_len
            else:
                if current_chunk:
                    # Join previous parts
                    joined = separator.join(current_chunk)
                    chunks.append(joined.strip())
                    
                    # Retain overlap from current chunk to next chunk
                    # Simple heuristic: keep last few parts that fit within chunk_overlap
                    overlap_parts = []
                    overlap_len = 0
                    for p in reversed(current_chunk):
                        if overlap_len + len(p) <= chunk_overlap:
                            overlap_parts.insert(0, p)
                            overlap_len += len(p)
                        else:
                            break
                    current_chunk = overlap_parts + [part]
                    current_length = sum(len(x) for x in current_chunk) + (len(separator) * (len(current_chunk) - 1))
                else:
                    # Single part exceeds chunk_size, split recursively
                    split_recursive(part, current_separator_idx + 1)
                    
        if current_chunk:
            chunks.append(separator.join(current_chunk).strip())
            
    split_recursive(text, 0)
    # Remove empty chunks and duplicates
    return [c for c in chunks if c]
