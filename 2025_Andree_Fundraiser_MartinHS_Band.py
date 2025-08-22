from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

@app.route("/message", methods=["POST"])
def handle_message():
    """Respond to SMS and WhatsApp messages."""
    from_number = request.form.get("From")
    incoming_msg = request.form.get("Body")

    resp = MessagingResponse()

    if from_number.startswith("whatsapp:"):
        reply_text = f"(WhatsApp) Thanks for contacting us! You said: {incoming_msg}"
    else:
        reply_text = f"(SMS) Thanks for contacting us! You said: {incoming_msg}"

    resp.message(reply_text)
    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
