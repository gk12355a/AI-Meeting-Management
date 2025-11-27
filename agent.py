import google.generativeai as genai
import os
import json
import redis
from dotenv import load_dotenv
from tools import available_tools
from datetime import datetime

# Google Generative AI Low-level imports for Schema definitions
from google.ai.generativelanguage import FunctionDeclaration, Tool, Schema, Type
from google.ai.generativelanguage import Content, Part, FunctionResponse

# 1. Configuration
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("Missing GEMINI_API_KEY in environment variables.")

genai.configure(api_key=api_key)

# 2. Redis Connection
redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = int(os.getenv("REDIS_PORT", 6379))
redis_password = os.getenv("REDIS_PASSWORD")
redis_db = int(os.getenv("REDIS_DB", 0))

if redis_password == "":
    redis_password = None

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

# 3. Tool Definitions (Protobuf Schema)

search_users_func = FunctionDeclaration(
    name="search_users",
    description="Find user ID by name or email.",
    parameters=Schema(
        type=Type.OBJECT,
        properties={"query": Schema(type=Type.STRING, description="Name or email to search")},
        required=["query"]
    )
)

get_rooms_func = FunctionDeclaration(
    name="get_rooms",
    description="Retrieve list of all meeting rooms and their IDs.",
    parameters=Schema(type=Type.OBJECT, properties={})
)

find_avail_func = FunctionDeclaration(
    name="find_available_rooms",
    description="Find available rooms based on time range.",
    parameters=Schema(
        type=Type.OBJECT,
        properties={
            "start_time": Schema(type=Type.STRING, description="ISO 8601: YYYY-MM-DDTHH:mm:ss"),
            "end_time": Schema(type=Type.STRING, description="ISO 8601: YYYY-MM-DDTHH:mm:ss"),
            "capacity": Schema(type=Type.INTEGER, description="Default: 5")
        },
        required=["start_time", "end_time"]
    )
)

get_meetings_func = FunctionDeclaration(
    name="get_my_meetings",
    description="Retrieve my upcoming meetings.",
    parameters=Schema(type=Type.OBJECT, properties={})
)

get_details_func = FunctionDeclaration(
    name="get_meeting_details",
    description="Get details of a specific meeting.",
    parameters=Schema(
        type=Type.OBJECT,
        properties={"meeting_id": Schema(type=Type.INTEGER)},
        required=["meeting_id"]
    )
)

create_meeting_func = FunctionDeclaration(
    name="create_meeting",
    description="Create a new meeting. REQUIRES USER CONFIRMATION.",
    parameters=Schema(
        type=Type.OBJECT,
        properties={
            "title": Schema(type=Type.STRING),
            "start_time": Schema(type=Type.STRING),
            "end_time": Schema(type=Type.STRING),
            "room_id": Schema(type=Type.INTEGER),
            "participant_ids": Schema(type=Type.ARRAY, items=Schema(type=Type.INTEGER)),
            "device_ids": Schema(type=Type.ARRAY, items=Schema(type=Type.INTEGER)),
            "description": Schema(type=Type.STRING),
            "recurrence": Schema(
                type=Type.OBJECT,
                properties={
                    "frequency": Schema(type=Type.STRING, enum=["DAILY", "WEEKLY", "MONTHLY"]),
                    "interval": Schema(type=Type.INTEGER),
                    "repeatUntil": Schema(type=Type.STRING),
                    "daysOfWeek": Schema(type=Type.ARRAY, items=Schema(type=Type.STRING))
                },
                required=["frequency", "interval", "repeatUntil"]
            )
        },
        required=["title", "start_time", "end_time", "room_id"]
    )
)

cancel_meeting_func = FunctionDeclaration(
    name="cancel_meeting",
    description="Cancel a meeting. REQUIRES USER CONFIRMATION.",
    parameters=Schema(
        type=Type.OBJECT,
        properties={
            "meeting_id": Schema(type=Type.INTEGER),
            "reason": Schema(type=Type.STRING)
        },
        required=["meeting_id", "reason"]
    )
)

get_devices_func = FunctionDeclaration(
    name="get_devices",
    description="List available devices.",
    parameters=Schema(type=Type.OBJECT, properties={})
)

update_meeting_func = FunctionDeclaration(
    name="update_meeting",
    description="Update a meeting. REQUIRES USER CONFIRMATION.",
    parameters=Schema(
        type=Type.OBJECT,
        properties={
            "meeting_id": Schema(type=Type.INTEGER),
            "title": Schema(type=Type.STRING),
            "start_time": Schema(type=Type.STRING),
            "end_time": Schema(type=Type.STRING),
            "room_id": Schema(type=Type.INTEGER),
            "participant_ids": Schema(type=Type.ARRAY, items=Schema(type=Type.INTEGER)),
            "description": Schema(type=Type.STRING)
        },
        required=["meeting_id", "title", "start_time", "end_time", "room_id"]
    )
)

respond_func = FunctionDeclaration(
    name="respond_invitation",
    description="Accept or Decline a meeting invitation.",
    parameters=Schema(
        type=Type.OBJECT,
        properties={
            "meeting_id": Schema(type=Type.INTEGER),
            "status": Schema(type=Type.STRING, enum=["ACCEPTED", "DECLINED"])
        },
        required=["meeting_id", "status"]
    )
)

