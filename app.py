import os
from dotenv import load_dotenv
import fb_bot

from flask import Flask, request

app = Flask(__name__)


@app.route('/', methods=['GET'])
def verify():
    """
    При верификации вебхука у Facebook он отправит запрос на этот адрес. На него нужно ответить VERIFY_TOKEN.
    """
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if not request.args.get("hub.verify_token") == os.getenv('VERIFY_TOKEN'):
            return "Verification token mismatch", 403
        return request.args["hub.challenge"], 200

    return "Hello world", 200


@app.route('/', methods=['POST'])
def webhook():
    """
    Основной вебхук, на который будут приходить сообщения от Facebook.
    """
    data = request.get_json()
    if data["object"] != "page":
        return "ok", 200
    for entry in data["entry"]:
        for messaging_event in entry["messaging"]:
                sender_id = messaging_event["sender"]["id"]
                if messaging_event.get("message"):
                    message_text = messaging_event["message"]["text"]
                    fb_bot.handle_users_reply(sender_id, message_text)
                elif messaging_event.get('postback'):
                    postback = messaging_event['postback']['payload']
                    fb_bot.handle_users_reply(sender_id, postback)
    return "ok", 200


if __name__ == '__main__':
    load_dotenv()
    app.run(debug=True)
