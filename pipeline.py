"""
pipeline.py - Multi-agent orchestrator with attachments + thorough mode
"""
import json
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, List, Dict

from agents import (
    PHASES, IMPL_PHASES, KICKOFF_PHASES,
    get_phases_for_mode, build_judge_prompt,
    CODER_INSTRUCTION, DEBUGGER_INSTRUCTION,
    CONTEXT_MAP, get_context_keys,
)

# Fix 2026-05-16 (Coddy #4 Day 2): ย้าย sessions ไปเก็บที่ user-profile (`~/.happy/sessions/`)
# เดิม Path("sessions") = relative ไป cwd → fragile (เปิด HAPPY จาก Start Menu/Desktop/shell
# cwd ต่างกัน → sessions ไปคนละที่). ตอนนี้รวมกับ auth.json ใน ~/.happy/ ที่เดียวกัน
SESSIONS_DIR = Path.home() / ".happy" / "sessions"


def _atomic_write_text(path: Path, content: str) -> None:
    """Atomic file write: tmp + fsync + os.replace.

    ENA Desktop v2.6.7 pattern — a crash/power-loss between open and
    close leaves either the OLD file intact OR the new file in place,
    never a half-written JSON that future reads would treat as corrupt
    (list_sessions silently drops sessions whose meta.json doesn't
    parse).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def create_session(task, model, settings):
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    session_path = SESSIONS_DIR / timestamp
    session_path.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(session_path / "00_task.txt", task)
    meta = {
        "task": task[:500],
        "model": model,
        "settings": settings,
        "mode": settings.get("mode", "quick"),
        "started_at": datetime.now().isoformat(),
        "status": "running",
        "phases_completed": [],
        "judge_rounds": 0,
        "has_attachments": False,
    }
    _atomic_write_text(
        session_path / "_meta.json",
        json.dumps(meta, ensure_ascii=False, indent=2),
    )
    return session_path


def update_meta(session_path, **updates):
    meta_file = session_path / "_meta.json"
    try:
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
    except Exception:
        meta = {}
    meta.update(updates)
    _atomic_write_text(
        meta_file, json.dumps(meta, ensure_ascii=False, indent=2)
    )


def save_phase_output(session_path, phase_index, phase_id, content):
    filename = f"{phase_index:02d}_{phase_id}.md"
    _atomic_write_text(session_path / filename, content)
    meta_file = session_path / "_meta.json"
    try:
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        if phase_id not in meta.get("phases_completed", []):
            meta.setdefault("phases_completed", []).append(phase_id)
            _atomic_write_text(
                meta_file,
                json.dumps(meta, ensure_ascii=False, indent=2),
            )
    except Exception:
        pass


# Retry mechanism — กัน Vertex AI server disconnect / 503 / timeout
MAX_RETRIES = 5  # Bug 21 fix (Coddy #5): bumped from 3 → 5 — Pro 3.1 demand spikes need more attempts
RETRY_DELAYS = [5, 15, 30, 60, 120]  # exponential-ish backoff (วินาที) — last attempt waits 2 min
# Bug 21: เพิ่ม delay สำหรับ capacity overload (503/UNAVAILABLE) — Google capacity spike มัก clear ใน 3-5 นาที
CAPACITY_DELAYS = [30, 120, 300, 300, 300]  # 30s → 2min → 5min → 5min → 5min
_TRANSIENT_PATTERNS = (
    "server disconnected",
    "503",
    "deadline",
    "timeout",
    "unavailable",
    "rate limit",
    "resource exhausted",
    "internal error",
    # Fix Bug 8: ถือว่า empty/blocked response เป็น transient ให้ retry
    "empty response",
    "blocked response",
    # Bug 21: explicit capacity overload markers
    "overloaded",
    "high demand",
)
# Subset ที่บ่งบอก capacity issue ชัดเจน → ใช้ CAPACITY_DELAYS (รอยาวกว่า)
_CAPACITY_PATTERNS = ("503", "unavailable", "overloaded", "high demand")


def _is_transient(err: Exception) -> bool:
    msg = str(err).lower()
    return any(p in msg for p in _TRANSIENT_PATTERNS)


def _is_capacity_overload(err: Exception) -> bool:
    """503/UNAVAILABLE/overloaded — Google capacity issue, ใช้ delay ยาวกว่า"""
    msg = str(err).lower()
    return any(p in msg for p in _CAPACITY_PATTERNS)


# Fix Bug 8: validate response — กัน silent skip ตอน Gemini ส่ง empty / blocked output
# finish_reason ที่ถือว่า "เสีย" → SAFETY/RECITATION/BLOCKLIST/PROHIBITED_CONTENT/SPII/OTHER/MALFORMED
# finish_reason "STOP" = ปกติ (output ครบแล้ว)
# finish_reason "MAX_TOKENS" = output ตัด — ถือว่า partial OK ถ้ามี text > 50 chars
_BAD_FINISH_REASONS = {
    "SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT",
    "SPII", "OTHER", "MALFORMED_FUNCTION_CALL", "LANGUAGE",
}
_MIN_USEFUL_OUTPUT_CHARS = 30   # ตำกว่านี้ = น่าสงสัย (แต่ db_admin "No database required..." = 35 chars ผ่านได้)


def _safe_text(response) -> str:
    """ดึง response.text แบบไม่ raise — return '' ถ้า None/ขาด candidates"""
    try:
        t = response.text
        return (t or "").strip()
    except Exception:
        return ""


def _validate_response(response, agent_label: str) -> str:
    """ตรวจสอบ response — ถ้า empty/blocked raise ให้ _call_with_retry จัดการ retry
    Fix Bug 8: HAPPY เคยรับ empty silently → save 0-byte file → user เห็นทีหลัง"""
    text = _safe_text(response)

    # Check finish_reason
    finish_reason_str = ""
    try:
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            fr = getattr(candidates[0], "finish_reason", None)
            if fr is not None:
                # FinishReason enum value or str
                finish_reason_str = str(fr).upper()
    except Exception:
        pass

    # block-class finish reasons → fail (will retry via _call_with_retry)
    if any(bad in finish_reason_str for bad in _BAD_FINISH_REASONS):
        raise RuntimeError(
            f"blocked response from {agent_label}: finish_reason={finish_reason_str}, "
            f"text_len={len(text)}"
        )

    # truly empty (after strip) → fail
    if not text:
        raise RuntimeError(
            f"empty response from {agent_label}: finish_reason={finish_reason_str or 'UNKNOWN'}"
        )

    # very short + STOP → might be legitimate (db_admin "No database required.") OR truncation
    # only fail if < MIN AND finish_reason isn't STOP — i.e. it ended weirdly
    if len(text) < _MIN_USEFUL_OUTPUT_CHARS:
        is_stop = "STOP" in finish_reason_str or not finish_reason_str
        if not is_stop:
            raise RuntimeError(
                f"empty response from {agent_label}: only {len(text)} chars, "
                f"finish_reason={finish_reason_str}"
            )

    return text


def _call_with_retry(fn, *args, **kwargs):
    """เรียก Gemini API พร้อม retry สำหรับ transient errors.
    Bug 21 fix (Coddy #5): แยก delay สำหรับ capacity overload (503) — ใช้ CAPACITY_DELAYS
    ที่ยาวกว่า เพราะ Google capacity spike clear ช้า (~3-5 นาที)"""
    last_err = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            last_err = e
            if attempt >= MAX_RETRIES or not _is_transient(e):
                raise
            # เลือก delay ตาม error type
            if _is_capacity_overload(e):
                delay = CAPACITY_DELAYS[min(attempt, len(CAPACITY_DELAYS) - 1)]
                _safe_log(f"[capacity-503] attempt {attempt+1}/{MAX_RETRIES}: "
                          f"Google overloaded, waiting {delay}s before retry — {str(e)[:120]}")
            else:
                delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                _safe_log(f"[transient] attempt {attempt+1}/{MAX_RETRIES}: "
                          f"retry in {delay}s — {str(e)[:120]}")
            time.sleep(delay)
    raise last_err


# Fix Bug 7: ตั้ง generation config ให้ output ยาวพอ + stable สำหรับ code
# - max_output_tokens=65536: max ของ Gemini 2.5/3.x (ทุกตัวยกเว้น 2.0-flash ซึ่ง 8192)
#   verified ผ่าน client.models.list() → output_token_limit field
# - temperature=0.4: สำหรับ code ค่าต่ำ → output stable + structured กว่า default ~1.0
def _gen_config():
    """สร้าง GenerateContentConfig สำหรับ code-quality output ใช้เต็ม budget"""
    try:
        from google.genai.types import GenerateContentConfig
        return GenerateContentConfig(
            max_output_tokens=65536,
            temperature=0.4,
            top_p=0.95,
            top_k=40,
        )
    except Exception:
        # fallback ถ้า SDK version ไม่รองรับ → return None (ใช้ default)
        return None


class _TPMTracker:
    """Adaptive throttling — rolling 60s window of tokens used.
    ก่อนทุก call เช็คว่า TPM ใกล้ ceiling หรือยัง — ถ้าใกล้ก็ sleep รอ window เลื่อน
    เพื่อกัน 429 (TPM hit).

    Thread-safety: pipeline worker thread calls `record` after each Gemini
    response; Running page (Tk main thread) calls `current_tpm` every
    500 ms for the live bar. Without a lock, the main-thread `for _, n
    in self._events` generator can hit "list changed size during
    iteration" if the worker happens to append at exactly the wrong tick.
    A short lock on every mutation + every read fixes it; contention is
    negligible (calls are ~10s apart).

    TPM ceiling is per-model (v2.4.5): PipelineRunner passes the
    user-selected model in, the tracker looks up the matching quota
    from core.quotas, and the throttle/back-off logic uses THAT
    number instead of a hard-coded 250 000 (which was right for
    flash-lite but wrong for pro tiers).
    """
    import threading as _threading
    SAFETY_THRESHOLD = 0.85  # ถ้า usage ใน 60s > 85% ของ ceiling → sleep

    def __init__(self, model: str = ""):
        # Resolve ceiling once at construction. If model is unknown
        # we fall back to DEFAULT_QUOTA which is conservative.
        try:
            from core.quotas import get_quota
            self.TPM_CEILING = get_quota(model).tpm
        except Exception:
            self.TPM_CEILING = 250_000
        self._events = []  # list[tuple(ts, total_tokens)]
        self._lock = self._threading.Lock()

    def _prune_locked(self):
        """Caller must hold self._lock."""
        now = time.time()
        self._events = [(t, n) for t, n in self._events if now - t < 60.0]

    def record(self, input_tokens: int, output_tokens: int):
        """เรียกหลัง response — บันทึก tokens ที่เพิ่งใช้"""
        with self._lock:
            self._prune_locked()
            self._events.append(
                (time.time(),
                 int(input_tokens or 0) + int(output_tokens or 0))
            )

    def current_tpm(self) -> int:
        with self._lock:
            self._prune_locked()
            return sum(n for _, n in self._events)

    def wait_if_needed(self, projected_input: int = 0, sleep_fn=time.sleep) -> int:
        """ก่อน call: ถ้าเพิ่ม projected_input จะเกิน safety threshold → sleep จน window เลื่อนพอ
        คืน seconds ที่ sleep ไป (สำหรับ logging)"""
        with self._lock:
            self._prune_locked()
            current = sum(n for _, n in self._events)
            oldest_ts = self._events[0][0] if self._events else None
        # ถ้า current + projected ยังต่ำกว่า safety, ผ่าน
        if current + projected_input < int(self.TPM_CEILING * self.SAFETY_THRESHOLD):
            return 0
        # ต้องรอ — sleep จนกว่า oldest event จะ "หลุดจาก 60s window"
        if oldest_ts is None:
            return 0
        wait_s = 60.0 - (time.time() - oldest_ts) + 0.5  # +0.5 buffer
        if wait_s > 0:
            sleep_fn(min(wait_s, 60.0))
            with self._lock:
                self._prune_locked()
            return int(wait_s)
        return 0


def _extract_usage(response, agent_label: str) -> dict:
    """Token usage tracking — read response.usage_metadata (no extra API call)
    Returns dict: {agent, input_tokens, output_tokens, total_tokens}"""
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        return {"agent": agent_label, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    return {
        "agent": agent_label,
        "input_tokens": int(getattr(usage, "prompt_token_count", 0) or 0),
        "output_tokens": int(getattr(usage, "candidates_token_count", 0) or 0),
        "total_tokens": int(getattr(usage, "total_token_count", 0) or 0),
    }


def _estimate_input_tokens(text: str) -> int:
    """Quick estimate ของ input tokens — ใช้ก่อน call (ก่อนรู้ตัวเลขจริง)
    Rule of thumb: ~4 chars/token สำหรับ English; ภาษาไทยใกล้เคียง"""
    return max(1, len(text) // 4)


def _safe_log(msg: str) -> None:
    """Print to stdout safely. Windows default stdio = cp1252 → unicode chars (≥, —, etc.)
    can raise UnicodeEncodeError when piped/redirected. Fallback to ASCII replace
    so the pipeline doesn't crash on a logging line."""
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode("ascii"), flush=True)
    except Exception:
        pass  # logging must NEVER bring down pipeline


