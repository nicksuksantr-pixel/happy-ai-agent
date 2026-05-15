"""
auth.py — Gemini API key authentication (AI Studio)

ใช้ Gemini Developer API ผ่าน API key จาก https://aistudio.google.com/apikey
ไม่ต้อง Google Cloud project, ไม่ต้อง Service Account JSON

ความปลอดภัย:
  - API key save ที่ ~/.happy/auth.json (เฉพาะ user ปัจจุบัน)
  - File permission ตาม OS default (Windows: user-only readable)
"""
import json
import os
import stat
from pathlib import Path
from typing import Optional, Tuple

from google import genai


CONFIG_DIR = Path.home() / ".happy"
CONFIG_FILE = CONFIG_DIR / "auth.json"


# ─────────────── Config (save/load API key) ───────────────

def save_api_key(api_key: str) -> Tuple[bool, str]:
    """Save API key to ~/.happy/auth.json (user-only readable on POSIX)"""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {"api_key": api_key.strip()}
        CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        # POSIX: chmod 600 (user-only). On Windows ACL = current user only by default.
        try:
            os.chmod(CONFIG_FILE, stat.S_IRUSR | stat.S_IWUSR)
        except Exception:
            pass
        return True, "บันทึก key แล้ว"
    except Exception as e:
        return False, f"บันทึกไม่ได้: {str(e)[:200]}"


def load_api_key() -> Optional[str]:
    """Load API key from ~/.happy/auth.json. Returns None if not set."""
    try:
        if not CONFIG_FILE.exists():
            return None
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        key = data.get("api_key", "").strip()
        return key if key else None
    except Exception:
        return None


def clear_api_key() -> bool:
    """Remove the stored API key (logout)"""
    try:
        if CONFIG_FILE.exists():
            CONFIG_FILE.unlink()
        return True
    except Exception:
        return False


def is_valid_key_format(key: str) -> bool:
    """ตรวจสอบ format ของ key คร่าวๆ (AI Studio key ขึ้นต้น AIza)"""
    return bool(key) and key.strip().startswith("AIza") and len(key.strip()) >= 35


# ─────────────── Client ───────────────

def create_client(api_key: str) -> Tuple[Optional[object], Optional[str]]:
    """Create genai.Client using AI Studio API key"""
    try:
        if not api_key or not api_key.strip():
            return None, "API key ว่าง"
        client = genai.Client(api_key=api_key.strip())
        return client, None
    except Exception as e:
        return None, f"สร้าง client ไม่ได้: {str(e)[:200]}"


def test_connection(client) -> Tuple[bool, str]:
    """ทดสอบเชื่อมต่อโดย list models"""
    try:
        models = list(client.models.list())
        if not models:
            return False, "เชื่อมต่อได้ แต่ไม่เจอ model"
        return True, f"✅ เชื่อมต่อสำเร็จ — เจอ {len(models)} models"
    except Exception as e:
        msg = str(e).lower()
        if "api key" in msg or "api_key" in msg or "401" in msg or "unauthor" in msg:
            return False, "❌ API key ไม่ถูกต้อง — ตรวจสอบ key ใหม่ที่ aistudio.google.com/apikey"
        if "quota" in msg or "rate" in msg or "429" in msg:
            return False, "❌ ติด rate limit — รอสักครู่"
        if "permission" in msg:
            return False, "❌ key นี้ไม่มีสิทธิ์เรียก Gemini API"
        return False, f"❌ เชื่อมต่อไม่ได้: {str(e)[:120]}"


def list_available_models(client) -> list:
    """List Gemini text generation models (filtered + sorted, ใหม่ก่อน)"""
    try:
        all_models = list(client.models.list())
        names = []
        for m in all_models:
            name = m.name.split("/")[-1] if "/" in m.name else m.name
            nl = name.lower()
            # ตัด models ที่ใช้ generate_content text ไม่ได้
            skip_kw = ["tts", "embedding", "imagen", "vision",
                       "-image", "image-preview", "native-audio", "live-",
                       "computer-use", "aqa", "text-bison", "chat-bison"]
            if any(s in nl for s in skip_kw):
                continue
            if "gemini" not in nl:
                continue
            names.append(name)

        def sort_key(n):
            # Recommended order: Flash variants ก่อน (quota สูง) → Pro ท้าย (quota ต่ำ)
            # 3.1-flash-lite-preview = preferred default
            nl = n.lower()
            if "3.1-flash-lite" in nl: return (0, n)
            if "3.1-flash" in nl: return (1, n)
            if "3-flash" in nl: return (2, n)
            if "2.5-flash" in nl: return (3, n)
            if "2.0-flash" in nl: return (4, n)
            if "3.1-pro" in nl: return (5, n)
            if "3-pro" in nl: return (6, n)
            if "2.5-pro" in nl: return (7, n)
            if "1.5" in nl: return (8, n)
            return (9, n)

        return sorted(set(names), key=sort_key)
    except Exception:
        # fallback list ถ้า list_models fail — เรียงตาม recommend
        # 3.1-flash-lite-preview = default (verified accessible, output 65K, free tier RPD=500)
        # Pro variants ท้ายๆ — quota ต่ำ (50/day free tier)
        return [
            "gemini-3.1-flash-lite-preview",
            "gemini-3.1-flash-lite",
            "gemini-3-flash-preview",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-3.1-pro-preview",
            "gemini-2.5-pro",
            "gemini-2.0-flash-001",
        ]
