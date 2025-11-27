"""
Utility script: Liệt kê tất cả các mô hình Gemini hiện có sẵn trên tài khoản của bạn
Hữu ích để kiểm tra:
- Quyền truy cập (API key có hoạt động không?)
- Model nào đang available (gemini-1.5-flash, gemini-1.5-pro, gemini-2.0-flash-exp, v.v.)
- Model nào hỗ trợ generateContent (dùng cho chat/function calling)

Chạy: python list_models.py
"""

import os
import google.generativeai as genai
from dotenv import load_dotenv



# 1. CẤU HÌNH API KEY

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise EnvironmentError(
        "GEMINI_API_KEY không được tìm thấy!\n"
        "Vui lòng tạo file .env trong thư mục gốc và thêm dòng:\n"
        "GEMINI_API_KEY=your_actual_api_key_here"
    )

# Cấu hình ngay khi có key
genai.configure(api_key=GEMINI_API_KEY)



# 2. LIỆT KÊ CÁC MODEL HỖ TRỢ GENERATE CONTENT

def list_available_models() -> None:
    """In ra danh sách các model Gemini có thể dùng cho chat / generateContent."""
    print("ĐANG LẤY DANH SÁCH MODEL TỪ GOOGLE AI STUDIO...\n")
    print("=" * 60)
    print("CÁC MODEL KHẢ DỤNG (hỗ trợ generateContent)")
    print("=" * 60)

    try:
        # Lấy toàn bộ danh sách model mà tài khoản hiện tại có quyền truy cập
        models = genai.list_models()

        # Lọc chỉ những model hỗ trợ phương thức generateContent (tức là dùng được cho chat)
        chat_models = [
            m for m in models
            if "generateContent" in m.supported_generation_methods
        ]

        if not chat_models:
            print("Không tìm thấy model nào hỗ trợ generateContent.")
            print("Có thể API key chưa được kích hoạt hoặc bị giới hạn quyền.")
            return

        # In danh sách theo thứ tự tên (để dễ đọc)
        for model in sorted(chat_models, key=lambda x: x.name):
            display_name = model.display_name or "Unknown"
            print(f"{model.name.ljust(40)} | {display_name}")

        print("=" * 60)
        print(f"Tổng cộng: {len(chat_models)} model khả dụng")
        print("\nGợi ý thường dùng:")
        print("   • models/gemini-1.5-flash      → Nhanh, rẻ, phù hợp chatbot")
        print("   • models/gemini-1.5-pro       → Mạnh hơn, context dài")
        print("   • models/gemini-2.0-flash-exp → Experimental, hiệu năng cao (nếu có)")

    except Exception as exc:
        print(f"Lỗi khi lấy danh sách model: {exc}")
        print("\nMột số nguyên nhân thường gặp:")
        print("   • API key sai hoặc chưa được bật billing")
        print("   • Chưa enable Generative Language API trong Google Cloud Console")
        print("   • Vùng (region) không hỗ trợ (thử dùng VPN nếu cần)")



# 3. ENTRY POINT

if __name__ == "__main__":
    list_available_models()