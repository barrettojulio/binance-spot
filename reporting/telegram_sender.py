import requests
class TelegramSender:
    def __init__(self, settings):
        api = settings.get("api", {})
        self.token = api.get("telegram_token", "").strip()
        self.chat_id = api.get("telegram_chat_id", "").strip()
    def send_message(self, text: str):
        if not self.token or not self.chat_id:
            print("[Telegram] Missing token/chat_id. Skipping send.")
            return
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        data = {"chat_id": self.chat_id, "text": text}
        try:
            requests.post(url, data=data, timeout=20)
        except Exception as e:
            print("[Telegram] Send error:", e)
