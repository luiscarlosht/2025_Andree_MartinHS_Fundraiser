from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import openai
import os

# Load environment variables (replace with your actual keys or use dotenv)
openai.api_key = os.getenv("OPENAI_API_KEY")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")

app = Flask(__name__)

@app.route("/whatsapp", methods=["POST"])
def whatsapp_reply():
    incoming_msg = request.form.get("Body")  # WhatsApp message text
    sender = request.form.get("From")       # WhatsApp sender

    print(f"Message from {sender}: {incoming_msg}")

    # Generate GPT-5 response
    try:
        completion = openai.ChatCompletion.create(
            model="gpt-5",  # Make sure you have GPT-5 access
            messages=[
                {"role": "system", "content": "You are a helpful assistant for fundraising."},
                {"role": "user", "content": incoming_msg}
            ]
        )
        gpt_response = completion['choices'][0]['message']['content'].strip()
    except Exception as e:
        gpt_response = f"Error generating response: {str(e)}"

    # Respond to WhatsApp
    resp = MessagingResponse()
    msg = resp.message()
    msg.body(gpt_response)

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
