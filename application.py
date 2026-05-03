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

latest_sensor_data = {
    "battery": "-",
    "altitude": 0,
    "progress": "-"
}

configuration = Configuration(access_token=os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))

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

@app.route("/sensor-data", methods=['POST'])
def receive_sensor_data():
    global latest_sensor_data
    data = request.json
    latest_sensor_data["battery"] = data.get("battery", "-")
    latest_sensor_data["altitude"] = data.get("altitude", 0)
    latest_sensor_data["progress"] = data.get("progress", "-")
    return jsonify({"status": "success"}), 200

@app.route("/data", methods=['POST'])
def receive_detection():
    data = request.json
    disease = data.get("disease", "ไม่ทราบชนิด")
    confidence = data.get("confidence", 0)
    image_url = data.get("image_url")
    
    if confidence > 0.8:
        alert_text = f"ตรวจพบโรคในนาข้าว!\n\nชนิด: {disease}\nความเชื่อมั่น: {confidence*100:.1f}%"
        for user_id in authorized_users:
            if authorized_users[user_id].get('authorized'):
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

@app.route("/")
def home():
    return render_template('index.html')

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
            reply = "กรุณาระบุขนาดพื้นที่นาข้าว (ไร่) เช่น '1 ไร่'"
        
        elif "ไร่" in user_text and any(char.isdigit() for char in user_text):
            area = [int(s) for s in user_text.split() if s.isdigit()][0]
            user_state[user_id] = {'area': area}
            reply = f"ระบุความสูงที่ต้องการให้โดรนบิน (เมตร) ตัวอย่าง: '5 เมตร'"
        
        elif "เมตร" in user_text and user_id in user_state:
            height = [int(s) for s in user_text.split() if s.isdigit()][0]
            area = user_state[user_id].get('area', 1)
            send_drone_command(f"START_SCAN_RAI_{area}_ALT_{height}")
            reply = f"รับทราบค่ะ เริ่มสแกนพื้นที่ {area} ไร่ ที่ความสูง {height} เมตร"
        
        elif user_text == "ตรวจสอบสถานะโดรน":
            send_drone_command("GET_STATUS") 
            
            reply = (f"📊 สถานะโดรนล่าสุด:\n"
                     f"🔋 แบตเตอรี่: {latest_sensor_data['battery']}%\n"
                     f"📏 ความสูง: {latest_sensor_data['altitude']} เมตร\n"
                     f"📈 ความคืบหน้า: {latest_sensor_data['progress']}%")

        elif user_text == "จัดการระบบประมวลผล":
            reply = "ต้องการให้ Raspberry Pi 'ปิดระบบ' หรือ 'เริ่มระบบใหม่' คะ"

        elif user_text == "หยุดระบบฉุกเฉิน":
            user_state[user_id] = {'pending_action': 'EMERGENCY_STOP'}
            reply = "⚠️ ยืนยันการหยุดระบบฉุกเฉินหรือไม่?\n\nพิมพ์ 'Y' เพื่อยืนยัน หรือ 'N' เพื่อยกเลิก"
    
        elif user_id in user_state and user_state[user_id].get('pending_action') == 'EMERGENCY_STOP':
            if user_text.upper() == 'Y':
                success = send_drone_command("EMERGENCY_STOP")
                if success:
                    reply = "รับทราบค่ะ โดรนกำลังหยุดทำงานทันที"
                else:
                    reply = "ไม่สามารถส่งคำสั่งได้ โปรดใช้รีโมทสำรอง"
            else:
                reply = "ยกเลิกคำสั่งหยุดฉุกเฉิน ระบบยังคงทำงานปกติ"
        
            del user_state[user_id]
        
        elif "ปิดระบบ" in user_text or "เริ่มระบบใหม่" in user_text:
            action = "SHUTDOWN" if "ปิดระบบ" in user_text else "REBOOT"
            success = send_drone_command(action)
            if success:
                reply = f"รับทราบค่ะ กำลังดำเนินรายการ {action} ใน 5 วินาที..."
            else:
                reply = "เกิดข้อผิดพลาดในการส่งคำสั่งไปยังโดรน โปรดตรวจสอบการเชื่อมต่อ"

    
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
