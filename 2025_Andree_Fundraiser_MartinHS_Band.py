from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import openai
import os

app = Flask(__name__)

# Set your keys
openai.api_key = os.getenv("OPENAI_API_KEY")

@app.route("/sms", methods=["POST"])
def sms_reply():
    incoming_msg = request.form.get("Body")
    sender = request.form.get("From")

    # GPT-5 Response
    response = openai.ChatCompletion.create(
        model="gpt-5",
        messages=[{"role": "system", "content": "You are a friendly fundraising assistant."},
                  {"role": "user", "content": incoming_msg}]
    )

    reply_text = response["choices"][0]["message"]["content"]

    # Twilio Reply
    resp = MessagingResponse()
    resp.message(reply_text)
    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
