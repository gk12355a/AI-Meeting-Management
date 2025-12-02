import requests
import os
import chromadb
import google.generativeai as genai
from dotenv import load_dotenv

# 1. Cấu hình môi trường & URL chuẩn hóa
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- LOGIC XỬ LÝ URL THÔNG MINH ---
# Đảm bảo URL luôn kết thúc đúng chuẩn /api/v1 bất kể cấu hình .env thế nào
raw_backend_url = os.getenv("JAVA_BACKEND_URL", "http://localhost:8080")
raw_backend_url = raw_backend_url.rstrip("/") # Xóa dấu / ở cuối nếu thừa

if raw_backend_url.endswith("/api/v1"):
    API_BASE_URL = raw_backend_url
else:
    API_BASE_URL = f"{raw_backend_url}/api/v1"

print(f"[INFO] Tools connected to: {API_BASE_URL}")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# --- RAG Configuration ---
policy_collection = None
try:
    chroma_client = chromadb.PersistentClient(path="./chroma_db")
    policy_collection = chroma_client.get_or_create_collection(name="meeting_policies")
except Exception as e:
    print(f"[WARN] ChromaDB connection failed. RAG features disabled. Error: {e}")

def _get_headers(token: str):
    if not token.startswith("Bearer "):
        token = f"Bearer {token}"
    return {
        "Authorization": token,
        "Content-Type": "application/json"
    }

# --- Retrieval Tools (Các hàm tra cứu) ---

def search_policy(token: str, query: str):
    """Tra cứu chính sách từ Vector DB."""
    if not policy_collection:
        return "Policy search service is unavailable."
    
    try:
        query_embedding = genai.embed_content(
            model="models/text-embedding-004",
            content=query,
            task_type="retrieval_query"
        )['embedding']
        
        results = policy_collection.query(
            query_embeddings=[query_embedding],
            n_results=2
        )
        
        if results['documents'] and results['documents'][0]:
            context = "\n---\n".join(results['documents'][0])
            return f"Relevant policy documents:\n{context}"
        return "No relevant policy found."
    except Exception as e:
        return f"Error searching policy: {str(e)}"

def search_users(token: str, query: str):
    url = f"{API_BASE_URL}/users/search"
    params = {"query": query}
    try:
        response = requests.get(url, headers=_get_headers(token), params=params)
        return response.json() if response.status_code == 200 else {"error": response.text}
    except Exception as e:
        return {"error": str(e)}

def get_rooms(token: str):
    url = f"{API_BASE_URL}/rooms"
    try:
        response = requests.get(url, headers=_get_headers(token))
        return response.json() if response.status_code == 200 else {"error": response.text}
    except Exception as e:
        return {"error": str(e)}

def get_devices(token: str):
    url = f"{API_BASE_URL}/devices"
    try:
        response = requests.get(url, headers=_get_headers(token))
        return response.json() if response.status_code == 200 else {"error": response.text}
    except Exception as e:
        return {"error": str(e)}

def find_available_rooms(token: str, start_time: str, end_time: str, capacity: int = 5):
    url = f"{API_BASE_URL}/rooms/available"
    params = {"startTime": start_time, "endTime": end_time, "capacity": capacity}
    try:
        response = requests.get(url, headers=_get_headers(token), params=params)
        return response.json() if response.status_code == 200 else {"error": response.text}
    except Exception as e:
        return {"error": str(e)}