# Nick's directive 2026-05-15 (จัดเต็ม): per-agent output-token floor.
# Below floor → call again with expand directive (max 2 retries).
# Mainstream agents target ~4K tokens output (~15K chars).
# Format-bound agents (Judge/Tester scorecards, devops "no-deploy" replies) have looser floors.
MIN_OUTPUT_TOKENS = {
    # Code-writing — long output required (target 4K+)
    "coder": 4000,
    "frontend": 4000,
    "debugger": 4000,
    # Documentation / analysis — long output expected
    "architect": 3000,
    "pm_kickoff": 3000,
    "summarizer": 3500,
    "brief_synth": 3000,
    # Kickoff phases — medium output
    "doc_analyst": 2000,
    "req_analyst": 2000,
    "arch_consult": 2000,
    "ux_lead": 2000,
    "data_lead": 2000,
    "security_lead": 2000,
    "pm_final": 2000,
    # Format-bound phases — short by design (light enforcement)
    "judge": 1000,
    "tester": 1200,
    "db_admin": 1500,
    "devops": 1500,
}


def _agent_id_from_label(label: str) -> str:
    """Extract base agent id from labels like 'tester(round 2)' or 'coder(revision 1)'"""
    return label.split("(")[0].strip()


def call_agent_text_with_min_length(client, model, instruction, input_text,
                                       agent_label: str, min_output_tokens: int = 0,
                                       token_log: list = None,
                                       tpm_tracker: "_TPMTracker" = None,
                                       max_retries: int = 2):
    """Wrapper: call_agent_text + retry if output below floor.
    Nick's "จัดเต็ม" directive — force AI to produce thorough output.
    Each retry feeds prior draft back with explicit "expand" directive."""
    text = call_agent_text(client, model, instruction, input_text,
                            agent_label=agent_label,
                            token_log=token_log, tpm_tracker=tpm_tracker)
    if min_output_tokens <= 0 or not token_log:
        return text

    last_tokens = token_log[-1].get("output_tokens", 0)
    for retry in range(1, max_retries + 1):
        if last_tokens >= min_output_tokens:
            return text
        # Build expansion input
        expand_input = (
            f"=== ORIGINAL INPUT ===\n{input_text}\n\n"
            f"=== YOUR PREVIOUS DRAFT (TOO SHORT: {last_tokens} tokens, need ≥{min_output_tokens}) ===\n"
            f"{text}\n\n"
            f"=== EXPANSION DIRECTIVE ===\n"
            f"Your previous draft is only {last_tokens} tokens. Required minimum: "
            f"{min_output_tokens} tokens. EXPAND SIGNIFICANTLY:\n"
            f"  • Add MORE edge cases (list explicitly + handling code/logic)\n"
            f"  • Add MORE examples + non-examples + counterexamples\n"
            f"  • Add deeper rationale per decision (WHY this choice, what alternatives, trade-offs)\n"
            f"  • Add test scenarios / acceptance criteria\n"
            f"  • For code: more inline comments, fuller docstrings, defensive checks\n"
            f"  • For docs: bulleted breakdowns, risks + mitigations, scaling considerations\n"
            f"KEEP all original content from your previous draft. ADD substantial detail. "
            f"Do NOT just restate — augment, deepen, exemplify."
        )
        _safe_log(f"[retry-length] {agent_label}: got {last_tokens}, need >={min_output_tokens} "
                   f"({retry}/{max_retries})")
        text = call_agent_text(client, model, instruction, expand_input,
                                agent_label=f"{agent_label}-expand{retry}",
                                token_log=token_log, tpm_tracker=tpm_tracker)
        last_tokens = token_log[-1].get("output_tokens", 0)
    return text


