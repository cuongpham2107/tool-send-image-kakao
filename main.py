import os
import io
import time
import struct
import shutil
import tempfile
import win32gui
import win32con
import win32clipboard
import pyautogui
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
import uvicorn

app = FastAPI(title="KakaoTalk Windows Batch Sender")

# ==================== 1. XỬ LÝ CLIPBOARD WINDOWS ====================

def copy_files_to_clipboard(file_paths: list[str]):
    """
    Nạp danh sách nhiều file vào Windows Clipboard định dạng CF_HDROP.
    (Giống hệt hành động chọn nhiều file trong File Explorer rồi bấm Ctrl + C)
    """
    # Cấu trúc DROPFILES chuẩn trong Win32:
    # Offset bắt đầu danh sách file là 20 bytes, fWide = 1 (Unicode UTF-16LE)
    dropfiles = struct.pack("IIIIi", 20, 0, 0, 0, 1)
    
    # Mã hóa danh sách đường dẫn tuyệt đối dạng UTF-16LE, kết thúc bằng 2 ký tự NULL
    files_bytes = b"".join([
        os.path.abspath(p).encode("utf-16le") + b"\x00\x00" 
        for p in file_paths
    ]) + b"\x00\x00"

    data = dropfiles + files_bytes

    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardData(win32con.CF_HDROP, data)
    win32clipboard.CloseClipboard()

def copy_text_to_clipboard(text: str):
    """Nạp văn bản tiếng Việt / Unicode vào Clipboard Windows"""
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardText(text, win32con.CF_UNICODETEXT)
    win32clipboard.CloseClipboard()


# ==================== 2. TÌM VÀ FOCUS CỬA SỔ KAKAOTALK ====================

def focus_chat_window(room_name: str) -> bool:
    """Tìm đúng cửa sổ chat và đưa ra trước màn hình"""
    target_hwnd = None

    def enum_cb(hwnd, _):
        nonlocal target_hwnd
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if room_name.lower() in title.lower():
                target_hwnd = hwnd
        return True

    win32gui.EnumWindows(enum_cb, None)
    if not target_hwnd:
        return False

    # Giả lập phím Alt để Windows cho phép cướp quyền Foreground
    pyautogui.press('alt')
    win32gui.ShowWindow(target_hwnd, win32con.SW_RESTORE)
    win32gui.SetForegroundWindow(target_hwnd)
    time.sleep(0.3)
    return True


# ==================== 3. LUỒNG THỰC THI (CTRL+V -> TAB -> ENTER) ====================

def execute_send_flow(room_name: str, file_paths: list[str], message: str = None):
    # 1. Kích hoạt cửa sổ phòng chat KakaoTalk
    if not focus_chat_window(room_name):
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy cửa sổ phòng chat '{room_name}'. Hãy chắc chắn bạn đã click đúp mở phòng chat này ra cửa sổ riêng!"
        )

    # 2. Đưa toàn bộ danh sách file ảnh vào Clipboard
    copy_files_to_clipboard(file_paths)
    time.sleep(0.3)

    # 3. Dán vào ô chat
    pyautogui.hotkey('ctrl', 'v')

    # 4. Chờ popup 'Send file' hiện lên và nạp đủ ảnh
    time.sleep(1.2)

    # 5. Bấm TAB để chuyển focus sang nút Send màu vàng, rồi bấm ENTER để gửi
    pyautogui.press('tab')
    time.sleep(0.3)
    pyautogui.press('enter')

    # 6. Chờ KakaoTalk tải ảnh xong
    time.sleep(1.0)

    # 7. Gửi tin nhắn văn bản kèm theo (nếu có)
    if message:
        copy_text_to_clipboard(message)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.3)
        pyautogui.press('enter')


# ==================== 4. ENDPOINT WEBHOOK ====================

@app.post("/send-images")
async def send_images_api(
    room_name: str = Form(..., description="Tên phòng chat KakaoTalk"),
    message: str = Form(None, description="Tin nhắn văn bản đi kèm (tùy chọn)"),
    files: list[UploadFile] = File(..., description="Danh sách các file ảnh gửi lên")
):
    if not files:
        raise HTTPException(status_code=400, detail="Vui lòng đính kèm ít nhất một file ảnh!")

    # Tạo thư mục tạm thời trên Windows để lưu các file upload
    temp_dir = tempfile.mkdtemp(prefix="kakao_win_")
    saved_paths = []

    try:
        # Ghi các file upload ra đĩa tạm
        for f in files:
            file_path = os.path.join(temp_dir, f.filename)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(f.file, buffer)
            saved_paths.append(file_path)

        # Thực thi quy trình gửi
        execute_send_flow(room_name, saved_paths, message)

        return {
            "status": "success",
            "detail": f"Đã gửi thành công {len(saved_paths)} ảnh tới '{room_name}'!"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # Dọn dẹp các file ảnh tạm sau khi gửi xong
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    # Chạy Webhook Server trên cổng 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)