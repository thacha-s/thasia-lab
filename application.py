import os
import paho.mqtt.client as mqtt
from flask import Flask, render_template, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, ReplyMessageRequest, 
    PushMessageRequest, TextMessage, ImageMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

app = Flask(__name__)

configuration = Configuration(access_token=os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))
authorized_users = {}
user_state = {}
PRODUCT_ID = "THASIA-KV-001"

MQTT_BROKER = "d1b0d2ac95f14deab954639fbaeba387.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = os.getenv('MQTT_USER')
MQTT_PASS = os.getenv('MQTT_PASSWORD')

def send_drone_command(command_text):
    client = mqtt.Client(transport="websockets") 
    client.tls_set() 
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.connect(MQTT_BROKER, MQTT_PORT)
    client.publish("kaset/vision/commands", command_text)
    client.disconnect()

@app.route("/")
def home():
    return render_template("index.html")

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
                                ImageMessage(
                                    original_content_url=image_url,
                                    preview_image_url=image_url
                                )
                            ]
                        )
                    )
    return "OK", 200

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
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
        authorized_users[user_id] = {'authorized': True, 'area': 1}
        reply = "ยืนยันรหัสผลิตภัณฑ์เรียบร้อยค่ะ ยินดีต้อนรับสู่ระบบ Kaset Vision ค่ะ"
    
    elif user_id not in authorized_users or not authorized_users[user_id]['authorized']:
        reply = "กรุณาใส่รหัส PRODUCT ID เพื่อเริ่มต้นใช้งานระบบควบคุมโดรน"

    else:
        if user_text == "สั่งบิน":
            reply = "กรุณาระบุขนาดพื้นที่นาข้าว (ในหน่วยไร่) เพื่อคำนวณเส้นทางบินค่ะ\n\nตัวอย่างการตอบ: \"1 ไร่\""
        
        elif "ไร่" in user_text and any(char.isdigit() for char in user_text):
            area = [int(s) for s in user_text.split() if s.isdigit()][0]
            user_state[user_id] = area
            reply = f"ระบุความสูงที่ต้องการให้โดรนบิน (เมตร)\n\nตัวอย่าง: \"5 เมตร\""
    
        elif "เมตร" in user_text:
            height = [int(s) for s in user_text.split() if s.isdigit()][0]
            area = user_state.get(user_id, 1)
            send_drone_command(f"START_SCAN_RAI_{area}_ALT_{height}")
            reply = f"รับทราบ! เริ่มสแกนพื้นที่ {area} ไร่ ที่ความสูง {height} เมตร"
    
        elif user_text == "ตรวจสอบสถานะโดรน":
            send_drone_command("GET_STATUS")
            reply = "กำลังดึงข้อมูลจากโดรน... \n\nแบตเตอรี่: กำลังตรวจสอบ\n\nความสูง: -- ม.\n\nความคืบหน้า: --%"
    
        elif user_text == "หยุดระบบฉุกเฉิน":
            reply = "ยืนยันการหยุดระบบฉุกเฉินหรือไม่? (พิมพ์ 'Y' เพื่อทำรายการ)"
    
        elif user_text == "Y":
            send_drone_command("EMERGENCY_STOP")
            reply = "สั่งหยุดระบบฉุกเฉินเรียบร้อยแล้ว! โปรดตรวจสอบความปลอดภัยของโดรน"
    
        elif user_text == "จัดการระบบประมวลผล":
            reply = "ต้องการให้ Raspberry Pi 'ปิดระบบ' หรือ 'เริ่มระบบใหม่' ครับ?"
    
        elif "ปิดระบบ" in user_text or "เริ่มระบบใหม่" in user_text:
            action = "SHUTDOWN" if "ปิดระบบ" in user_text else "REBOOT"
            send_drone_command(action)
            reply = f"รับทราบ กำลังดำเนินรายการ {action} ใน 5 วินาที..."
    
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
    app.run(host="0.0.0.0", port=port)
