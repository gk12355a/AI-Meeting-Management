from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from agent import simple_chat
import uvicorn

app = FastAPI()

# Model dữ liệu nhận từ Frontend
class ChatPayload(BaseModel):
    message: str

@app.get("/")
def health_check():
    return {"status": "AI Service is running"}

@app.post("/api/chat")
async def chat(payload: ChatPayload, authorization: str = Header(None)):
    """
    API Chatbot:
    - Nhận tin nhắn từ user.
    - Nhận JWT Token từ Header.
    - Gọi Agent xử lý.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Token is missing")
    
    # Lấy token (bỏ chữ Bearer nếu có, nhưng ở đây ta truyền nguyên chuỗi cũng được vì tools.py đã xử lý)
    user_token = authorization.replace("Bearer ", "")
    
    try:
        reply = await simple_chat(payload.message, user_token)
        return {"reply": reply}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)