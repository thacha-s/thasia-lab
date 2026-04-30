import os
from flask import Flask, render_template, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, ReplyMessageRequest, 
    PushMessageRequest, TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

app = Flask(__name__)

configuration = Configuration(access_token=os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))

# Your User ID (Found in LINE Developers Console under Messaging API tab)
# Or you can capture it dynamically when you message the bot
ADMIN_USER_ID = os.getenv('USER_ID') 

@app.route("/")
def home():
    return render_template("index.html")

# --- ROUTE FOR THE RASPBERRY PI ---
@app.route("/sensor-data", methods=['POST'])
def receive_sensor_data():
    data = request.json  # This gets the {"status": "...", "location": "..."} from your Pi
    status = data.get("status", "Unknown Alert")
    location = data.get("location", "Unknown Location")
    
    alert_text = f"🚨 KASET VISION ALERT!\nStatus: {status}\nLocation: {location}"
    
    # Push message to YOU (not a reply, but an proactive alert)
    if ADMIN_USER_ID:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.push_message(
                PushMessageRequest(
                    to=ADMIN_USER_ID,
                    messages=[TextMessage(text=alert_text)]
                )
            )
    return "OK", 200

# --- ROUTE FOR LINE WEBHOOK ---
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
    user_text = event.message.text.lower()
    
    # Store your User ID if you don't know it yet (check Azure logs)
    print(f"User ID is: {event.source.user_id}")

    if "status" in user_text:
        reply = "Kaset Vision Cloud: All systems operational. Waiting for drone telemetry."
    else:
        reply = f"Cloud received: {event.message.text}"

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