def call_agent_text(client, model, instruction, input_text, agent_label: str = "agent",
                     token_log: list = None, tpm_tracker: "_TPMTracker" = None):
    full_prompt = f"{instruction}\n\nInput:\n{input_text}"
    projected = _estimate_input_tokens(full_prompt)

    # Adaptive throttling: ก่อน call ถ้าใกล้ TPM ceiling → sleep รอ
    if tpm_tracker is not None:
        waited = tpm_tracker.wait_if_needed(projected)
        if waited > 0:
            _safe_log(f"[TPM throttle] sleep {waited}s before {agent_label} "
                       f"(window={tpm_tracker.current_tpm():,} + projected={projected:,})")

    def _do():
        cfg = _gen_config()
        kwargs = {"model": model, "contents": full_prompt}
        if cfg is not None:
            kwargs["config"] = cfg
        response = client.models.generate_content(**kwargs)
        text = _validate_response(response, agent_label)
        usage = _extract_usage(response, agent_label)
        if token_log is not None:
            token_log.append(usage)
        if tpm_tracker is not None:
            tpm_tracker.record(usage["input_tokens"], usage["output_tokens"])
        return text
    return _call_with_retry(_do)


def call_agent_multimodal(client, model, instruction, input_text, attachments,
                            agent_label: str = "agent", token_log: list = None,
                            tpm_tracker: "_TPMTracker" = None):
    from file_loader import build_gemini_parts
    prompt = f"{instruction}\n\nInput:\n{input_text}"
    parts = build_gemini_parts(prompt, attachments)
    projected = _estimate_input_tokens(prompt)
    if tpm_tracker is not None:
        waited = tpm_tracker.wait_if_needed(projected)
        if waited > 0:
            _safe_log(f"[TPM throttle] sleep {waited}s before {agent_label}")

    def _do():
        cfg = _gen_config()
        kwargs = {"model": model, "contents": parts}
        if cfg is not None:
            kwargs["config"] = cfg
        response = client.models.generate_content(**kwargs)
        text = _validate_response(response, agent_label)
        usage = _extract_usage(response, agent_label)
        if token_log is not None:
            token_log.append(usage)
        if tpm_tracker is not None:
            tpm_tracker.record(usage["input_tokens"], usage["output_tokens"])
        return text
    return _call_with_retry(_do)


