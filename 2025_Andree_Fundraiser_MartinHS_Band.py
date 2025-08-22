from flask import Flask, request
from twilio.rest import Client
import openai
import os

app = Flask(__name__)

# Load credentials from environment variables
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_SMS_NUMBER = os.getenv("TWILIO_SMS_NUMBER")  # e.g. +12292354360
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")  # e.g. whatsapp:+12292354360
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
openai.api_key = OPENAI_API_KEY

@app.route("/sms", methods=['POST'])
def sms_reply():
    incoming_msg = request.values.get('Body', '').strip()
    from_number = request.values.get('From', '')
    
    # Generate GPT response
    gpt_response = get_gpt_response(incoming_msg)

    # Send SMS back
    client.messages.create(
        body=gpt_response,
        from_=TWILIO_SMS_NUMBER,
        to=from_number
    )

    return "OK", 200

@app.route("/whatsapp", methods=['POST'])
def whatsapp_reply():
    incoming_msg = request.values.get('Body', '').strip()
    from_number = request.values.get('From', '')
    
    # Generate GPT response
    gpt_response = get_gpt_response(incoming_msg)

    # Send WhatsApp reply
    client.messages.create(
        body=gpt_response,
        from_=TWILIO_WHATSAPP_NUMBER,
        to=from_number
    )

    return "OK", 200

def get_gpt_response(prompt):
    response = openai.ChatCompletion.create(
        model="gpt-4",  # or gpt-4o-mini for cost efficiency
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    return response['choices'][0]['message']['content']

if __name__ == "__main__":
    app.run(debug=True)
