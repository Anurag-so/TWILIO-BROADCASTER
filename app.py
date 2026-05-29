import os
import re
import json
import time
from datetime import datetime
import requests
from flask import Flask, render_template, request, jsonify, Response
from twilio.rest import Client
from openai import OpenAI
from dotenv import load_dotenv

# Load config from .env
load_dotenv()

app = Flask(__name__, template_folder="templates", static_folder="static")

DATA_FILE = "people.json"

# In-memory chat logs for the UI monitor (persists during server uptime)
CHAT_LOGS = []

# -------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------

def load_people():
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []

def save_people(people_list):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(people_list, f, indent=2)
        return True
    except Exception as e:
        print(f"❌ Save Failed: {e}")
        return False

def add_chat_log(sender_name, message, log_type):
    """Adds a new message entry to the in-memory chat monitor log list."""
    CHAT_LOGS.append({
        "sender": sender_name,
        "message": message,
        "type": log_type,  # 'incoming' (user text) or 'outgoing' (AI reply)
        "time": datetime.now().strftime("%I:%M %p")
    })
    # Keep only the last 50 chat messages in-memory to prevent bloat
    if len(CHAT_LOGS) > 50:
        CHAT_LOGS.pop(0)

# -------------------------------------------------------------
# Outbound Communication Handlers
# -------------------------------------------------------------

def trigger_sms(name, phone, text, sid, token, twilio_phone):
    try:
        client = Client(sid, token)
        message = client.messages.create(body=text, from_=twilio_phone, to=phone)
        return True
    except Exception as e:
        print(f"❌ Twilio SMS Error for {name}: {e}")
        return False

def trigger_voice_call(name, phone, text, sid, token, twilio_phone):
    twiml_instruction = f'<Response><Say voice="alice">{text}</Say></Response>'
    try:
        client = Client(sid, token)
        client.calls.create(twiml=twiml_instruction, from_=twilio_phone, to=phone)
        return True
    except Exception as e:
        print(f"❌ Twilio Call Error for {name}: {e}")
        return False

def trigger_whatsapp_green(name, phone, text, green_id, green_token):
    clean_phone = phone.replace("+", "").strip()
    chat_id = f"{clean_phone}@c.us"
    url = f"https://api.green-api.com/waInstance{green_id}/sendMessage/{green_token}"
    payload = {"chatId": chat_id, "message": text}
    
    # ⚡ Added flush=True to force instant printing in terminal!
    print(f"\n🟢 Preparing Personal WhatsApp for {name} ({phone})...", flush=True)
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        res_data = response.json()
        
        # 🔍 DEBUG: Print the exact response if it fails
        if response.status_code == 200 and "idMessage" in res_data:
            print(f"   ✅ WhatsApp sent successfully! Msg ID: {res_data['idMessage']}", flush=True)
            return True
        else:
            print(f"   ❌ Green-API Send Failed (Status {response.status_code}): {res_data}", flush=True)
            return False
            
    except Exception as e:
        print(f"   ❌ Request Failed: {e}", flush=True)
        return False

# -------------------------------------------------------------
# HTML Frontend Route
# -------------------------------------------------------------

@app.route("/")
def index():
    """Renders the main glassmorphic dashboard webpage."""
    return render_template("index.html")

# -------------------------------------------------------------
# REST API Endpoints
# -------------------------------------------------------------

@app.route("/api/contacts", methods=["GET", "POST"])
def manage_contacts():
    """GET/POST endpoint for managing the local people.json contacts list."""
    if request.method == "GET":
        return jsonify(load_people())
        
    elif request.method == "POST":
        data = request.json
        name = data.get("name", "").strip()
        phone = data.get("phone", "").strip()
        tags = data.get("tags", [])

        if not name or not phone:
            return jsonify({"success": False, "message": "Name and Phone are required."}), 400

        people = load_people()
        people.append({
            "name": name,
            "phone": phone,
            "tags": [tag.strip().lower() for tag in tags if tag.strip()]
        })
        
        if save_people(people):
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "message": "Database write error."}), 500

