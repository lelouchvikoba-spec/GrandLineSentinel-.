"""Persistent Telegram animation file ID for successful /claim rewards."""
import json
import os
import tempfile

from config import DATA_DIR

CLAIM_GIF_PATH = os.path.join(DATA_DIR, "claim_reward_gif.json")


def get_claim_reward_gif():
    try:
        with open(CLAIM_GIF_PATH, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None
    value = raw.get("file_id") if isinstance(raw, dict) else None
    return value.strip() if isinstance(value, str) and value.strip() else None


def set_claim_reward_gif(file_id):
    value = str(file_id or "").strip()
    if not value:
        raise ValueError("A Telegram animation file ID is required")
    os.makedirs(DATA_DIR, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix="claim_reward_gif_", suffix=".json", dir=DATA_DIR)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"file_id": value}, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(temp_path, CLAIM_GIF_PATH)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def clear_claim_reward_gif():
    existed = os.path.exists(CLAIM_GIF_PATH)
    try:
        os.remove(CLAIM_GIF_PATH)
    except FileNotFoundError:
        existed = False
    return existed


async def send_claim_reward_animation(client, chat_id, caption, reply_to_message_id=None):
    """Send the configured claim animation; return False when unset or unavailable."""
    file_id = get_claim_reward_gif()
    if not file_id:
        return False
    try:
        await client.send_animation(
            chat_id,
            file_id,
            caption=caption,
            reply_to_message_id=reply_to_message_id,
        )
    except Exception as exc:
        print(f"[claim reward GIF] failed to send: {exc}")
        return False
    return True