def get_my_meetings(token: str, date_filter: str = None):
    """
    Xem lịch họp của tôi.
    Args:
        token: JWT Token
        date_filter: (Optional) Ngày cần lọc (Format: YYYY-MM-DD). Ví dụ: '2025-11-29'.
    """
    url = f"{API_BASE_URL}/meetings/my-meetings"
    try:
        # Lấy số lượng lớn một chút để đảm bảo lọc được ngày cần tìm
        response = requests.get(url, headers=_get_headers(token), params={"size": 50})
        
        if response.status_code == 200:
            data = response.json()
            meetings = data.get("content", [])
            
            # --- LOGIC LỌC THEO NGÀY (NẾU CÓ) ---
            if date_filter:
                filtered_meetings = []
                for m in meetings:
                    # startTime dạng "2025-11-29T09:00:00"
                    start_time = m.get("startTime", "")
                    if start_time.startswith(date_filter):
                        filtered_meetings.append(m)
                
                if not filtered_meetings:
                    return f"Hệ thống: Không tìm thấy lịch họp nào của bạn vào ngày {date_filter}."
                
                return filtered_meetings
            
            return meetings
            
        return {"error": response.text}
    except Exception as e:
        return {"error": str(e)}

def get_meeting_details(token: str, meeting_id: int):
    url = f"{API_BASE_URL}/meetings/{meeting_id}"
    try:
        response = requests.get(url, headers=_get_headers(token))
        return response.json() if response.status_code == 200 else {"error": response.text}
    except Exception as e:
        return {"error": str(e)}

def get_notifications(token: str):
    url = f"{API_BASE_URL}/notifications"
    try:
        response = requests.get(url, headers=_get_headers(token))
        if response.status_code == 200:
            return response.json().get("content", [])
        return {"error": response.text}
    except Exception as e:
        return {"error": str(e)}

def get_contact_groups(token: str):
    url = f"{API_BASE_URL}/contact-groups"
    try:
        response = requests.get(url, headers=_get_headers(token))
        return response.json() if response.status_code == 200 else {"error": response.text}
    except Exception as e:
        return {"error": str(e)}

def suggest_meeting_time(token: str, participant_ids: list[int], start_date: str, end_date: str, duration: int = 30):
    url = f"{API_BASE_URL}/meetings/suggest-time"
    payload = {
        "participantIds": participant_ids,
        "rangeStart": start_date,
        "rangeEnd": end_date,
        "durationMinutes": duration
    }
    try:
        response = requests.post(url, headers=_get_headers(token), json=payload)
        return response.json() if response.status_code == 200 else {"error": response.text}
    except Exception as e:
        return {"error": str(e)}

def find_available_devices(token: str, start_time: str, end_time: str):
    """Tìm thiết bị rảnh theo giờ."""
    url = f"{API_BASE_URL}/devices/available"
    params = {"startTime": start_time, "endTime": end_time}
    try:
        response = requests.get(url, headers=_get_headers(token), params=params)
        return response.json() if response.status_code == 200 else {"error": response.text}
    except Exception as e:
        return {"error": str(e)}

# --- Action Tools (Các hàm Ghi/Sửa/Xóa) ---

def create_meeting(token: str, title: str, start_time: str, end_time: str, room_id: int, 
                   participant_ids: list[int] = [], description: str = "", 
                   device_ids: list[int] = [], recurrence: dict = None):
    url = f"{API_BASE_URL}/meetings"
    payload = {
        "title": title, "description": description,
        "startTime": start_time, "endTime": end_time,
        "roomId": room_id, "participantIds": participant_ids,
        "deviceIds": device_ids, "guestEmails": []
    }
    
    # Quan trọng: Map recurrence dict từ Agent thành field 'recurrenceRule' của Java
    if recurrence: 
        payload["recurrenceRule"] = recurrence
    
    try:
        # Debug log
        print(f"DEBUG: Creating meeting at {url} with payload: {payload}")
        response = requests.post(url, headers=_get_headers(token), json=payload)
        return response.json() if response.status_code in [200, 201] else {"error": response.text}
    except Exception as e:
        return {"error": str(e)}

def cancel_meeting(token: str, meeting_id: int, reason: str):
    url = f"{API_BASE_URL}/meetings/{meeting_id}"
    try:
        response = requests.request("DELETE", url, headers=_get_headers(token), json={"reason": reason})
        return {"success": True, "message": "Cancelled successfully."} if response.status_code == 200 else {"error": response.text}
    except Exception as e:
        return {"error": str(e)}

