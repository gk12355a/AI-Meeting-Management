import os
from dotenv import load_dotenv # Import thêm
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agent import simple_chat
import uvicorn

# 1. Load biến môi trường
load_dotenv()
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173") # Giá trị mặc định nếu quên config

app = FastAPI()

# 2. Cấu hình CORS Dynamic
origins = [
    FRONTEND_URL,           # Lấy từ .env
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatPayload(BaseModel):
    message: str

@app.get("/")
def health_check():
    return {"status": "AI Service is running"}

@app.post("/api/chat")
async def chat(payload: ChatPayload, authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Token is missing")
    
    # Lấy token (bỏ chữ Bearer nếu có)
    user_token = authorization.replace("Bearer ", "")
    
    try:
        reply = await simple_chat(payload.message, user_token)
        return {"reply": reply}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)