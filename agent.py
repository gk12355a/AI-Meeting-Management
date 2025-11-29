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
    raise ValueError("Missing GEMINI_API_KEY")

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

# 3. Tool Definitions (GIỮ NGUYÊN CẤU TRÚC PROTOBUF CHUẨN)
# (Để tiết kiệm dòng, tôi gộp phần định nghĩa schema đã đúng ở phiên bản trước)
# ... Bạn giữ nguyên phần định nghĩa FunctionDeclaration từ code trước ...
# ... Nếu lỡ xóa, hãy bảo tôi gửi lại đoạn Schema này ...

# --- Tái sử dụng Schema từ phiên bản trước (Đảm bảo bạn copy đủ list tools_list) ---
search_users_func = FunctionDeclaration(
    name="search_users", description="Tìm ID người dùng theo tên/email.",
    parameters=Schema(type=Type.OBJECT, properties={"query": Schema(type=Type.STRING)}, required=["query"])
)
get_rooms_func = FunctionDeclaration(
    name="get_rooms", description="Lấy danh sách tất cả phòng họp và ID.",
    parameters=Schema(type=Type.OBJECT, properties={})
)
find_avail_func = FunctionDeclaration(
    name="find_available_rooms", description="Tìm phòng trống.",
    parameters=Schema(type=Type.OBJECT, properties={"start_time": Schema(type=Type.STRING), "end_time": Schema(type=Type.STRING), "capacity": Schema(type=Type.INTEGER)}, required=["start_time", "end_time"])
)
get_meetings_func = FunctionDeclaration(
    name="get_my_meetings", description="Xem lịch họp. Dùng date_filter nếu cần lọc ngày.",
    parameters=Schema(type=Type.OBJECT, properties={"date_filter": Schema(type=Type.STRING)})
)
get_details_func = FunctionDeclaration(
    name="get_meeting_details", description="Xem chi tiết 1 cuộc họp.",
    parameters=Schema(type=Type.OBJECT, properties={"meeting_id": Schema(type=Type.INTEGER)}, required=["meeting_id"])
)
create_meeting_func = FunctionDeclaration(
    name="create_meeting", description="Tạo cuộc họp.",
    parameters=Schema(type=Type.OBJECT, properties={
        "title": Schema(type=Type.STRING), "start_time": Schema(type=Type.STRING), "end_time": Schema(type=Type.STRING),
        "room_id": Schema(type=Type.INTEGER), "participant_ids": Schema(type=Type.ARRAY, items=Schema(type=Type.INTEGER)),
        "device_ids": Schema(type=Type.ARRAY, items=Schema(type=Type.INTEGER)), "description": Schema(type=Type.STRING),
        "recurrence": Schema(type=Type.OBJECT, properties={"frequency": Schema(type=Type.STRING), "interval": Schema(type=Type.INTEGER), "repeatUntil": Schema(type=Type.STRING), "daysOfWeek": Schema(type=Type.ARRAY, items=Schema(type=Type.STRING))}, required=["frequency", "interval", "repeatUntil"])
    }, required=["title", "start_time", "end_time", "room_id"])
)
cancel_meeting_func = FunctionDeclaration(
    name="cancel_meeting", description="Hủy cuộc họp.",
    parameters=Schema(type=Type.OBJECT, properties={"meeting_id": Schema(type=Type.INTEGER), "reason": Schema(type=Type.STRING)}, required=["meeting_id", "reason"])
)
get_devices_func = FunctionDeclaration(
    name="get_devices", description="Lấy danh sách thiết bị.",
    parameters=Schema(type=Type.OBJECT, properties={})
)
update_meeting_func = FunctionDeclaration(
    name="update_meeting", description="Sửa cuộc họp.",
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
    name="check_in_meeting", description="Check-in.",
    parameters=Schema(type=Type.OBJECT, properties={"room_id": Schema(type=Type.INTEGER)}, required=["room_id"])
)
suggest_time_func = FunctionDeclaration(
    name="suggest_meeting_time", description="Gợi ý giờ họp.",
    parameters=Schema(type=Type.OBJECT, properties={"participant_ids": Schema(type=Type.ARRAY, items=Schema(type=Type.INTEGER)), "start_date": Schema(type=Type.STRING), "end_date": Schema(type=Type.STRING), "duration": Schema(type=Type.INTEGER)}, required=["participant_ids", "start_date", "end_date"])
)
get_groups_func = FunctionDeclaration(
    name="get_contact_groups", description="Lấy nhóm liên hệ.",
    parameters=Schema(type=Type.OBJECT, properties={})
)
search_policy_func = FunctionDeclaration(
    name="search_policy", description="Tra cứu quy định.",
    parameters=Schema(type=Type.OBJECT, properties={"query": Schema(type=Type.STRING)}, required=["query"])
)
find_avail_devices_func = FunctionDeclaration(
    name="find_available_devices", description="Tìm thiết bị trống.",
    parameters=Schema(type=Type.OBJECT, properties={"start_time": Schema(type=Type.STRING), "end_time": Schema(type=Type.STRING)}, required=["start_time", "end_time"])
)
checkin_qr_func = FunctionDeclaration(
    name="check_in_by_qr", description="Check-in bằng mã QR.",
    parameters=Schema(type=Type.OBJECT, properties={"qr_code": Schema(type=Type.STRING)}, required=["qr_code"])
)
cancel_series_func = FunctionDeclaration(
    name="cancel_meeting_series", description="Hủy chuỗi lịch.",
    parameters=Schema(type=Type.OBJECT, properties={"series_id": Schema(type=Type.STRING), "reason": Schema(type=Type.STRING)}, required=["series_id", "reason"])
)
update_series_func = FunctionDeclaration(
    name="update_meeting_series", description="Sửa chuỗi lịch.",
    parameters=Schema(type=Type.OBJECT, properties={
        "series_id": Schema(type=Type.STRING), "title": Schema(type=Type.STRING), "start_time": Schema(type=Type.STRING),
        "end_time": Schema(type=Type.STRING), "room_id": Schema(type=Type.INTEGER), "participant_ids": Schema(type=Type.ARRAY, items=Schema(type=Type.INTEGER)),
        "description": Schema(type=Type.STRING),
        "recurrence": Schema(type=Type.OBJECT, properties={"frequency": Schema(type=Type.STRING), "interval": Schema(type=Type.INTEGER), "repeatUntil": Schema(type=Type.STRING), "daysOfWeek": Schema(type=Type.ARRAY, items=Schema(type=Type.STRING))}, required=["frequency", "interval", "repeatUntil"])
    }, required=["series_id", "title", "start_time", "end_time", "room_id", "recurrence"])
)

