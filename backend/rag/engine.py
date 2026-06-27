from typing import List, Dict, Any, Optional
from openai import OpenAI
from backend.config import settings
from backend.embeddings.embedder import embedder
from backend.vectorstore.database import db_manager
from backend.models.schemas import Message

def run_rag_query(
    query: str,
    website_url: Optional[str] = None,
    chat_history: Optional[List[Message]] = None,
    model_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes a RAG query:
    1. Embeds user query.
    2. Retrieves top similarities matching the query.
    3. Feeds structured prompt (retrieved contexts + chat history) to Gemini via OpenRouter.
    4. Formulates citations.
    """
    if not model_name:
        model_name = settings.LLM_MODEL
        
    # 1. Embed query
    query_embeddings = embedder.embed_texts([query])
    if not query_embeddings:
        return {
            "answer": "Failed to compute embedding representation for your query.",
            "sources": []
        }
    query_emb = query_embeddings[0]
    
    # 2. Retrieve similarity results from database
    # website_url is the base domain (e.g. https://example.com)
    retrieved = db_manager.query(query_embedding=query_emb, website_url=website_url, k=5)
    
    if not retrieved:
        return {
            "answer": "No indexed data found for the selected website(s). Please crawl and index the site first.",
            "sources": []
        }
        
    # 3. Build context block
    context_chunks = []
    for idx, item in enumerate(retrieved):
        meta = item["metadata"]
        context_chunks.append(
            f"[Source {idx + 1}]\n"
            f"URL: {meta.get('source')}\n"
            f"Title: {meta.get('title')}\n"
            f"Content Type: {meta.get('content_type')}\n"
            f"Content: {item['chunk']}"
        )
    context_block = "\n\n---\n\n".join(context_chunks)
    
    # 4. Construct message queue
    messages = []
    
    # System Instructions
    messages.append({
        "role": "system",
        "content": (
            "You are a professional RAG assistant designed to answer user questions based STRICTLY on the retrieved context from crawled website details.\n"
            "Guidelines:\n"
            "- Answer the user's question accurately using ONLY the provided website contexts.\n"
            "- Cite the sources by referring to their source index/number in brackets (e.g. [Source 1], [Source 2]) whenever you reference their content.\n"
            "- If the exact answer to the user's question cannot be found with absolute certainty in the provided contexts, do NOT simply say 'I cannot find the answer in the crawled website details.' Instead, provide a helpful summary of whatever relevant/partial details are present in the contexts regarding the entities and topics mentioned (while citing the sources). Clearly state what relevant information is available and what part of the question cannot be answered. Only if there is absolutely no related information at all should you say 'I cannot find the answer in the crawled website details.'\n"
            "- Do NOT make up facts or utilize external database info that is not in the context.\n"
            "- Keep your response clear, well-structured, and concise."
        )
    })
    
    # Map chat history (converting schema to dictionary)
    if chat_history:
        for msg in chat_history:
            role = msg.role if msg.role in ["user", "assistant", "system"] else "user"
            # Normalize assistant/user roles to openai standard
            messages.append({"role": role, "content": msg.content})

            
    # Inject active contexts + query
    user_payload = (
        f"Retrieved Website Context:\n"
        f"=======================\n"
        f"{context_block}\n"
        f"=======================\n\n"
        f"User Question: {query}"
    )
    messages.append({"role": "user", "content": user_payload})
    
    # 5. Send request to OpenAI-compatible OpenRouter API
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        return {
            "answer": "Error: GEMINI_API_KEY is not defined in the environment. Please check your .env configuration.",
            "sources": []
        }
        
    try:
        client = OpenAI(
            base_url=settings.OPENROUTER_BASE_URL,
            api_key=api_key
        )
        
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.2,
            max_tokens=65535
        )

        
        answer = response.choices[0].message.content
        
        # Format sources list
        sources_list = []
        seen_urls = set()
        for r in retrieved:
            meta = r["metadata"]
            src_url = meta.get("source", "")
            title = meta.get("title", "Untitled Page")
            c_type = meta.get("content_type", "text")
            score = r["score"]
            
            if src_url and src_url not in seen_urls:
                seen_urls.add(src_url)
                sources_list.append({
                    "source": src_url,
                    "title": title,
                    "content_type": c_type,
                    "score": score
                })
                
        return {
            "answer": answer,
            "sources": sources_list
        }
        
    except Exception as e:
        print(f"Error calling OpenRouter API: {e}")
        return {
            "answer": f"Error calling Language Model: {str(e)}",
            "sources": []
        }