@app.route("/api/broadcast", methods=["POST"])
def launch_broadcast():
    """Filters contacts by tag and broadcasts personalized SMS, Calls, or WhatsApp texts."""
    data = request.json
    tag = data.get("tag", "").strip().lower()
    method = data.get("method", "").strip().lower()
    message_template = data.get("message", "").strip()

    if not tag or not method or not message_template:
        return jsonify({"success": False, "message": "All fields are required."}), 400

    people = load_people()
    matching_people = [p for p in people if tag in [t.lower() for t in p.get("tags", [])]]

    if not matching_people:
        return jsonify({"success": False, "message": f"No contacts found with tag '{tag}'."}), 404

    # Load credentials from system variables
    green_id = os.getenv("GREEN_API_ID_INSTANCE")
    green_token = os.getenv("GREEN_API_TOKEN_INSTANCE")
    twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
    twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
    twilio_phone = os.getenv("TWILIO_PHONE_NUMBER")

    sent_count = 0

    # Execute sending queue
    for p in matching_people:
        # Dynamic personalized template substitution
        personalized_text = message_template.replace("{name}", p["name"])

        if method == "sms":
            if trigger_sms(p["name"], p["phone"], personalized_text, twilio_sid, twilio_token, twilio_phone):
                sent_count += 1
        elif method == "call":
            if trigger_voice_call(p["name"], p["phone"], personalized_text, twilio_sid, twilio_token, twilio_phone):
                sent_count += 1
        elif method == "whatsapp":
            if trigger_whatsapp_green(p["name"], p["phone"], personalized_text, green_id, green_token):
                sent_count += 1
        
        # Subtle sleep to respect rate-limiting
        time.sleep(0.5)

    return jsonify({
        "success": True,
        "sent_count": sent_count,
        "total_targets": len(matching_people)
    })

# -------------------------------------------------------------
# Real-Time Chat logs API
# -------------------------------------------------------------

@app.route("/api/chat-logs", methods=["GET", "DELETE"])
def manage_chat_logs():
    """GETs current chat logs or DELETEs the logs list completely."""
    global CHAT_LOGS
    if request.method == "GET":
        return jsonify(CHAT_LOGS)
    elif request.method == "DELETE":
        CHAT_LOGS = []
        return jsonify({"success": True})

# -------------------------------------------------------------
# System settings management (.env dynamic saver)
# -------------------------------------------------------------

@app.route("/api/settings", methods=["GET", "POST"])
def manage_settings():
    """Retrieves or dynamically updates `.env` values from the UI dashboard."""
    if request.method == "GET":
        return jsonify({
            "GREEN_API_ID_INSTANCE": os.getenv("GREEN_API_ID_INSTANCE", ""),
            "GREEN_API_TOKEN_INSTANCE": os.getenv("GREEN_API_TOKEN_INSTANCE", ""),
            "TWILIO_ACCOUNT_SID": os.getenv("TWILIO_ACCOUNT_SID", ""),
            "TWILIO_AUTH_TOKEN": os.getenv("TWILIO_AUTH_TOKEN", ""),
            "TWILIO_PHONE_NUMBER": os.getenv("TWILIO_PHONE_NUMBER", ""),
            "OPENROUTER_API_KEY": os.getenv("OPENROUTER_API_KEY", ""),
            "OPENROUTER_MODEL": os.getenv("OPENROUTER_MODEL", "qwen/qwen3-32b")
        })
        
    elif request.method == "POST":
        data = request.json
        # Format the incoming configuration settings back as key=value lines
        env_lines = [
            f"GREEN_API_ID_INSTANCE={data.get('GREEN_API_ID_INSTANCE', '').strip()}",
            f"GREEN_API_TOKEN_INSTANCE={data.get('GREEN_API_TOKEN_INSTANCE', '').strip()}",
            f"TWILIO_ACCOUNT_SID={data.get('TWILIO_ACCOUNT_SID', '').strip()}",
            f"TWILIO_AUTH_TOKEN={data.get('TWILIO_AUTH_TOKEN', '').strip()}",
            f"TWILIO_PHONE_NUMBER={data.get('TWILIO_PHONE_NUMBER', '').strip()}",
            f"OPENROUTER_API_KEY={data.get('OPENROUTER_API_KEY', '').strip()}",
            f"OPENROUTER_MODEL={data.get('OPENROUTER_MODEL', 'qwen/qwen3-32b').strip()}"
        ]

        try:
            with open(".env", "w") as f:
                f.write("\n".join(env_lines) + "\n")
            
            # Instantly reload system variables in memory
            for line in env_lines:
                if "=" in line:
                    key, val = line.split("=", 1)
                    os.environ[key] = val
                    
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500

# -------------------------------------------------------------
# Real-Time Green-API Webhook Endpoint
# -------------------------------------------------------------