notif_func = FunctionDeclaration(
    name="get_notifications",
    description="Get latest notifications.",
    parameters=Schema(type=Type.OBJECT, properties={})
)

checkin_func = FunctionDeclaration(
    name="check_in_meeting",
    description="Check-in to a meeting.",
    parameters=Schema(
        type=Type.OBJECT,
        properties={"room_id": Schema(type=Type.INTEGER)},
        required=["room_id"]
    )
)

suggest_time_func = FunctionDeclaration(
    name="suggest_meeting_time",
    description="Find common free slots for participants.",
    parameters=Schema(
        type=Type.OBJECT,
        properties={
            "participant_ids": Schema(type=Type.ARRAY, items=Schema(type=Type.INTEGER)),
            "start_date": Schema(type=Type.STRING, description="ISO format"),
            "end_date": Schema(type=Type.STRING, description="ISO format"),
            "duration": Schema(type=Type.INTEGER)
        },
        required=["participant_ids", "start_date", "end_date"]
    )
)

get_groups_func = FunctionDeclaration(
    name="get_contact_groups",
    description="Get contact groups (to resolve member IDs).",
    parameters=Schema(type=Type.OBJECT, properties={})
)

search_policy_func = FunctionDeclaration(
    name="search_policy",
    description="Retrieve system policies and regulations.",
    parameters=Schema(
        type=Type.OBJECT,
        properties={"query": Schema(type=Type.STRING)},
        required=["query"]
    )
)

# Tool aggregation
tools_list = [
    search_users_func, get_rooms_func, find_avail_func, get_meetings_func,
    get_details_func, create_meeting_func, cancel_meeting_func, update_meeting_func,
    get_devices_func, respond_func, notif_func, checkin_func,
    suggest_time_func, get_groups_func, search_policy_func
]

meeting_tools = Tool(function_declarations=tools_list)
model = genai.GenerativeModel(model_name='models/gemini-2.0-flash', tools=[meeting_tools])

# 4. Redis Helper Functions

def get_chat_history(user_token: str):
    """Retrieve chat history from Redis."""
    if not redis_client: return []
    key = f"chat_history:{user_token}"
    try:
        data = redis_client.get(key)
        if data:
            items = json.loads(data)
            # Reconstruct textual history only to maintain context safely
            return [Content(role=i["role"], parts=[Part(text=i["text"])]) for i in items if i.get("text")]
    except Exception as e:
        print(f"[ERROR] Redis read error: {e}")
    return []

def save_chat_turn(user_token: str, user_msg: str, bot_msg: str):
    """Save chat turn to Redis."""
    if not redis_client: return
    key = f"chat_history:{user_token}"
    try:
        data = redis_client.get(key)
        hist = json.loads(data) if data else []
        hist.append({"role": "user", "text": user_msg})
        hist.append({"role": "model", "text": bot_msg})
        # Keep last 20 interactions
        if len(hist) > 20: hist = hist[-20:]
        redis_client.set(key, json.dumps(hist))
        redis_client.expire(key, 3600)
    except Exception as e:
        print(f"[ERROR] Redis save error: {e}")

# 5. Main Logic

async def simple_chat(user_message: str, user_token: str):
    history = get_chat_history(user_token)
    chat = model.start_chat(history=history, enable_automatic_function_calling=False)
    
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    system_instruction = f"""
    [SYSTEM] You are the AI Assistant for CMC Meeting System. Current time: {current_time}.
    
    INSTRUCTIONS:
    1. **Policy**: Use `search_policy` for questions about rules/regulations.
    2. **Scheduling**: Use `search_users` -> `suggest_meeting_time` to find slots.
    3. **Groups**: Use `get_contact_groups` -> `create_meeting` for group bookings.
    4. **Confirmation**: ALWAYS ask "Are you sure...?" with summary before Create/Update/Cancel actions.
    5. **Time**: Use ISO 8601 format (YYYY-MM-DDTHH:mm:ss).
    """

    try:
        response = chat.send_message(f"{system_instruction}\nUser: {user_message}")
    except Exception as e:
        return f"AI Connection Error: {str(e)}"

    turn = 0
    max_turns = 10
    
    while turn < max_turns:
        part = response.parts[0]
        
        # Text response (Question or Final Answer)
        if not part.function_call:
            bot_reply = response.text
            save_chat_turn(user_token, user_message, bot_reply)
            return bot_reply

        # Function Call
        fc = part.function_call
        fname = fc.name
        args = fc.args
        print(f"[AGENT] Invoking: {fname} | Args: {args}")

        result = {}
        try:
            if fname in available_tools:
                func = available_tools[fname]
                
                # Argument mapping
                call_args = {"token": user_token}
                for key, value in args.items():
                    if key in ["room_id", "meeting_id", "capacity", "duration"]:
                        call_args[key] = int(value)
                    elif key in ["participant_ids", "device_ids"]:
                        call_args[key] = [int(x) for x in value]
                    elif key == "recurrence":
                        call_args[key] = dict(value)
                    else:
                        call_args[key] = value
                
                result = func(**call_args)
            else:
                result = {"error": f"Tool {fname} not implemented."}
        except Exception as e:
            result = {"error": str(e)}

        print(f"[AGENT] Result: {result}")

        # Send result back to Model
        response = chat.send_message(
            Content(parts=[Part(function_response=FunctionResponse(name=fname, response={"result": result}))])
        )
        turn += 1

    return "Process terminated: Too many execution steps."