# Fix Bug 9: ตรวจว่า extracted output ครบ — กัน "Coder ทำ game.js แต่ไม่มี index.html"
def _validate_project_completeness(session_path) -> None:
    """ตรวจว่าโค้ดที่ extract ออกมาเป็น runnable project — raise ถ้าขาด entry point.

    Rules:
      - JS files แต่ไม่มี HTML → web project ไม่มี entry → fail
      - ไม่มี .py และ ไม่มี .html → ไม่มี entry → fail
    """
    from extractor import extract_from_session
    files = extract_from_session(session_path)
    names = list(files.keys())
    if not names:
        raise RuntimeError("incomplete project: no code files extracted from session")

    def _has(ext): return any(n.lower().endswith(ext) for n in names)
    has_py_non_test = any(
        n.lower().endswith(".py")
        and not n.lower().startswith("test_")
        and not n.lower().endswith("_test.py")
        and n.lower() not in ("conftest.py", "tests.py")
        for n in names
    )
    has_html = _has(".html")
    has_js = _has(".js")
    has_py_total = _has(".py")

    if has_js and not has_html:
        raise RuntimeError(
            "incomplete project: has .js file(s) but no entry-point .html. "
            "Web projects must include index.html that loads the JS."
        )
    if not (has_py_total or has_html):
        raise RuntimeError(
            f"incomplete project: no .py or .html entry-point. Extracted files: {names}"
        )
    # If only test files (.py) without main → no real entry
    if has_py_total and not has_py_non_test and not has_html:
        raise RuntimeError(
            "incomplete project: only test_*.py files found — no main entry point."
        )


