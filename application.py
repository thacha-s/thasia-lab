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

# --- Safe IoT Hub Initialization ---
IOT_SERVICE_CONNECTION = os.getenv('AZURE_IOT_SERVICE_CONNECTION')
DEVICE_ID = "KasetID"
registry_manager = None

if IOT_SERVICE_CONNECTION:
    try:
        # Prevent crash if connection string is malformed
        registry_manager = IoTHubRegistryManager(IOT_SERVICE_CONNECTION)
        print("IoT Hub Registry Manager initialized successfully.")
    except Exception as e:
        print(f"Error initializing IoT Hub: {e}")
else:
    print("WARNING: AZURE_IOT_SERVICE_CONNECTION is not set in Environment Variables.")

authorized_users = {}
user_state = {}
PRODUCT_ID = "THASIA-KV-001"

def send_drone_command(command_text):
    if registry_manager is None:
        print("Command failed: IoT Hub not connected.")
        return False
    try:
        registry_manager.send_c2d_message(DEVICE_ID, command_text)
        print(f"IoT Hub Success: Sent '{command_text}' to {DEVICE_ID}")
        return True
    except Exception as e:
        print(f"IoT Hub Send Error: {e}")
        return False

@app.route("/")
def home():
    return "Kaset Vision Server is Online!"

@app.route("/data", methods=['POST'])
def receive_data():
    data = request.json
    disease = data.get("disease", "ไม่ระบุชนิด")
    confidence = data.get("confidence", 0)
    image_url = data.get("image_url")
    
    if confidence > 0.8:
        for user_id, info in authorized_users.items():
            if info.get('authorized') and image_url:
                alert_text = f"ตรวจพบโรคในนาข้าว!\n\nชนิด: {disease}\nความเชื่อมั่น: {confidence*100:.1f}%"
                with ApiClient(configuration) as api_client:
                    line_bot_api = MessagingApi(api_client)
                    line_bot_api.push_message(
                        PushMessageRequest(
                            to=user_id,
                            messages=[
                                TextMessage(text=alert_text),
                                ImageMessage(original_content_url=image_url, preview_image_url=image_url)
                            ]
                        )
                    )
    return "OK", 200

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
        elif "ไร่" in user_text and "เมตร" in user_text:
            # Simple parser logic for brevity
            send_drone_command("START_SCAN")
            reply = "รับทราบค่ะ เริ่มดำเนินการบินสแกนพื้นที่"
        elif user_text == "ตรวจสอบสถานะโดรน":
            send_drone_command("GET_STATUS")
            reply = "กำลังดึงข้อมูลจากโดรน..."
        else:
            reply = "คำสั่งไม่ชัดเจน โปรดลองใหม่อีกครั้งค่ะ"
    
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
