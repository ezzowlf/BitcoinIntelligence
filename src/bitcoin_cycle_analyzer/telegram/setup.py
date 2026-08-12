from __future__ import annotations
import json,os
from pathlib import Path
from .client import TelegramClient

def masked_token(token):return "UNSET" if not token else f"{token[:4]}...{token[-4:]}"
def discover_chats(token,session=None):
    client=TelegramClient(token,None,enabled=True,dry_run=False,session=session);client.dry_run=False;me=client.get_me();chats={}
    for update in client.get_updates():
        message=update.get("message") or update.get("channel_post") or {};chat=message.get("chat",{})
        if chat.get("id") is not None and str(message.get("text","")).split()[0:1]==["/start"]:chats[str(chat["id"]) ]={"chat_id":str(chat["id"]),"type":chat.get("type"),"title":chat.get("title") or chat.get("username") or chat.get("first_name") or "unknown"}
    return me,list(chats.values())
def save_allowlist(path,chat_ids,bot):
    payload={"allowed_chat_ids":sorted({str(x) for x in chat_ids}),"bot_id":bot.get("id"),"bot_username":bot.get("username"),"token":"NOT_STORED"};path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(payload,indent=2),encoding="utf-8");return payload
def run_setup(path,selected_chat_ids=None,session=None,input_fn=input,output_fn=print):
    token=os.getenv("TELEGRAM_BOT_TOKEN","").strip()
    if not token:raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    output_fn(f"Testing Telegram token {masked_token(token)}");me,chats=discover_chats(token,session)
    if not chats:raise RuntimeError("No /start update found. Send /start to the bot and retry.")
    if selected_chat_ids is None:
        output_fn("Available chats: "+", ".join(f"{c['chat_id']} ({c['title']})" for c in chats));selected_chat_ids=[x.strip() for x in input_fn("Allowed chat IDs (comma-separated): ").split(",") if x.strip()]
    valid={c["chat_id"] for c in chats}
    if not selected_chat_ids or not set(map(str,selected_chat_ids))<=valid:raise ValueError("allowlist contains an unknown chat ID")
    return save_allowlist(path,list(map(str,selected_chat_ids)),me)
def load_allowlist(path):
    path=Path(path);return set() if not path.exists() else set(map(str,json.loads(path.read_text(encoding="utf-8")).get("allowed_chat_ids",[])))
