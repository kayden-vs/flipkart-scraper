import requests
import logging

def send_telegram_message(message, bot_token, chat_id):
    """
    Sends a message to the specified Telegram chat using the bot token.
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code != 200:
            logging.error("Failed to send Telegram message: %s", response.text)
    except requests.RequestException as e:
        logging.error("Error sending Telegram message: %s", e)