tools_list = [
    search_users_func, get_rooms_func, find_avail_func, get_meetings_func,
    get_details_func, create_meeting_func, cancel_meeting_func, update_meeting_func,
    get_devices_func, respond_func, notif_func, checkin_func,
    suggest_time_func, get_groups_func, search_policy_func,
    find_avail_devices_func, checkin_qr_func, cancel_series_func, update_series_func
]

meeting_tools = Tool(function_declarations=tools_list)
model = genai.GenerativeModel(model_name='models/gemini-2.0-flash', tools=[meeting_tools])

# 4. Redis Logic (GIỮ NGUYÊN)
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
        if len(hist) > 10: hist = hist[-10:] # Giữ ít thôi cho đỡ loạn context
        redis_client.set(key, json.dumps(hist))
        redis_client.expire(key, 1800) # 30 phút timeout
    except: pass

# 5. MAIN LOGIC - PHẦN QUAN TRỌNG NHẤT
async def simple_chat(user_message: str, user_token: str):
    history = get_chat_history(user_token)
    chat = model.start_chat(history=history, enable_automatic_function_calling=False)
    
    now = datetime.now()
    current_time_str = now.strftime('%Y-%m-%d %H:%M:%S')
    today_date = now.strftime('%Y-%m-%d')
    
    # --- SYSTEM PROMPT TỐI ƯU HÓA "ĐÚNG TRỌNG TÂM" ---
    system_instruction = f"""
    [VAI TRÒ] Bạn là Trợ lý Ảo chuyên nghiệp của CMC Meeting. Bạn KHÔNG phải là chatbot giao tiếp xã giao. Hãy trả lời ngắn gọn, đi thẳng vào vấn đề.
    
    [THÔNG TIN HIỆN TẠI]
    - Thời gian thực: {current_time_str} (Thứ {now.weekday() + 2}).
    - Hôm nay là: {today_date}.
    
    [NGUYÊN TẮC XỬ LÝ - TUÂN THỦ TUYỆT ĐỐI]
    1. **KHÔNG BAO GIỜ BỊA ĐẶT ID:** Nếu user nói tên phòng ("Sao Hỏa") hoặc tên người ("Tuấn"), bạn BẮT BUỘC phải gọi tool `get_rooms` hoặc `search_users` để lấy ID. Nếu không tìm thấy, hãy báo lỗi, không được tự đoán ID.
    2. **XỬ LÝ THỜI GIAN:** - "Chiều nay" = Từ 13:00 đến 17:00 ngày {today_date}.
       - "Sáng mai" = Từ 08:00 đến 11:00 ngày mai.
       - Luôn convert sang ISO 8601: YYYY-MM-DDTHH:mm:ss.
    3. **QUY TRÌNH ĐẶT LỊCH (BẮT BUỘC):**
       - B1: Nếu thiếu thông tin (Giờ/Phòng/Người) -> Hỏi ngay, không đoán.
       - B2: Có đủ thông tin -> Gọi tool tra cứu ID (get_rooms, search_users).
       - B3: **XÁC NHẬN:** Tóm tắt lại "Bạn muốn đặt phòng [Tên] (ID [Số]) lúc [Giờ] với [Người] phải không?".
       - B4: User đồng ý -> Gọi `create_meeting`.
    4. **TRẢ LỜI:**
       - Ngắn gọn. Ví dụ: "Đã tìm thấy phòng A, B.", "Đã đặt thành công."
       - Nếu gặp lỗi từ hệ thống, hãy báo nguyên văn lỗi đó.
    5. **TRA CỨU:**
       - Nếu hỏi "hôm nay có lịch không", gọi `get_my_meetings(date_filter='{today_date}')`.
       - Nếu hỏi quy định, gọi `search_policy`.
    """

    try:
        # Gửi prompt kèm tin nhắn để đảm bảo bot luôn nhớ nhiệm vụ
        response = chat.send_message(f"{system_instruction}\nUser: {user_message}")
    except Exception as e:
        return "Hệ thống AI đang bận. Vui lòng thử lại sau."

    turn = 0
    max_turns = 8 # Giới hạn số bước để tránh lặp vô tận
    
    while turn < max_turns:
        part = response.parts[0]
        
        # Nếu AI trả lời Text -> Trả về luôn
        if not part.function_call:
            bot_reply = response.text
            save_chat_turn(user_token, user_message, bot_reply)
            return bot_reply

        # Nếu AI gọi Hàm
        fc = part.function_call
        fname = fc.name
        args = fc.args
        print(f"🤖 [AI Action] {fname} | Args: {args}")

        result = {}
        try:
            if fname in available_tools:
                func = available_tools[fname]
                
                call_args = {"token": user_token}
                for key, value in args.items():
                    # Ép kiểu dữ liệu để tránh lỗi API Java
                    if key in ["room_id", "meeting_id", "capacity", "duration", "interval"]:
                        call_args[key] = int(value)
                    elif key in ["participant_ids", "device_ids"]:
                        call_args[key] = [int(x) for x in value]
                    elif key == "recurrence":
                        call_args[key] = dict(value)
                    else:
                        call_args[key] = value
                
                result = func(**call_args)
            else:
                result = {"error": f"Tool {fname} không tồn tại."}
        except Exception as e:
            result = {"error": str(e)}

        print(f"✅ [API Result] {result}")

        # Gửi kết quả lại cho AI
        response = chat.send_message(
            Content(parts=[Part(function_response=FunctionResponse(name=fname, response={"result": result}))])
        )
        turn += 1

    return "Tôi đang gặp khó khăn trong việc xử lý yêu cầu này. Vui lòng thử lại cụ thể hơn."