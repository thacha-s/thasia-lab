import os
from flask import Flask, render_template, request, abort
from azure.iot.hub import IoTHubRegistryManager
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, ReplyMessageRequest, 
    PushMessageRequest, TextMessage, ImageMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

app = Flask(__name__)

# --- Configurations ---
configuration = Configuration(access_token=os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))

# --- IoT Hub Connection ---
IOT_SERVICE_CONNECTION = os.getenv('AZURE_IOT_SERVICE_CONNECTION')
DEVICE_ID = "KasetID"
registry_manager = None

if IOT_SERVICE_CONNECTION:
    try:
        registry_manager = IoTHubRegistryManager(IOT_SERVICE_CONNECTION)
    except Exception as e:
        print(f"IoT Hub Initialization Error: {e}")

authorized_users = {}
user_state = {}
PRODUCT_ID = "THASIA-KV-001"

def send_drone_command(command_text):
    if registry_manager is None:
        return False
    try:
        registry_manager.send_c2d_message(DEVICE_ID, command_text)
        return True
    except Exception as e:
        print(f"Send Error: {e}")
        return False

@app.route("/")
def home():
    return "Kaset Vision Server is Online!"

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    user_text = event.message.text.strip()
    reply = ""

    if user_text == PRODUCT_ID:
        authorized_users[user_id] = {'authorized': True}
        reply = "ยืนยันรหัสผลิตภัณฑ์เรียบร้อยค่ะ ยินดีต้อนรับสู่ระบบ Kaset Vision ค่ะ"
    
    elif user_id not in authorized_users or not authorized_users[user_id]['authorized']:
        reply = "กรุณาใส่รหัส PRODUCT ID เพื่อเริ่มต้นใช้งานระบบควบคุมโดรน"

    else:
        if user_text == "สั่งบิน":
            reply = "กรุณาระบุพื้นที่ (ไร่) และความสูง (เมตร) เช่น '1 ไร่ 5 เมตร'"
        
        elif user_text == "ตรวจสอบสถานะโดรน":
            send_drone_command("GET_STATUS")
            reply = "กำลังดึงข้อมูลจากโดรน..."

        elif user_text == "จัดการระบบประมวลผล":
            reply = "ต้องการให้ Raspberry Pi 'ปิดระบบ' หรือ 'เริ่มระบบใหม่' คะ"
        
        elif "ปิดระบบ" in user_text or "เริ่มระบบใหม่" in user_text:
            action = "SHUTDOWN" if "ปิดระบบ" in user_text else "REBOOT"
            success = send_drone_command(action)
            if success:
                reply = f"รับทราบค่ะ กำลังดำเนินรายการ {action} ใน 5 วินาที..."
            else:
                reply = "เกิดข้อผิดพลาดในการส่งคำสั่งไปยังโดรน โปรดตรวจสอบการเชื่อมต่อ"

        else:
            reply = "ขออภัยค่ะ ฉันไม่เข้าใจคำสั่งนี้ ลองเลือกจากเมนูดูนะคะ"
    
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)]
            )
        )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)
