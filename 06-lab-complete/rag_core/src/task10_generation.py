"""
Task 10 — Generation Có Citation.
"""

import os
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

from .task9_retrieval_pipeline import retrieve

# =============================================================================
# CONFIGURATION 
# =============================================================================

# top_k: Số chunks đưa vào context
# Chọn 5 vì: đủ evidence mà không quá dài gây lost in the middle
TOP_K = 5

# top_p (nucleus sampling): Xác suất tích luỹ cho token generation
# Chọn 0.9 vì: đủ diverse nhưng không quá random
TOP_P = 0.9

# temperature: Độ ngẫu nhiên của output
# Chọn 0.3 vì: RAG cần factual, ít sáng tạo
TEMPERATURE = 0.3


# =============================================================================
# SYSTEM PROMPT
# =============================================================================

SYSTEM_PROMPT = """<instructions>
Answer the following question comprehensively in Vietnamese.
For every statement of fact or claim, immediately insert a citation in brackets linking to the specific source.
</instructions>

<citation_rules>
- Legal document citation format: [Luật Phòng chống ma tuý 2021, Điều X] or [Nghị định 57/2022/NĐ-CP, Điều Y]
- News article citation format: [VnExpress, 2024] or [Lao Động, 2024]
</citation_rules>

<fallback_policy>
If the information is not explicitly stated in the provided context, state: 'Tôi không thể xác minh thông tin này từ nguồn hiện có' rather than guessing. Do not manufacture details.
</fallback_policy>

<constraints>
- Only use information from the provided context.
- Every factual claim MUST have a citation.
- Structure your answer with clear paragraphs.
</constraints>"""


# =============================================================================
# DOCUMENT REORDERING (tránh lost in the middle)
# =============================================================================

def reorder_for_llm(chunks: list[dict]) -> list[dict]:
    """
    Sắp xếp chunks để tránh "lost in the middle" effect.
    LLM nhớ tốt thông tin ở ĐẦU và CUỐI prompt, quên thông tin ở GIỮA.
    """
    if len(chunks) <= 2:
        return chunks

    reordered = []
    # Lấy các chunk ở vị trí chẵn (0, 2, 4...) đặt ở đầu
    for i in range(0, len(chunks), 2):
        reordered.append(chunks[i])
    # Lấy các chunk ở vị trí lẻ (1, 3, 5...) đặt ở cuối, theo thứ tự ngược
    start_odd = len(chunks) - 1
    if start_odd % 2 == 0:
        start_odd -= 1
    for i in range(start_odd, 0, -2):
        reordered.append(chunks[i])

    return reordered


# =============================================================================
# CONTEXT FORMATTING
# =============================================================================

def format_context(chunks: list[dict]) -> str:
    """
    Format chunks thành context string cho prompt.
    """
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        source = chunk.get("metadata", {}).get("source", f"Source {i}")
        doc_type = chunk.get("metadata", {}).get("type", "unknown")
        context_parts.append(
            f"[Document {i} | Source: {source} | Type: {doc_type}]\n"
            f"{chunk['content']}\n"
        )
    return "\n---\n".join(context_parts)


# =============================================================================
# GENERATION
# =============================================================================

def generate_with_citation(query: str, top_k: int = TOP_K) -> dict:
    """
    End-to-end RAG generation có citation.
    """
    # Step 1: Retrieve
    chunks = retrieve(query, top_k=top_k)
    
    if not chunks:
        return {
            "answer": "Không tìm thấy thông tin nào liên quan đến câu hỏi.",
            "sources": [],
            "retrieval_source": "none"
        }

    # Step 2: Reorder
    reordered = reorder_for_llm(chunks)

    # Step 3: Format context
    context = format_context(reordered)

    # Step 4: Build prompt
    user_message = f"""Context:\n{context}\n\n---\n\nQuestion: {query}"""

    # Step 5: Call LLM
    openai_key = os.getenv("OPENAI_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")

    if gemini_key:
        try:
            import requests
            import json
            # Call Gemini API via REST to avoid library dependencies
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key={gemini_key}"
            headers = {"Content-Type": "application/json"}
            
            # Formulate prompt combined with system prompt for Gemini
            prompt_text = f"{SYSTEM_PROMPT}\n\nContext:\n{context}\n\n---\n\nQuestion: {query}"
            
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt_text}
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": TEMPERATURE,
                    "topP": TOP_P
                }
            }
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            resp_data = response.json()
            
            # Extract content from Gemini response
            answer = resp_data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            logger.error(f"Gemini Generation error: {e}")
            answer = f"LỖI Gemini Generation: {e}"
    elif openai_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_key)

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message}
                ],
                temperature=TEMPERATURE,
                top_p=TOP_P,
            )
            answer = response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI Generation error: {e}")
            answer = f"LỖI OpenAI Generation: {e}"
    else:
        logger.warning("Không tìm thấy GEMINI_API_KEY hoặc OPENAI_API_KEY. Không thể chạy Generation.")
        return {
            "answer": "LỖI: Chưa cấu hình GEMINI_API_KEY hoặc OPENAI_API_KEY trong file .env.",
            "sources": chunks,
            "retrieval_source": chunks[0].get("source", "hybrid") if chunks else "none"
        }

    # Step 6: Return
    return {
        "answer": answer,
        "sources": chunks,
        "retrieval_source": chunks[0].get("source", "hybrid") if chunks else "none"
    }


if __name__ == "__main__":
    import sys
    # Reconfigure stdout to use UTF-8 on Windows to avoid UnicodeEncodeError
    if sys.platform.startswith('win'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except AttributeError:
            pass # older python versions
            
    test_queries = [
        "Hình phạt cho tội tàng trữ trái phép chất ma tuý theo pháp luật Việt Nam?",
        "Những nghệ sĩ nào đã bị bắt vì liên quan tới ma tuý?",
        "Quy trình cai nghiện bắt buộc theo Luật Phòng chống ma tuý 2021?",
    ]

    output_lines = []
    output_lines.append("# RAG Pipeline Execution Results\n")
    output_lines.append(f"Ran on: {sys.version}\n")

    for q in test_queries:
        header = f"\nQ: {q}"
        print(f"\n{'='*70}")
        print(header)
        print("=" * 70)
        
        result = generate_with_citation(q)
        
        ans = result['answer']
        source_info = f"[Sources: {len(result['sources'])} chunks | via {result['retrieval_source']}]"
        
        print(f"\nA: {ans}")
        print(f"\n{source_info}")
        
        output_lines.append(f"## {q}\n")
        output_lines.append(f"**Answer:**\n{ans}\n")
        output_lines.append(f"*{source_info}*\n")
        output_lines.append("---\n")

    # Write output to markdown file for easy viewing
    results_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "rag_results.md")
    os.makedirs(os.path.dirname(results_path), exist_ok=True)
    with open(results_path, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))
    
    print(f"\n[SUCCESS] Results written to: {results_path}")


