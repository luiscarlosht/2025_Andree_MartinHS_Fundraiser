from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import openai
import os

app = Flask(__name__)

# Configure OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

@app.route("/", methods=["GET"])
def home():
    return """
    <h1>🎶 Andree Martin HS Band Fundraiser 🎶</h1>
    <p>Welcome! This is our fundraising chatbot powered by Flask + Twilio + OpenAI.</p>
    <p><a href='/donate'>Click here to donate</a></p>
    """

@app.route("/donate", methods=["GET"])
def donate():
    return """
    <h1>💖 Support the Andree Martin HS Band 💖</h1>
    <p>Thank you for supporting our fundraiser! 🎺🥁🎷</p>
    <p>Donations help us buy instruments, uniforms, and fund trips.</p>
    <p><b>Ways to donate:</b></p>
    <ul>
        <li>Send a check payable to <i>Andree Martin HS Band</i></li>
        <li>CashApp / Venmo (coming soon)</li>
        <li>Contact us directly via the chatbot 🤖</li>
    </ul>
    <a href='/'>⬅️ Back to Home</a>
    """

@app.route("/sms", methods=["POST"])
def sms_reply():
    """Respond to incoming SMS with an AI-generated message"""
    incoming_msg = request.form.get("Body", "").strip()
    
    # Default reply if no message
    if not incoming_msg:
        reply = "Hello! Thanks for messaging the Andree Martin HS Band fundraiser."
    else:
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": incoming_msg}]
            )
            reply = response.choices[0].message["content"].strip()
        except Exception as e:
            reply = f"⚠️ Error: {str(e)}"

    # Twilio SMS response
    resp = MessagingResponse()
    resp.message(reply)
    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
