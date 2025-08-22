import os
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI

# Load environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM")
WHATSAPP_TO = os.getenv("WHATSAPP_TO")

if not OPENAI_API_KEY:
    raise ValueError("Missing OpenAI API key! Set OPENAI_API_KEY as an environment variable.")

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

app = Flask(__name__)

@app.route("/whatsapp", methods=["POST"])
def whatsapp_reply():
    incoming_msg = request.values.get("Body", "").strip()
    response = MessagingResponse()
    msg = response.message()

    if incoming_msg:
        try:
            # Send to GPT-5 model
            ai_response = client.responses.create(
                model="gpt-5",
                input=incoming_msg
            )

            bot_reply = ai_response.output_text.strip()
            msg.body(bot_reply)

        except Exception as e:
            msg.body(f"Error: {str(e)}")
    else:
        msg.body("Hi! Please send a message to get started.")

    return str(response)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
