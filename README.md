pip install -r requirements.txt


curl -X POST http://<IP_MAY_WIN>:8000/send-images \
  -F "room_name=Anh Tùng" \
  -F "message=Báo cáo ảnh hôm nay" \
  -F "files=@anh1.png" \
  -F "files=@anh2.png" \
  -F "files=@anh3.png"