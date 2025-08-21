from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import openai
import os

app = Flask(__name__)

# 🔑 Set your API key (better: export OPENAI_API_KEY in your VM)
openai.api_key = os.getenv("OPENAI_API_KEY")

@app.route("/sms", methods=["POST"])
def sms_reply():
    """Respond to incoming WhatsApp messages with GPT-5."""
    incoming_msg = request.form.get("Body", "").strip()
    
    # Generate reply using GPT-5
    try:
        response = openai.ChatCompletion.create(
            model="gpt-5",   # 👈 switched to GPT-5
            messages=[
                {"role": "system", "content": "You are a helpful assistant for a fundraiser campaign."},
                {"role": "user", "content": incoming_msg}
            ],
            max_tokens=300
        )
        gpt_reply = response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        gpt_reply = f"⚠️ Error: {str(e)}"

    # Twilio WhatsApp response
    resp = MessagingResponse()
    resp.message(gpt_reply)
    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
