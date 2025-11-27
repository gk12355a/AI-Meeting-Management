"""
Ingest script: Nạp tài liệu chính sách họp nội bộ vào ChromaDB để phục vụ RAG (Retrieval-Augmented Generation)

Yêu cầu:
- File data/policy.txt tồn tại và chứa nội dung quy định (mỗi đoạn cách nhau bằng dòng trống)
- GEMINI_API_KEY được đặt trong file .env
- Chạy script này mỗi khi cập nhật chính sách mới

Sau khi chạy xong → có thể dùng trong tools/search_policy.py
"""

import os
import chromadb
import google.generativeai as genai
from dotenv import load_dotenv
from typing import List



# 1. CẤU HÌNH MÔI TRƯỜNG & GEMINI

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY không được tìm thấy trong file .env")

genai.configure(api_key=GEMINI_API_KEY)



# 2. KHỞI TẠO CHROMADB (Persistent - lưu trữ trên disk)

CHROMA_DB_PATH = "./chroma_db"
COLLECTION_NAME = "meeting_policies"

chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

# Xóa collection cũ nếu tồn tại → đảm bảo dữ liệu luôn tươi mới khi ingest lại
try:
    chroma_client.delete_collection(COLLECTION_NAME)
    print(f"Đã xóa collection cũ: {COLLECTION_NAME}")
except Exception:
    # Collection chưa tồn tại → bình thường
    pass

# Tạo collection mới (hoặc lấy lại nếu đã có)
collection = chroma_client.get_or_create_collection(name=COLLECTION_NAME)
print(f"Collection '{COLLECTION_NAME}' đã sẵn sàng tại {CHROMA_DB_PATH}")



# 3. HÀM TẠO EMBEDDING

def get_embedding(text: str) -> List[float]:
    """
    Chuyển đổi đoạn văn bản thành vector embedding sử dụng Gemini text-embedding-004.
    
    Args:
        text: Đoạn văn bản cần embedding (nên < 8192 tokens)
    
    Returns:
        List[float]: Vector 768 chiều
    """
    try:
        result = genai.embed_content(
            model="models/text-embedding-004",
            content=text.strip(),
            task_type="retrieval_document",    # Tối ưu cho việc lưu tài liệu
        )
        return result["embedding"]
    except Exception as exc:
        raise RuntimeError(f"Lỗi khi tạo embedding: {exc}")



# 4. CHUNKING & INGESTION LOGIC

def ingest_policy_documents(source_file: str = "data/policy.txt") -> None:
    """
    Đọc file chính sách, chia nhỏ theo đoạn, tạo embedding và lưu vào ChromaDB.
    """
    print("Bắt đầu quá trình nạp dữ liệu chính sách vào vector database...")

    # Đọc file gốc
    if not os.path.exists(source_file):
        raise FileNotFoundError(f"Không tìm thấy file chính sách: {source_file}")

    with open(source_file, "r", encoding="utf-8") as f:
        raw_text = f.read()

    if not raw_text.strip():
        raise ValueError(f"File {source_file} rỗng hoặc không có nội dung hợp lệ.")

    # Chia nhỏ theo đoạn trống (paragraph-based chunking)
    # Cách này giữ nguyên ngữ nghĩa tốt hơn so với chia theo số ký tự
    chunks = [chunk.strip() for chunk in raw_text.split("\n\n") if chunk.strip()]
    
    if not chunks:
        raise ValueError("Không tìm thấy đoạn văn bản nào để xử lý. Kiểm tra định dạng file.")

    print(f"Đã chia thành {len(chunks)} đoạn văn bản.")

    # Tạo embedding cho từng chunk
    documents = []
    embeddings = []
    ids = []
    metadatas = []

    print("Đang tạo embeddings (có thể mất vài giây đến vài phút tùy kích thước)...")
    for idx, chunk in enumerate(chunks):
        try:
            embedding = get_embedding(chunk)
            
            doc_id = f"policy_{idx:04d}"
            documents.append(chunk)
            embeddings.append(embedding)
            ids.append(doc_id)
            metadatas.append({
                "source": source_file,
                "chunk_index": idx,
                "char_length": len(chunk)
            })

            print(f"   Processed [{idx + 1}/{len(chunks)}] Đoạn {idx + 1} → {len(chunk):,} ký tự")

        except Exception as exc:
            print(f"   Failed Lỗi tại đoạn {idx + 1}: {exc}")
            continue

    # Lưu vào ChromaDB (batch insert)
    if documents:
        collection.add(
            documents=documents,
            embeddings=embeddings,
            ids=ids,
            metadatas=metadatas
        )
        print(f"\nTHÀNH CÔNG! Đã nạp {len(documents)} đoạn chính sách vào ChromaDB.")
        print(f"   → Collection: {COLLECTION_NAME}")
        print(f"   → Tổng số vector: {collection.count()}")
    else:
        print("\nKhông có dữ liệu nào được nạp. Vui lòng kiểm tra file nguồn và kết nối mạng.")



# 5. ENTRY POINT

if __name__ == "__main__":
    try:
        ingest_policy_documents()
        print("\nQuá trình ingest hoàn tất. Bạn có thể khởi động bot để tra cứu chính sách!")
    except Exception as e:
        print(f"\nLỗi nghiêm trọng trong quá trình ingest: {e}")
        raise