def parse_judge_score(output: str) -> int:
    """ดึง SCORE: X/100 ออกมาเป็น int. คืน -1 ถ้าไม่เจอ → treat as fail
    รองรับรูปแบบ: 'SCORE: 95/100', 'SCORE: 95', '**SCORE: 95/100**', etc."""
    import re
    cleaned = output.replace("**", "").replace("*", "")
    # หา pattern "SCORE: <num>" (case insensitive)
    m = re.search(r"SCORE\s*:\s*(\d{1,3})\b", cleaned, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass
    return -1


def parse_judge(output):
    """Fix Bug 10: คืน (score:int, instructions:str)
    pipeline เอา score มาเทียบ threshold เอง — ไม่เชื่อ 'DECISION: PASS' ของ Judge
    (Judge เคยบอก PASS ตอน score=95 ทั้งที่ threshold=100)"""
    score = parse_judge_score(output)
    instructions = ""
    if "INSTRUCTIONS_FOR_CODER:" in output:
        instructions = output.split("INSTRUCTIONS_FOR_CODER:", 1)[1].strip()
    elif "ISSUES FOUND:" in output:
        instructions = output.split("ISSUES FOUND:", 1)[1].strip()
    return score, instructions


def parse_tester_decision(output: str) -> tuple:
    """Fix Bug 13: Tester ใหม่ใช้ PLAYABLE/BROKEN — parse decision + instructions
    Returns: (playable: bool, instructions: str)"""
    import re
    cleaned = output.replace("**", "").replace("*", "")
    # หา DECISION line
    m = re.search(r"DECISION\s*:\s*(PLAYABLE|BROKEN)", cleaned, re.IGNORECASE)
    playable = bool(m and m.group(1).upper() == "PLAYABLE")

    instructions = ""
    if "INSTRUCTIONS_FOR_CODER:" in output:
        instructions = output.split("INSTRUCTIONS_FOR_CODER:", 1)[1].strip()
    elif "ISSUES_FOUND:" in output:
        instructions = output.split("ISSUES_FOUND:", 1)[1].strip()
    elif "ISSUES FOUND:" in output:
        instructions = output.split("ISSUES FOUND:", 1)[1].strip()
    return playable, instructions

class PipelineRunner:
    def __init__(self, client, model, delay=10, judge_threshold=85, max_judge_loops=5,
                 mode="quick", attachments=None,
                 on_phase_start=None, on_phase_complete=None,
                 on_phase_error=None, on_judge_round=None, should_stop=None):
        self.client = client
        self.model = model
        self.delay = delay
        self.judge_threshold = judge_threshold
        self.max_judge_loops = max_judge_loops
        self.mode = mode
        self.attachments = attachments or []
        self.on_phase_start = on_phase_start or (lambda *a, **k: None)
        self.on_phase_complete = on_phase_complete or (lambda *a, **k: None)
        self.on_phase_error = on_phase_error or (lambda *a, **k: None)
        self.on_judge_round = on_judge_round or (lambda *a, **k: None)
        self.should_stop = should_stop or (lambda: False)
        self.outputs = {}
        self.phase_index = 0
        # Token monitoring: ทุก call จะ append ที่นี่ — read โดย run() เพื่อ store ลง meta
        self.token_log = []
        # Adaptive TPM throttling: บันทึก rolling 60s window of token usage.
        # Pass the model name so the tracker picks the right TPM ceiling
        # (250K for flash-lite, 125K for pro-preview, 1M for 2.0-flash, …).
        self._tpm = _TPMTracker(model=model)
        # Estimated input tokens ของ last call (สำหรับ TPM projection ก่อน call ถัดไป)
        self._last_input_estimate = 0
    
    def _check_stop(self):
        return self.should_stop()

    def build_context(self, agent_id: str, task: str, extras: dict = None) -> str:
        """Nick's directive (2026-05-15): per-agent selective context with original task
        always prepended as ground truth.

        Reads CONTEXT_MAP from agents.py to know which prior outputs this agent needs.
        Special tokens: 'task' (skip — already prepended), 'ALL', 'ALL_KICKOFF', 'final_code'.

        extras: optional {label: content} pairs appended at the end (e.g., 'current_code',
                'judge_instructions' for revision calls).
        """
        parts = [f"=== ORIGINAL USER TASK (ground truth) ===\n{task}"]
        needs = get_context_keys(agent_id)
        kickoff_ids = [p["id"] for p in KICKOFF_PHASES]
        added = set()  # กัน duplicate ถ้า "ALL"/"ALL_KICKOFF" overlap กับ explicit ids

        for key in needs:
            if key == "task":
                continue
            elif key == "ALL":
                for prev_id, prev_out in self.outputs.items():
                    if prev_id in added or not isinstance(prev_out, str):
                        continue
                    parts.append(f"=== {prev_id.upper()} ===\n{prev_out}")
                    added.add(prev_id)
            elif key == "ALL_KICKOFF":
                for kid in kickoff_ids:
                    if kid in added or kid not in self.outputs:
                        continue
                    parts.append(f"=== {kid.upper()} (kickoff) ===\n{self.outputs[kid]}")
                    added.add(kid)
            elif key == "final_code":
                if "final_code" not in added and "final_code" in self.outputs:
                    parts.append(f"=== FINAL_CODE ===\n{self.outputs['final_code']}")
                    added.add("final_code")
            elif key in self.outputs and key not in added:
                parts.append(f"=== {key.upper()} ===\n{self.outputs[key]}")
                added.add(key)

        if extras:
            for label, content in extras.items():
                if content:
                    parts.append(f"=== {label.upper().replace('_', ' ')} ===\n{content}")

        full = "\n\n---\n\n".join(parts)
        # Log context summary so user can verify Selective Context is active
        _safe_log(f"[context] {agent_id}: {len(needs)} key(s), {len(added)} resolved, "
                   f"{len(full):,} chars")
        return full
    
    def _delay(self):
        if self.delay > 0:
            time.sleep(self.delay)
    
    def _call(self, instruction, input_text, use_attachments=False, agent_label="agent"):
        # Nick's directive 2026-05-15 (จัดเต็ม): retry if output < per-agent min floor
        agent_id = _agent_id_from_label(agent_label)
        min_tokens = MIN_OUTPUT_TOKENS.get(agent_id, 0)
        if use_attachments and self.attachments:
            # multimodal path — uses single-call (no retry yet — multimodal less common)
            return call_agent_multimodal(
                self.client, self.model, instruction, input_text, self.attachments,
                agent_label=agent_label, token_log=self.token_log,
                tpm_tracker=self._tpm,
            )
        return call_agent_text_with_min_length(
            self.client, self.model, instruction, input_text,
            agent_label=agent_label,
            min_output_tokens=min_tokens,
            token_log=self.token_log,
            tpm_tracker=self._tpm,
        )

    def _run_phase_generic(self, phase, input_text, session_path, use_attachments=False):
        pid = phase["id"]
        name = phase["name"]
        instr = phase["instruction"]
        try:
            self.on_phase_start(pid, name, self.phase_index)
            output = self._call(instr, input_text, use_attachments=use_attachments,
                                 agent_label=f"{pid}({name})")
            self.outputs[pid] = output
            save_phase_output(session_path, self.phase_index + 1, pid, output)
            self.on_phase_complete(pid, name, self.phase_index, output)
            self.phase_index += 1
            self._delay()
        except Exception as e:
            err = str(e)[:300]
            self.outputs[pid] = f"[ERROR] {err}"
            self.on_phase_error(pid, name, err)
            try:
                # Fix P2.9 (Coddy #5 2026-05-16): ใช้ with block — กัน file handle leak บน Windows
                with (session_path / "errors.log").open("a", encoding="utf-8") as _ef:
                    _ef.write(f"[{datetime.now().isoformat()}] {pid}: {err}\n")
            except Exception:
                pass
            raise
    
    def _run_kickoff_meeting(self, task, session_path):
        # Nick's directive: every phase uses build_context() with CONTEXT_MAP — original
        # task always prepended; only the agents listed in CONTEXT_MAP get added.
        kickoff_id_to_phase = {p["id"]: p for p in KICKOFF_PHASES}

        # 1. Document Analyst (has file attachments)
        if self._check_stop(): return ""
        doc_ctx = self.build_context(
            "doc_analyst", task,
            extras={"attachments_note": "(Files attached - analyze them)" if self.attachments else "No files attached."},
        )
        self._run_phase_generic(kickoff_id_to_phase["doc_analyst"], doc_ctx,
                                  session_path, use_attachments=True)

        # 2-6. req_analyst, arch_consult, ux_lead, data_lead, security_lead
        for kid in ("req_analyst", "arch_consult", "ux_lead", "data_lead", "security_lead"):
            if self._check_stop(): return ""
            ctx = self.build_context(kid, task)
            self._run_phase_generic(kickoff_id_to_phase[kid], ctx, session_path)

        # 7. Brief Synthesizer — gets ALL_KICKOFF via map
        if self._check_stop(): return ""
        synth_ctx = self.build_context("brief_synth", task,
                                         extras={"meeting_end": "Synthesize the final Project Brief."})
        self._run_phase_generic(kickoff_id_to_phase["brief_synth"], synth_ctx, session_path)

        return self.outputs["brief_synth"]
    def _run_judge_loop(self, task, code, session_path):
        judge_instruction = build_judge_prompt(self.judge_threshold)
        current_code = code
        
        for round_num in range(1, self.max_judge_loops + 1):
            if self._check_stop():
                return current_code
            
            self.on_phase_start("judge", f"Judge (round {round_num})", self.phase_index)
            try:
                judge_output = call_agent_text_with_min_length(
                    self.client, self.model, judge_instruction,
                    self.build_context("judge", task,
                                        extras={"code_to_judge": current_code,
                                                "round": str(round_num)}),
                    agent_label=f"judge(round {round_num})",
                    min_output_tokens=MIN_OUTPUT_TOKENS.get("judge", 0),
                    token_log=self.token_log,
                    tpm_tracker=self._tpm,
                )
            except Exception as e:
                self.on_phase_error("judge", f"Judge (round {round_num})", str(e)[:200])
                # v2.4.6 fix: re-raise so the outer worker terminates
                # the pipeline. Previously this silently returned,
                # which made the caller continue to DevOps/Summarizer/
                # PM Final on un-scored code — user saw "Judge: error"
                # but DevOps still showed "done". Quality gate must
                # actually gate.
                raise

            (session_path / f"{self.phase_index+1:02d}_judge_round{round_num}.md").write_text(
                judge_output, encoding="utf-8"
            )

            # Fix Bug 10: ใช้ score เทียบ threshold ตรงๆ — ไม่เชื่อ "DECISION: PASS" ของ Judge
            score, instructions = parse_judge(judge_output)
            passed = score >= self.judge_threshold
            decision = "PASS" if passed else "REVISE"
            score_display = str(score) if score >= 0 else "?"

            # Fix Bug 14: emit on_phase_complete หลัง judge call สำเร็จ — กัน pill ค้าง 🔄
            self.on_phase_complete(
                "judge", f"Judge (round {round_num}) {decision} {score_display}/100",
                self.phase_index, judge_output,
            )
            self.on_judge_round(round_num, decision, score_display)
            update_meta(session_path, judge_rounds=round_num)
            self._delay()

            if passed:
                self.outputs["judge"] = judge_output
                save_phase_output(session_path, self.phase_index + 1, "judge", judge_output)
                self.phase_index += 1
                return current_code

            if round_num == self.max_judge_loops:
                self.outputs["judge"] = judge_output
                save_phase_output(session_path, self.phase_index + 1, "judge", judge_output)
                self.phase_index += 1
                return current_code

            # revise — score < threshold → ส่งกลับให้ Coder/Debugger แก้
            # Fix P2.7 (Coddy #5 2026-05-16): track _last_phase เพื่อให้ on_phase_error ระบุ phase ถูกต้อง
            # Regression of Bug 14 — Debugger call (line ~743) ก็ throw ได้ แต่ except เดิมส่ง "coder" เสมอ
            _last_phase = "coder"
            _last_phase_label = f"Coder (revision {round_num})"
            self.on_phase_start("coder", _last_phase_label, self.phase_index)
            try:
                revised = call_agent_text_with_min_length(
                    self.client, self.model, CODER_INSTRUCTION,
                    self.build_context("coder", task, extras={
                        "current_code": current_code,
                        "judge_score": f"{score}/{self.judge_threshold}",
                        "judge_instructions": instructions,
                    }),
                    agent_label=f"coder(revision {round_num})",
                    min_output_tokens=MIN_OUTPUT_TOKENS.get("coder", 0),
                    token_log=self.token_log,
                    tpm_tracker=self._tpm,
                )
                # update self.outputs["coder"] เพื่อ downstream context build (Debugger, summarizer) เห็นเวอร์ชันล่าสุด
                self.outputs["coder"] = revised
                # Fix Bug 14: emit on_phase_complete หลัง Coder revision — กัน pill ค้าง 🔄
                self.on_phase_complete(
                    "coder", f"Coder (rev {round_num} done)", self.phase_index, revised,
                )
                self._delay()
                _last_phase = "debugger"
                _last_phase_label = f"Debugger (re-check {round_num})"
                self.on_phase_start("debugger", _last_phase_label, self.phase_index)
                current_code = call_agent_text_with_min_length(
                    self.client, self.model, DEBUGGER_INSTRUCTION,
                    self.build_context("debugger", task, extras={
                        "revised_code": revised,
                        "directive": f"Round {round_num}: review the revised code above. Output complete corrected code with `### File: name.ext` headings.",
                    }),
                    agent_label=f"debugger(revision {round_num})",
                    min_output_tokens=MIN_OUTPUT_TOKENS.get("debugger", 0),
                    token_log=self.token_log,
                    tpm_tracker=self._tpm,
                )
                # Fix Bug 14: emit on_phase_complete หลัง Debugger revision — กัน pill ค้าง 🔄
                self.on_phase_complete(
                    "debugger", f"Debugger (rev {round_num} done)", self.phase_index, current_code,
                )
                self.outputs["debugger_revised"] = current_code
                rev_filename = f"06b_debugger_revision_{round_num}.md"
                (session_path / rev_filename).write_text(current_code, encoding="utf-8")
                self._delay()
            except Exception as e:
                # Fix P2.7: ใช้ _last_phase/_last_phase_label ที่ track ไว้ — ไม่ใช่ hardcode "coder"
                self.on_phase_error(_last_phase, _last_phase_label, str(e)[:200])
                # v2.4.6 fix: re-raise. A failed Coder revision OR
                # Debugger re-check inside the Judge loop means we
                # can't produce the next code candidate — continuing
                # to DevOps would deploy whatever stale code remains,
                # which is exactly the "ข้ามขั้นตอน" Nick caught.
                raise

        return current_code

    def _run_tester_loop(self, task, _unused, session_path, tester_phase):
        """Bug 13: Tester gate ก่อน Debugger+Judge — เช็คว่าโปรแกรมรันได้จริง
        ถ้า BROKEN → ส่งกลับ Coder revise → re-run Tester (max self.max_judge_loops รอบ).
        Nick's directive: ใช้ build_context (CONTEXT_MAP['tester'] = task+coder+frontend+req+arch).
        Coder revision updates self.outputs['coder'] เพื่อ downstream context พบเวอร์ชันล่าสุด."""
        for round_num in range(1, self.max_judge_loops + 1):
            if self._check_stop(): return self.outputs.get("coder", "")

            label = f"Tester (round {round_num})" if round_num > 1 else "Tester"
            self.on_phase_start("tester", label, self.phase_index)
            try:
                tester_output = call_agent_text_with_min_length(
                    self.client, self.model, tester_phase["instruction"],
                    self.build_context("tester", task,
                                        extras={"round": str(round_num)}),
                    agent_label=f"tester(round {round_num})",
                    min_output_tokens=MIN_OUTPUT_TOKENS.get("tester", 0),
                    token_log=self.token_log,
                    tpm_tracker=self._tpm,
                )
            except Exception as e:
                self.on_phase_error("tester", label, str(e)[:200])
                # v2.4.6 fix: re-raise instead of silently continuing
                # to Debugger+Judge+DevOps on un-tested code.
                raise

            self.outputs["tester"] = tester_output
            # ไฟล์ round 1 = main; รอบถัดไป save แยก (debug history)
            if round_num == 1:
                save_phase_output(session_path, self.phase_index + 1, "tester", tester_output)
            else:
                (session_path / f"{self.phase_index+1:02d}_tester_round{round_num}.md").write_text(
                    tester_output, encoding="utf-8")

            playable, instructions = parse_tester_decision(tester_output)
            self.on_phase_complete("tester", label, self.phase_index, tester_output)
            self._delay()

            if playable:
                self.phase_index += 1
                return self.outputs.get("coder", "")

            if round_num == self.max_judge_loops:
                update_meta(session_path, tester_warning=f"After {round_num} rounds, Tester says BROKEN")
                self.phase_index += 1
                return self.outputs.get("coder", "")

            # BROKEN → revise via Coder (no Debugger here — Debugger runs after tester loop)
            if self._check_stop(): return self.outputs.get("coder", "")
            self.on_phase_start("coder", f"Coder (tester-rev {round_num})", self.phase_index)
            try:
                revised = call_agent_text_with_min_length(
                    self.client, self.model, CODER_INSTRUCTION,
                    self.build_context("coder", task, extras={
                        "current_coder_output": self.outputs.get("coder", ""),
                        "current_frontend_output": self.outputs.get("frontend", ""),
                        "tester_decision": "BROKEN",
                        "tester_instructions": instructions,
                    }),
                    agent_label=f"coder(tester-rev {round_num})",
                    min_output_tokens=MIN_OUTPUT_TOKENS.get("coder", 0),
                    token_log=self.token_log,
                    tpm_tracker=self._tpm,
                )
                # update self.outputs["coder"] — Tester รอบถัดไป จะได้ context ล่าสุดผ่าน build_context
                self.outputs["coder"] = revised
                # Fix Bug 14: emit on_phase_complete หลัง Coder tester-revision — กัน pill ค้าง 🔄
                self.on_phase_complete(
                    "coder", f"Coder (tester-rev {round_num} done)", self.phase_index, revised,
                )
                (session_path / f"04b_coder_tester_revision_{round_num}.md").write_text(
                    revised, encoding="utf-8")
                self._delay()
            except Exception as e:
                self.on_phase_error("coder", f"Coder tester-rev {round_num}", str(e)[:200])
                # v2.4.6 fix: re-raise so the outer worker can mark
                # the run as failed instead of letting Debugger+Judge+
                # downstream run on an un-revised Coder output.
                raise

        return self.outputs.get("coder", "")

    def run(self, task, session_path):
        self.phase_index = 0
        # Fix Bug 13: lookup phases by id (เลิก IMPL_PHASES[N] index-based ที่เปราะ
        # เวลา reorder — Tester ถูกย้ายขึ้นมาก่อน Debugger+Judge)
        phases_by_id = {p["id"]: p for p in IMPL_PHASES}

        if self.mode == "thorough":
            brief = self._run_kickoff_meeting(task, session_path)
            effective_task = f"Project Brief from Kickoff Meeting:\n\n{brief}\n\n---\n\nOriginal user request:\n{task}"
        else:
            effective_task = task

        # Nick's directive: every phase uses build_context() — original task always prepended,
        # selective per CONTEXT_MAP. ลบ truncation [:1500] ออกหมด — Summarizer ได้ของเต็ม
        # 1. PM Kickoff
        if self._check_stop(): return self.outputs
        self._run_phase_generic(phases_by_id["pm_kickoff"],
            self.build_context("pm_kickoff", effective_task), session_path)

        # 2. Architect
        if self._check_stop(): return self.outputs
        self._run_phase_generic(phases_by_id["architect"],
            self.build_context("architect", effective_task), session_path)

        # 3. DB Admin
        if self._check_stop(): return self.outputs
        self._run_phase_generic(phases_by_id["db_admin"],
            self.build_context("db_admin", effective_task), session_path)

        # 4. Coder — pass 1 (initial draft)
        if self._check_stop(): return self.outputs
        self._run_phase_generic(phases_by_id["coder"],
            self.build_context("coder", effective_task,
                                extras={"directive": "PASS 1 (initial draft): produce complete backend code with `### File: name.ext` headings."}),
            session_path)

        # Coder — pass 2 (critique + expand) — Nick's "จัดเต็ม" directive 2026-05-15
        # ทำให้ Coder review งานตัวเองและขยาย (ไม่รอจน Tester/Judge ค่อย flag)
        if self._check_stop(): return self.outputs
        draft1 = self.outputs["coder"]
        (session_path / "04a_coder_pass1.md").write_text(draft1, encoding="utf-8")
        self.on_phase_start("coder", "Coder (pass 2 — critique+expand)", self.phase_index)
        try:
            improved = call_agent_text_with_min_length(
                self.client, self.model, CODER_INSTRUCTION,
                self.build_context("coder", effective_task, extras={
                    "pass1_draft": draft1,
                    "directive": ("PASS 2: review your pass-1 draft above. Identify weaknesses: "
                                  "missing edge cases, weak error handling, sparse comments, "
                                  "thin tests, scope gaps. Produce the FULL improved version "
                                  "(every file, complete). Do not just diff — output complete files. "
                                  "Use `### File: name.ext` headings."),
                }),
                agent_label="coder(pass 2)",
                min_output_tokens=MIN_OUTPUT_TOKENS.get("coder", 0),
                token_log=self.token_log,
                tpm_tracker=self._tpm,
            )
            self.outputs["coder"] = improved
            save_phase_output(session_path, self.phase_index, "coder", improved)
            self.on_phase_complete("coder", "Coder (pass 2 done)", self.phase_index, improved)
            self._delay()
        except Exception as e:
            # INTENTIONAL silent fallback (not the v2.4.6 bug pattern).
            # Pass 2 is a "critique + expand" enhancement on top of a
            # complete Pass 1 draft. If the enhancement call fails,
            # self.outputs["coder"] still holds the valid Pass 1 draft
            # (the `= improved` assignment is inside the try, so it
            # never ran on failure). Downstream phases continue safely
            # with the Pass 1 candidate. Re-raising here would kill an
            # otherwise-successful run just because the polish step
            # transient-erred — the opposite of what Nick wants.
            self.on_phase_error("coder", "Coder pass 2", str(e)[:200])

        # 5. Frontend
        if self._check_stop(): return self.outputs
        self._run_phase_generic(phases_by_id["frontend"],
            self.build_context("frontend", effective_task,
                                extras={"directive": "Produce complete frontend code with `### File: name.ext` headings. All `<script src>`/`<link href>` must reference files YOU produce."}),
            session_path)

        # 6. TESTER (Bug 13 — functional gate, loops if BROKEN)
        if self._check_stop(): return self.outputs
        approved_code = self._run_tester_loop(effective_task, None, session_path, phases_by_id["tester"])

        # 7. Debugger
        if self._check_stop(): return self.outputs
        self._run_phase_generic(phases_by_id["debugger"],
            self.build_context("debugger", effective_task,
                                extras={"approved_code": approved_code,
                                        "directive": "Review ALL above. Produce the COMPLETE corrected code (every file, with `### File: name.ext` headings)."}),
            session_path)

        # 8. Judge loop
        if self._check_stop(): return self.outputs
        self._run_judge_loop(effective_task, self.outputs["debugger"], session_path)
        final_code = self.outputs.get("debugger_revised", self.outputs["debugger"])
        self.outputs["final_code"] = final_code

        # Fix Bug 9: completeness check (soft warning ใน meta)
        try:
            _validate_project_completeness(session_path)
        except RuntimeError as e:
            update_meta(session_path, completeness_warning=str(e)[:300])
            self.outputs["_completeness_warning"] = str(e)

        # 9. DevOps — uses final_code via CONTEXT_MAP
        if self._check_stop(): return self.outputs
        self._run_phase_generic(phases_by_id["devops"],
            self.build_context("devops", effective_task), session_path)

        # 10. Summarizer — CONTEXT_MAP says "ALL" → ทุก output เต็ม ไม่ truncate
        if self._check_stop(): return self.outputs
        self._run_phase_generic(phases_by_id["summarizer"],
            self.build_context("summarizer", effective_task), session_path)

        # 11. PM Final
        if self._check_stop(): return self.outputs
        self._run_phase_generic(phases_by_id["pm_final"],
            self.build_context("pm_final", effective_task), session_path)

        # Token monitoring: summarize + persist to meta
        if self.token_log:
            inputs = [t["input_tokens"] for t in self.token_log]
            outputs_tok = [t["output_tokens"] for t in self.token_log]
            stats = {
                "total_input_tokens": sum(inputs),
                "total_output_tokens": sum(outputs_tok),
                "peak_input_tokens": max(inputs) if inputs else 0,
                "avg_input_tokens": int(sum(inputs) / len(inputs)) if inputs else 0,
                "calls": len(self.token_log),
                "per_call": self.token_log,
            }
            update_meta(session_path, token_stats=stats)

        update_meta(session_path, status="completed", completed_at=datetime.now().isoformat())
        return self.outputs

def list_sessions():
    if not SESSIONS_DIR.exists():
        return []
    sessions = []
    for path in sorted(SESSIONS_DIR.iterdir(), reverse=True):
        if not path.is_dir():
            continue
        meta_file = path / "_meta.json"
        if not meta_file.exists():
            continue
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            sessions.append({
                "path": path,
                "name": path.name,
                "task_preview": meta.get("task", "")[:60],
                "status": meta.get("status", "unknown"),
                "started_at": meta.get("started_at", ""),
                "phases_completed": len(meta.get("phases_completed", [])),
                "mode": meta.get("mode", "quick"),
                "has_attachments": meta.get("has_attachments", False),
            })
        except Exception:
            continue
    return sessions


def load_session(session_path):
    meta_file = session_path / "_meta.json"
    meta = {}
    if meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    outputs = {}
    for f in sorted(session_path.iterdir()):
        if f.suffix == ".md":
            stem = f.stem
            parts = stem.split("_", 1)
            if len(parts) == 2:
                phase_id = parts[1]
                outputs[phase_id] = f.read_text(encoding="utf-8")
    return {"meta": meta, "outputs": outputs, "path": session_path}


def delete_session(session_path):
    import shutil
    if session_path.exists() and session_path.is_dir():
        shutil.rmtree(session_path)


def build_combined_txt(session_path):
    task = (session_path / "00_task.txt").read_text(encoding="utf-8") if (session_path / "00_task.txt").exists() else ""
    lines = [f"TASK:\n{task}\n\n"]
    section_map = {
        "doc_analyst": "DOCUMENT ANALYST",
        "req_analyst": "REQUIREMENTS ANALYST",
        "arch_consult": "ARCHITECT CONSULT",
        "ux_lead": "UX LEAD",
        "data_lead": "DATA LEAD",
        "security_lead": "SECURITY LEAD",
        "brief_synth": "PROJECT BRIEF",
        "pm_kickoff": "PM KICKOFF",
        "architect": "ARCHITECT",
        "db_admin": "DB ADMIN",
        "coder": "BACKEND CODE",
        "frontend": "FRONTEND CODE",
        "debugger": "DEBUGGER (FINAL CODE)",
        "judge": "JUDGE",
        "tester": "TESTS",
        "devops": "DEVOPS",
        "summarizer": "SUMMARY",
        "pm_final": "PM FINAL",
    }
    for f in sorted(session_path.iterdir()):
        if f.suffix != ".md":
            continue
        stem = f.stem
        parts = stem.split("_", 1)
        if len(parts) != 2:
            continue
        phase_id = parts[1]
        header = section_map.get(phase_id, phase_id.upper())
        content = f.read_text(encoding="utf-8")
        lines.append(f"{header}:\n{content}\n\n")
    return "".join(lines)