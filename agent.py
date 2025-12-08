import google.generativeai as genai
import os
import json
import redis
from dotenv import load_dotenv
from tools import available_tools
from datetime import datetime

# Google Generative AI Low-level imports
from google.ai.generativelanguage import FunctionDeclaration, Tool, Schema, Type
from google.ai.generativelanguage import Content, Part, FunctionResponse

# 1. Configuration
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("Missing GEMINI_API_KEY in .env file")

genai.configure(api_key=api_key)

# 2. Redis Connection
redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = int(os.getenv("REDIS_PORT", 6379))
redis_password = os.getenv("REDIS_PASSWORD")
redis_db = int(os.getenv("REDIS_DB", 0))
if redis_password == "": redis_password = None

try:
    redis_client = redis.Redis(
        host=redis_host, port=redis_port, password=redis_password, db=redis_db,
        decode_responses=True, socket_connect_timeout=5
    )
    redis_client.ping()
    print(f"[INFO] Redis connected: {redis_host}:{redis_port}")
except Exception as e:
    print(f"[ERROR] Redis connection failed: {e}")
    redis_client = None

# 3. SCHEMA DEFINITIONS (Định nghĩa cấu trúc dữ liệu chuẩn)

# --- RECURRENCE SCHEMA ---
recurrence_schema = Schema(
    type=Type.OBJECT,
    properties={
        "frequency": Schema(
            type=Type.STRING,
            enum=["DAILY", "WEEKLY", "MONTHLY", "YEARLY"]
        ),
        "interval": Schema(type=Type.INTEGER, description="Ví dụ: 1 (mỗi tuần), 2 (mỗi 2 tuần)"),
        "repeatUntil": Schema(type=Type.STRING, description="Ngày kết thúc lặp. Format: YYYY-MM-DD"),
        "daysOfWeek": Schema(
            type=Type.ARRAY,
            items=Schema(
                type=Type.STRING,
                enum=["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
            )
        )
    },
    required=["frequency", "interval", "repeatUntil"]
)

# 4. TOOL DEFINITIONS

search_users_func = FunctionDeclaration(
    name="search_users", description="Tìm ID người dùng theo tên/email.",
    parameters=Schema(type=Type.OBJECT, properties={"query": Schema(type=Type.STRING)}, required=["query"])
)
get_rooms_func = FunctionDeclaration(
    name="get_rooms", description="Lấy danh sách tất cả phòng họp và ID.",
    parameters=Schema(type=Type.OBJECT, properties={})
)
find_avail_func = FunctionDeclaration(
    name="find_available_rooms", description="Tìm phòng trống theo giờ.",
    parameters=Schema(type=Type.OBJECT, properties={"start_time": Schema(type=Type.STRING), "end_time": Schema(type=Type.STRING), "capacity": Schema(type=Type.INTEGER)}, required=["start_time", "end_time"])
)
get_meetings_func = FunctionDeclaration(
    name="get_my_meetings", description="Xem lịch họp cá nhân. Dùng date_filter nếu cần lọc ngày cụ thể.",
    parameters=Schema(type=Type.OBJECT, properties={"date_filter": Schema(type=Type.STRING)})
)
get_details_func = FunctionDeclaration(
    name="get_meeting_details", description="Xem chi tiết 1 cuộc họp (để lấy seriesId).",
    parameters=Schema(type=Type.OBJECT, properties={"meeting_id": Schema(type=Type.INTEGER)}, required=["meeting_id"])
)

# --- CREATE MEETING ---
create_meeting_func = FunctionDeclaration(
    name="create_meeting", description="Tạo cuộc họp mới (đơn lẻ hoặc định kỳ).",
    parameters=Schema(
        type=Type.OBJECT, 
        properties={
            "title": Schema(type=Type.STRING), 
            "start_time": Schema(type=Type.STRING, description="ISO 8601 Format: YYYY-MM-DDTHH:mm:ss"), 
            "end_time": Schema(type=Type.STRING, description="ISO 8601 Format: YYYY-MM-DDTHH:mm:ss"),
            "room_id": Schema(type=Type.INTEGER), 
            "participant_ids": Schema(type=Type.ARRAY, items=Schema(type=Type.INTEGER)),
            "device_ids": Schema(type=Type.ARRAY, items=Schema(type=Type.INTEGER)), 
            "description": Schema(type=Type.STRING),
            "recurrence": recurrence_schema
        }, 
        required=["title", "start_time", "end_time", "room_id"]
    )
)

cancel_meeting_func = FunctionDeclaration(
    name="cancel_meeting", description="Hủy MỘT cuộc họp lẻ.",
    parameters=Schema(type=Type.OBJECT, properties={"meeting_id": Schema(type=Type.INTEGER), "reason": Schema(type=Type.STRING)}, required=["meeting_id", "reason"])
)
get_devices_func = FunctionDeclaration(
    name="get_devices", description="Lấy danh sách thiết bị.",
    parameters=Schema(type=Type.OBJECT, properties={})
)
update_meeting_func = FunctionDeclaration(
    name="update_meeting", description="Sửa MỘT cuộc họp lẻ.",
    parameters=Schema(type=Type.OBJECT, properties={
        "meeting_id": Schema(type=Type.INTEGER), "title": Schema(type=Type.STRING), "start_time": Schema(type=Type.STRING),
        "end_time": Schema(type=Type.STRING), "room_id": Schema(type=Type.INTEGER), "participant_ids": Schema(type=Type.ARRAY, items=Schema(type=Type.INTEGER)), "description": Schema(type=Type.STRING)
    }, required=["meeting_id", "title", "start_time", "end_time", "room_id"])
)
respond_func = FunctionDeclaration(
    name="respond_invitation", description="Phản hồi mời họp.",
    parameters=Schema(type=Type.OBJECT, properties={"meeting_id": Schema(type=Type.INTEGER), "status": Schema(type=Type.STRING, enum=["ACCEPTED", "DECLINED"])}, required=["meeting_id", "status"])
)
notif_func = FunctionDeclaration(
    name="get_notifications", description="Xem thông báo.",
    parameters=Schema(type=Type.OBJECT, properties={})
)
checkin_func = FunctionDeclaration(
    name="check_in_meeting", description="Check-in vào phòng.",
    parameters=Schema(type=Type.OBJECT, properties={"room_id": Schema(type=Type.INTEGER)}, required=["room_id"])
)
suggest_time_func = FunctionDeclaration(
    name="suggest_meeting_time", description="Gợi ý giờ họp phù hợp cho các thành viên.",
    parameters=Schema(type=Type.OBJECT, properties={"participant_ids": Schema(type=Type.ARRAY, items=Schema(type=Type.INTEGER)), "start_date": Schema(type=Type.STRING), "end_date": Schema(type=Type.STRING), "duration": Schema(type=Type.INTEGER)}, required=["participant_ids", "start_date", "end_date"])
)
get_groups_func = FunctionDeclaration(
    name="get_contact_groups", description="Lấy danh sách nhóm liên hệ.",
    parameters=Schema(type=Type.OBJECT, properties={})
)
search_policy_func = FunctionDeclaration(
    name="search_policy", description="Tra cứu quy định, chính sách công ty.",
    parameters=Schema(type=Type.OBJECT, properties={"query": Schema(type=Type.STRING)}, required=["query"])
)
find_avail_devices_func = FunctionDeclaration(
    name="find_available_devices", description="Tìm thiết bị trống.",
    parameters=Schema(type=Type.OBJECT, properties={"start_time": Schema(type=Type.STRING), "end_time": Schema(type=Type.STRING)}, required=["start_time", "end_time"])
)
checkin_qr_func = FunctionDeclaration(
    name="check_in_by_qr", description="Check-in bằng mã QR code.",
    parameters=Schema(type=Type.OBJECT, properties={"qr_code": Schema(type=Type.STRING)}, required=["qr_code"])
)

# --- SERIES TOOLS ---
cancel_series_func = FunctionDeclaration(
    name="cancel_meeting_series", description="Hủy TOÀN BỘ chuỗi lịch định kỳ.",
    parameters=Schema(type=Type.OBJECT, properties={"series_id": Schema(type=Type.STRING), "reason": Schema(type=Type.STRING)}, required=["series_id", "reason"])
)
update_series_func = FunctionDeclaration(
    name="update_meeting_series", description="Sửa TOÀN BỘ chuỗi lịch định kỳ.",
    parameters=Schema(
        type=Type.OBJECT, 
        properties={
            "series_id": Schema(type=Type.STRING), 
            "title": Schema(type=Type.STRING), 
            "start_time": Schema(type=Type.STRING),
            "end_time": Schema(type=Type.STRING), 
            "room_id": Schema(type=Type.INTEGER), 
            "participant_ids": Schema(type=Type.ARRAY, items=Schema(type=Type.INTEGER)),
            "description": Schema(type=Type.STRING),
            "recurrence": recurrence_schema
        }, 
        required=["series_id", "title", "start_time", "end_time", "room_id", "recurrence"]
    )
)

tools_list = [
    search_users_func, get_rooms_func, find_avail_func, get_meetings_func,
    get_details_func, create_meeting_func, cancel_meeting_func, update_meeting_func,
    get_devices_func, respond_func, notif_func, checkin_func,
    suggest_time_func, get_groups_func, search_policy_func,
    find_avail_devices_func, checkin_qr_func, cancel_series_func, update_series_func
]

meeting_tools = Tool(function_declarations=tools_list)
model = genai.GenerativeModel(model_name='models/gemini-2.5-flash', tools=[meeting_tools])

# 5. REDIS LOGIC
def get_chat_history(user_token: str):
    if not redis_client: return []
    key = f"chat_history:{user_token}"
    try:
        data = redis_client.get(key)
        if data:
            items = json.loads(data)
            return [Content(role=i["role"], parts=[Part(text=i["text"])]) for i in items if i.get("text")]
    except: pass
    return []

def save_chat_turn(user_token: str, user_msg: str, bot_msg: str):
    if not redis_client: return
    key = f"chat_history:{user_token}"
    try:
        data = redis_client.get(key)
        hist = json.loads(data) if data else []
        hist.append({"role": "user", "text": user_msg})
        hist.append({"role": "model", "text": bot_msg})
        if len(hist) > 20: hist = hist[-20:] 
        redis_client.set(key, json.dumps(hist))
        redis_client.expire(key, 1800) 
    except: pass

# 6. MAIN CHAT LOGIC (QUAN TRỌNG: ĐÃ THÊM LOGIC SỬA LỖI REPEATEDCOMPOSITE)
async def simple_chat(user_message: str, user_token: str):
    history = get_chat_history(user_token)
    chat = model.start_chat(history=history, enable_automatic_function_calling=False)
    
    now = datetime.now()
    current_time_str = now.strftime('%Y-%m-%d %H:%M:%S')
    today_date = now.strftime('%Y-%m-%d')
    
    system_instruction = f"""
    [VAI TRÒ] Bạn là Trợ lý Ảo CMC Meeting chuyên nghiệp.
    
    [THÔNG TIN HIỆN TẠI]
    - Thời gian thực: {current_time_str} (Thứ {now.weekday() + 2}).
    - Hôm nay là: {today_date}.
    
    [QUY TẮC XỬ LÝ QUAN TRỌNG - TUÂN THỦ TUYỆT ĐỐI]
    1. **TẠO LỊCH ĐỊNH KỲ:**
       - Nếu user nói "hàng tuần", "hàng ngày", "mỗi thứ 2"... -> Bắt buộc dùng tham số `recurrence`.
       - `frequency`: CHỈ CHẤP NHẬN: "DAILY", "WEEKLY", "MONTHLY", "YEARLY" (Viết hoa).
       - `daysOfWeek`: CHỈ CHẤP NHẬN: "MONDAY", "TUESDAY", ... (Viết hoa).
       
    2. **XỬ LÝ CHUỖI LỊCH (SERIES):**
       - Lịch định kỳ được quản lý bằng `seriesId` (String), KHÔNG phải `meeting_id` (Int).
       - Nếu user muốn sửa/hủy "toàn bộ chuỗi" hoặc "tất cả các buổi":
         - B1: Gọi `get_my_meetings` hoặc `get_meeting_details` để tìm `seriesId`.
         - B2: Gọi `update_meeting_series` hoặc `cancel_meeting_series`.
         
    3. **KHÔNG BỊA ĐẶT ID:**
       - Nếu user nói tên phòng (vd: "phòng sao hỏa"), BẮT BUỘC phải gọi `get_rooms` để tìm ID của nó trước.
       - Không được tự ý điền ID bừa bãi (vd: ID=1) nếu chưa xác nhận.
       
    4. **PHẢN HỒI:** Ngắn gọn, súc tích.
    """

    try:
        response = chat.send_message(f"{system_instruction}\nUser: {user_message}")
    except Exception as e:
        print(f"❌ Error Gemini: {e}")
        return "Hệ thống AI đang bận. Vui lòng thử lại sau."

    turn = 0
    max_turns = 8 
    
    while turn < max_turns:
        part = response.parts[0]
        
        if not part.function_call:
            bot_reply = response.text
            save_chat_turn(user_token, user_message, bot_reply)
            return bot_reply

        fc = part.function_call
        fname = fc.name
        args = fc.args
        print(f"🤖 [AI Action] {fname} | Args: {args}")

        result = {}
        try:
            if fname in available_tools:
                func = available_tools[fname]
                
                # --- LOGIC QUAN TRỌNG: FIX LỖI REPEATED COMPOSITE ---
                # Chuyển đổi dữ liệu từ Protobuf sang Python Native Types trước khi gọi hàm
                call_args = {"token": user_token}
                for key, value in args.items():
                    if key == "recurrence":
                        # Convert MapComposite -> Dict
                        rec_dict = dict(value)
                        
                        # QUAN TRỌNG NHẤT: Ép kiểu daysOfWeek từ RepeatedComposite -> List
                        if "daysOfWeek" in rec_dict:
                            rec_dict["daysOfWeek"] = list(rec_dict["daysOfWeek"])
                            
                        call_args[key] = rec_dict
                        
                    elif key in ["participant_ids", "device_ids"]:
                        # Convert RepeatedComposite -> List Int
                        call_args[key] = [int(x) for x in value]
                        
                    elif key in ["room_id", "meeting_id", "capacity", "duration", "interval"]:
                        call_args[key] = int(value)
                        
                    else:
                        call_args[key] = value
                
                result = func(**call_args)
            else:
                result = {"error": f"Tool {fname} không tồn tại."}
        except Exception as e:
            result = {"error": str(e)}

        print(f"✅ [API Result] {result}")

        response = chat.send_message(
            Content(parts=[Part(function_response=FunctionResponse(name=fname, response={"result": result}))])
        )
        turn += 1

    return "Tôi đang gặp khó khăn trong việc xử lý yêu cầu này. Vui lòng thử lại cụ thể hơn."