def update_meeting(token: str, meeting_id: int, title: str, start_time: str, end_time: str, room_id: int, 
                   participant_ids: list[int], description: str = ""):
    url = f"{API_BASE_URL}/meetings/{meeting_id}"
    payload = {
        "title": title, "description": description,
        "startTime": start_time, "endTime": end_time,
        "roomId": room_id, "participantIds": participant_ids,
        "deviceIds": [], "guestEmails": []
    }
    try:
        response = requests.put(url, headers=_get_headers(token), json=payload)
        return response.json() if response.status_code == 200 else {"error": response.text}
    except Exception as e:
        return {"error": str(e)}

def respond_invitation(token: str, meeting_id: int, status: str):
    url = f"{API_BASE_URL}/meetings/{meeting_id}/respond"
    try:
        response = requests.post(url, headers=_get_headers(token), json={"status": status})
        return {"success": True} if response.status_code == 200 else {"error": response.text}
    except Exception as e:
        return {"error": str(e)}

def check_in_meeting(token: str, room_id: int):
    url = f"{API_BASE_URL}/meetings/check-in"
    try:
        response = requests.post(url, headers=_get_headers(token), json={"roomId": room_id})
        return {"success": True, "msg": response.text} if response.status_code == 200 else {"error": response.text}
    except Exception as e:
        return {"error": str(e)}

def check_in_by_qr(token: str, qr_code: str):
    """Check-in bằng chuỗi mã QR."""
    url = f"{API_BASE_URL}/meetings/check-in/qr"
    payload = {"qrCode": qr_code}
    try:
        response = requests.post(url, headers=_get_headers(token), json=payload)
        return {"success": True, "message": response.text} if response.status_code == 200 else {"error": response.text}
    except Exception as e:
        return {"error": str(e)}

def update_meeting_series(token: str, series_id: str, title: str, start_time: str, end_time: str, 
                          room_id: int, participant_ids: list[int], description: str = "", recurrence: dict = None):
    """Cập nhật toàn bộ CHUỖI lịch định kỳ."""
    url = f"{API_BASE_URL}/meetings/series/{series_id}"
    payload = {
        "title": title, "description": description,
        "startTime": start_time, "endTime": end_time,
        "roomId": room_id, "participantIds": participant_ids,
        "deviceIds": [], "guestEmails": []
    }
    if recurrence: 
        payload["recurrenceRule"] = recurrence
    
    try:
        response = requests.put(url, headers=_get_headers(token), json=payload)
        return response.json() if response.status_code == 200 else {"error": response.text}
    except Exception as e:
        return {"error": str(e)}

def cancel_meeting_series(token: str, series_id: str, reason: str):
    """Hủy toàn bộ CHUỖI lịch định kỳ."""
    url = f"{API_BASE_URL}/meetings/series/{series_id}"
    try:
        response = requests.request("DELETE", url, headers=_get_headers(token), json={"reason": reason})
        return {"success": True, "message": "Đã hủy chuỗi thành công."} if response.status_code == 200 else {"error": response.text}
    except Exception as e:
        return {"error": str(e)}

# Export tool mapping
available_tools = {
    "search_policy": search_policy,
    "search_users": search_users, "get_rooms": get_rooms, "get_devices": get_devices,
    "find_available_rooms": find_available_rooms, "get_my_meetings": get_my_meetings,
    "get_meeting_details": get_meeting_details, "get_notifications": get_notifications,
    "get_contact_groups": get_contact_groups, "suggest_meeting_time": suggest_meeting_time,
    "create_meeting": create_meeting, "cancel_meeting": cancel_meeting,
    "update_meeting": update_meeting, "respond_invitation": respond_invitation,
    "check_in_meeting": check_in_meeting, "find_available_devices": find_available_devices,
    "check_in_by_qr": check_in_by_qr,
    "update_meeting_series": update_meeting_series,
    "cancel_meeting_series": cancel_meeting_series
}