@app.route("/webhook", methods=["POST"])
def whatsapp_webhook():
    """
    Webhook endpoint that Green-API calls when a WhatsApp message is received.
    Uses OpenRouter + Qwen3 to generate conversational human responses.
    """
    data = request.json
    if not data:
        return jsonify({"status": "no data"}), 400

    webhook_type = data.get("typeWebhook")
    message_data = data.get("messageData", {})
    type_message = message_data.get("typeMessage")
    
    # 1. Check if this is an incoming message
    if webhook_type == "incomingMessageReceived" and type_message in ["textMessage", "extendedTextMessage"]:
        chat_id = data.get("senderData", {}).get("chatId")
        sender_name = data.get("senderData", {}).get("senderName", "Friend")

        # Extract message content depending on message formatting type
        if type_message == "textMessage":
            incoming_msg = message_data.get("textMessageData", {}).get("textMessage", "").strip()
        else:
            incoming_msg = message_data.get("extendedTextMessageData", {}).get("text", "").strip()

        print(f"\n📨 Webhook WhatsApp from {sender_name} ({chat_id}): '{incoming_msg}'")
        
        # Log the incoming message to the Dashboard's chat screen!
        add_chat_log(sender_name, incoming_msg, "incoming")

        # Load OpenRouter Credentials in real-time
        or_key = os.getenv("OPENROUTER_API_KEY")
        or_model = os.getenv("OPENROUTER_MODEL", "qwen/qwen3-32b")
        green_id = os.getenv("GREEN_API_ID_INSTANCE")
        green_token = os.getenv("GREEN_API_TOKEN_INSTANCE")

        system_prompt = (
            "You are a real human friend chatting casually on WhatsApp. "
            "Speak in an extremely natural, casual, and warm human way. "
            "Fluent in Hinglish (Hindi written in English alphabets like 'kaise ho bro?', 'sahi hai', 'kya haal hai?'), "
            "Hindi, and casual English. Reply in the same language/vibe that the user uses. "
            "Keep your replies very short, relaxed, and warm—just like a friend texting on WhatsApp. "
            "Use casual texting slang (like 'bro', 'haha', 'haan', 'sahi hai', 'yaaar') and a few emojis naturally. "
            "Do NOT sound like a robot, AI, or professional bot."
        )

        try:
            print(f"🤖 Generating AI reply using OpenRouter model '{or_model}'...")
            client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=or_key)
            
            response = client.chat.completions.create(
                extra_headers={
                    "HTTP-Referer": "http://localhost:5000",
                    "X-Title": "WhatsApp Chatbot",
                },
                model=or_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": incoming_msg}
                ]
            )
            
            raw_reply = response.choices[0].message.content.strip()
            print(f"📥 Raw AI Response: '{raw_reply}'")

            # SMART FILTER: Strip out thinking tokens (<think>...</think>)
            ai_reply = re.sub(r'<think>.*?</think>', '', raw_reply, flags=re.DOTALL).strip()
            if "</think>" in ai_reply:
                ai_reply = ai_reply.split("</think>")[-1].strip()

            print(f"📤 Cleaned Human Reply: '{ai_reply}'")

            # Log outgoing reply to dashboard
            add_chat_log("AI Friend", ai_reply, "outgoing")

            # Send reply back to the contact
            trigger_whatsapp_green(sender_name, chat_id.split("@")[0], ai_reply, green_id, green_token)

        except Exception as e:
            print(f"❌ Error generating reply: {e}")
            fallback = "Oops! Connection drop ho gaya bro. Ek baar firse message karo na!"
            add_chat_log("AI Friend", fallback, "outgoing")
            trigger_whatsapp_green(sender_name, chat_id.split("@")[0], fallback, green_id, green_token)
            
    # 2. Log outgoing message (So that messages sent from your actual phone ALSO appear in the live chat!)
    elif webhook_type == "outgoingAPIMessageReceived" or webhook_type == "outgoingMessageReceived":
        message_data = data.get("messageData", {})
        type_message = message_data.get("typeMessage")
        
        if type_message in ["textMessage", "extendedTextMessage"]:
            if type_message == "textMessage":
                msg = message_data.get("textMessageData", {}).get("textMessage", "").strip()
            else:
                msg = message_data.get("extendedTextMessageData", {}).get("text", "").strip()
                
            sender_name = data.get("senderData", {}).get("senderName", "You")
            
            # Avoid duplicate logs for messages generated by the AI
            if "Oops! Kuch network issue" not in msg and not any(log["message"] == msg for log in CHAT_LOGS[-3:]):
                print(f"📤 Outgoing WhatsApp Logged: '{msg}'")
                add_chat_log(sender_name, msg, "outgoing")

    return jsonify({"status": "success"}), 200

# -------------------------------------------------------------
# Launch Local Server
# -------------------------------------------------------------

if __name__ == "__main__":
    print("==================================================")
    print("      🎨 PREMIUM GLASSMORPHIC DASHBOARD ACTIVE    ")
    print("==================================================")
    print("🚀 URL: http://localhost:5000")
    print("🔗 Send Green-API Webhooks to: http://<your-ngrok-url>/webhook")
    print("==================================================")
    
    app.run(host="0.0.0.0", port=5000, debug=True)
