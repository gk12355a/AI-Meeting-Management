#!/bin/bash

# 1. Nhận các tham số từ Jenkins
# Thứ tự: $1=TênService, $2=VersionTag, $3=MôiTrường, $4=ThưMụcYAML
SERVICE_NAME=$1
VERSION=$2
ENV_NAME=$3
YAML_DIR=$4

# 2. Cấu hình Docker Hub User
DOCKER_USER="gk123a"

# 3. Tạo chuỗi Image Tag mới
NEW_TAG="${VERSION}-${ENV_NAME}"
NEW_FULL_IMAGE="${DOCKER_USER}/${SERVICE_NAME}:${NEW_TAG}"

echo "-------------------------------------------------"
echo "Script: Update Image in Kubernetes Manifest (Linux)"
echo "Service Name    : $SERVICE_NAME"
echo "New Image       : $NEW_FULL_IMAGE"
echo "Target Dir      : $YAML_DIR"
echo "-------------------------------------------------"

# [DEBUG] In ra dòng image hiện tại để kiểm tra xem script có tìm thấy file không
echo "--- Current Image in YAML ---"
grep "image:" ${YAML_DIR}/*.yaml

# 4. Thực hiện thay thế bằng lệnh sed (Cú pháp chuẩn Linux)
sed -i "s|image: .*/${SERVICE_NAME}:.*|image: ${NEW_FULL_IMAGE}|g" ${YAML_DIR}/*.yaml

# [DEBUG] In ra kết quả sau khi sed để xác nhận đã thay đổi
echo "--- Updated Image in YAML ---"
grep "image:" ${YAML_DIR}/*.yaml

# 5. Kiểm tra mã lỗi
if [ $? -eq 0 ]; then
  echo "✅ Success: Command executed."
else
  echo "❌ Error: Failed to update image tag."
  exit 1
fi
