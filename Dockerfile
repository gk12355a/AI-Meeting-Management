# Sử dụng Python 3.11 slim để đảm bảo nhẹ và tương thích tốt với ChromaDB
FROM python:3.11-slim

# Thiết lập thư mục làm việc
WORKDIR /app

# Cài đặt các gói hệ thống cần thiết (build-essential cho gcc, curl để test)
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt trước để tận dụng Docker cache
COPY requirements.txt .

# Cài đặt các thư viện Python
# --no-cache-dir giúp giảm dung lượng image
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ mã nguồn vào image
COPY . .

# Tạo thư mục cho ChromaDB và cấp quyền (tránh lỗi permission)
RUN mkdir -p /app/chroma_db && chmod 777 /app/chroma_db

# Expose cổng 8000 (cổng FastAPI chạy)
EXPOSE 8000

# Lệnh khởi chạy ứng dụng
# Sử dụng host 0.0.0.0 để container có thể nhận request từ bên ngoài
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]