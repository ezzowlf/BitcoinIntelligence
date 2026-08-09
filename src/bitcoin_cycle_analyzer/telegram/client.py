from __future__ import annotations

import logging
import time
import requests
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass


class TelegramClient:
    def __init__(self, token, chat_id, enabled=False, dry_run=True, retries=3, session=None):
        self.token=token;self.chat_id=str(chat_id) if chat_id else None;self.enabled=enabled;self.dry_run=dry_run or not (enabled and token and chat_id);self.retries=retries;self.session=session or requests.Session()

    def send(self, message):
        if self.dry_run:
            return {"status":"DRY_RUN","delivered":False,"message":message}
        url=f"https://api.telegram.org/bot{self.token}/sendMessage"
        for attempt in range(1,self.retries+1):
            try:
                response=self.session.post(url,json={"chat_id":self.chat_id,"text":message},timeout=15)
                response.raise_for_status()
                payload=response.json()
                if not payload.get("ok"):raise RuntimeError("Telegram rejected the message")
                return {"status":"DELIVERED","delivered":True,"message_id":payload["result"]["message_id"]}
            except Exception as exc:
                logging.warning("Telegram delivery failed (%s/%s): %s",attempt,self.retries,type(exc).__name__)
                if attempt<self.retries:time.sleep(min(2**(attempt-1),4))
        return {"status":"FAILED","delivered":False}

    def get_updates(self, offset=None):
        if self.dry_run:return []
        response=self.session.get(f"https://api.telegram.org/bot{self.token}/getUpdates",params={"timeout":10,"offset":offset} if offset else {"timeout":10},timeout=15)
        response.raise_for_status();payload=response.json()
        return payload.get("result",[]) if payload.get("ok") else []

    def authorized_command(self, update):
        message=update.get("message",{});chat=message.get("chat",{})
        if str(chat.get("id"))!=self.chat_id:return None
        text=message.get("text","").split("@",1)[0].strip().split()[0] if message.get("text") else ""
        return text if text.startswith("/") else None
