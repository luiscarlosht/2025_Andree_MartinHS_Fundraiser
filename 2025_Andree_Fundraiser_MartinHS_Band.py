from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import openai
import os

app = Flask(__name__)

# Set environment variables before running:
# export OPENAI_API_KEY="your_openai_key"
# export TWILIO_AUTH_TOKEN="your_twilio_auth_token"
# export TWILIO_ACCOUNT_SID="your_twilio_sid"

openai.api_key = os.getenv("OPENAI_API_KEY")

@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.form.get("Body")
    sender = request.form.get("From")

    print(f"Received from {sender}: {incoming_msg}")

    # Generate GPT-5 response
    gpt_response = generate_gpt_response(incoming_msg)

    # Send response back
    twilio_response = MessagingResponse()
    twilio_response.message(gpt_response)

    return str(twilio_response)

def generate_gpt_response(prompt):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",  # Use GPT-5 alias if available
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.7
        )
        return response['choices'][0]['message']['content'].strip()
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
