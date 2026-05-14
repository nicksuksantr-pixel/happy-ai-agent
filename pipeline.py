"""
pipeline.py - Multi-agent orchestrator with attachments + thorough mode
"""
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, List, Dict

from agents import (
    PHASES, IMPL_PHASES, KICKOFF_PHASES,
    get_phases_for_mode, build_judge_prompt,
    CODER_INSTRUCTION, DEBUGGER_INSTRUCTION,
)

SESSIONS_DIR = Path("sessions")


def create_session(task, model, settings):
    SESSIONS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    session_path = SESSIONS_DIR / timestamp
    session_path.mkdir(parents=True, exist_ok=True)
    (session_path / "00_task.txt").write_text(task, encoding="utf-8")
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
    (session_path / "_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return session_path


def update_meta(session_path, **updates):
    meta_file = session_path / "_meta.json"
    try:
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
    except Exception:
        meta = {}
    meta.update(updates)
    meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def save_phase_output(session_path, phase_index, phase_id, content):
    filename = f"{phase_index:02d}_{phase_id}.md"
    (session_path / filename).write_text(content, encoding="utf-8")
    meta_file = session_path / "_meta.json"
    try:
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        if phase_id not in meta.get("phases_completed", []):
            meta.setdefault("phases_completed", []).append(phase_id)
            meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


# Retry mechanism — กัน Vertex AI server disconnect / 503 / timeout
MAX_RETRIES = 3
RETRY_DELAYS = [5, 15, 30]  # exponential-ish backoff (วินาที)
_TRANSIENT_PATTERNS = (
    "server disconnected",
    "503",
    "deadline",
    "timeout",
    "unavailable",
    "rate limit",
    "resource exhausted",
    "internal error",
)


def _is_transient(err: Exception) -> bool:
    msg = str(err).lower()
    return any(p in msg for p in _TRANSIENT_PATTERNS)


def _call_with_retry(fn, *args, **kwargs):
    """เรียก Vertex AI API พร้อม retry สำหรับ transient errors"""
    last_err = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            last_err = e
            if attempt >= MAX_RETRIES or not _is_transient(e):
                raise
            delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
            time.sleep(delay)
    raise last_err


def call_agent_text(client, model, instruction, input_text):
    def _do():
        response = client.models.generate_content(
            model=model,
            contents=f"{instruction}\n\nInput:\n{input_text}"
        )
        return response.text
    return _call_with_retry(_do)


def call_agent_multimodal(client, model, instruction, input_text, attachments):
    from file_loader import build_gemini_parts
    prompt = f"{instruction}\n\nInput:\n{input_text}"
    parts = build_gemini_parts(prompt, attachments)
    def _do():
        response = client.models.generate_content(model=model, contents=parts)
        return response.text
    return _call_with_retry(_do)


def parse_judge(output):
    output_clean = output.replace("**", "").replace("*", "")
    if "DECISION: PASS" in output_clean.upper():
        return "PASS", None
    instructions = ""
    if "INSTRUCTIONS_FOR_CODER:" in output:
        instructions = output.split("INSTRUCTIONS_FOR_CODER:", 1)[1].strip()
    elif "ISSUES FOUND:" in output:
        instructions = output.split("ISSUES FOUND:", 1)[1].strip()
    return "REVISE", instructions

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
    
    def _check_stop(self):
        return self.should_stop()
    
    def _delay(self):
        if self.delay > 0:
            time.sleep(self.delay)
    
    def _call(self, instruction, input_text, use_attachments=False):
        if use_attachments and self.attachments:
            return call_agent_multimodal(
                self.client, self.model, instruction, input_text, self.attachments
            )
        return call_agent_text(self.client, self.model, instruction, input_text)
    
    def _run_phase_generic(self, phase, input_text, session_path, use_attachments=False):
        pid = phase["id"]
        name = phase["name"]
        instr = phase["instruction"]
        try:
            self.on_phase_start(pid, name, self.phase_index)
            output = self._call(instr, input_text, use_attachments=use_attachments)
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
                (session_path / "errors.log").open("a", encoding="utf-8").write(
                    f"[{datetime.now().isoformat()}] {pid}: {err}\n"
                )
            except Exception:
                pass
            raise
    
    def _run_kickoff_meeting(self, task, session_path):
        # 1. Document Analyst
        if self._check_stop(): return ""
        doc_input = f"User task:\n{task}\n\n" + ("(Files attached - analyze them)" if self.attachments else "No files attached.")
        self._run_phase_generic(KICKOFF_PHASES[0], doc_input, session_path, use_attachments=True)
        
        # 2. Requirements Analyst
        if self._check_stop(): return ""
        req_input = f"User Task:\n{task}\n\nDocument Analyst Report:\n{self.outputs['doc_analyst']}"
        self._run_phase_generic(KICKOFF_PHASES[1], req_input, session_path)
        
        # Common input for phases 3-6
        common_input = (
            f"User Task:\n{task}\n\n"
            f"Document Analyst Report:\n{self.outputs['doc_analyst']}\n\n"
            f"Requirements Analyst:\n{self.outputs['req_analyst']}"
        )
        
        # 3. Architect Consultant
        if self._check_stop(): return ""
        self._run_phase_generic(KICKOFF_PHASES[2], common_input, session_path)
        
        # 4. UX Lead
        if self._check_stop(): return ""
        self._run_phase_generic(KICKOFF_PHASES[3], common_input, session_path)
        
        # 5. Data Lead
        if self._check_stop(): return ""
        self._run_phase_generic(KICKOFF_PHASES[4], common_input, session_path)
        
        # 6. Security Lead
        if self._check_stop(): return ""
        self._run_phase_generic(KICKOFF_PHASES[5], common_input, session_path)
        
        # 7. Brief Synthesizer
        if self._check_stop(): return ""
        synth_input = (
            f"User Task:\n{task}\n\n"
            f"=== KICKOFF MEETING INPUT ===\n\n"
            f"[Document Analyst]\n{self.outputs['doc_analyst']}\n\n"
            f"[Requirements Analyst]\n{self.outputs['req_analyst']}\n\n"
            f"[Architect Consultant]\n{self.outputs['arch_consult']}\n\n"
            f"[UX Lead]\n{self.outputs['ux_lead']}\n\n"
            f"[Data Lead]\n{self.outputs['data_lead']}\n\n"
            f"[Security Lead]\n{self.outputs['security_lead']}\n\n"
            f"=== END MEETING ===\n\nSynthesize the final Project Brief."
        )
        self._run_phase_generic(KICKOFF_PHASES[6], synth_input, session_path)
        
        return self.outputs["brief_synth"]
    def _run_judge_loop(self, task, code, session_path):
        judge_instruction = build_judge_prompt(self.judge_threshold)
        current_code = code
        
        for round_num in range(1, self.max_judge_loops + 1):
            if self._check_stop():
                return current_code
            
            self.on_phase_start("judge", f"Judge (round {round_num})", self.phase_index)
            try:
                judge_output = call_agent_text(
                    self.client, self.model, judge_instruction,
                    f"Original Task:\n{task}\n\nCode:\n{current_code}"
                )
            except Exception as e:
                self.on_phase_error("judge", f"Judge (round {round_num})", str(e)[:200])
                return current_code
            
            (session_path / f"{self.phase_index+1:02d}_judge_round{round_num}.md").write_text(
                judge_output, encoding="utf-8"
            )
            
            decision, instructions = parse_judge(judge_output)
            score = "?"
            for line in judge_output.splitlines():
                if "SCORE:" in line.upper():
                    score = line.split(":", 1)[1].strip().split("/")[0].strip()
                    break
            
            self.on_judge_round(round_num, decision, score)
            update_meta(session_path, judge_rounds=round_num)
            self._delay()
            
            if decision == "PASS":
                self.outputs["judge"] = judge_output
                save_phase_output(session_path, self.phase_index + 1, "judge", judge_output)
                self.phase_index += 1
                return current_code
            
            if round_num == self.max_judge_loops:
                self.outputs["judge"] = judge_output
                save_phase_output(session_path, self.phase_index + 1, "judge", judge_output)
                self.phase_index += 1
                return current_code
            
            # revise
            self.on_phase_start("coder", f"Coder (revision {round_num})", self.phase_index)
            try:
                revised = call_agent_text(
                    self.client, self.model, CODER_INSTRUCTION,
                    f"Current Code:\n{current_code}\n\nJudge Instructions:\n{instructions}"
                )
                self._delay()
                self.on_phase_start("debugger", f"Debugger (re-check {round_num})", self.phase_index)
                current_code = call_agent_text(
                    self.client, self.model, DEBUGGER_INSTRUCTION, revised
                )
                self.outputs["debugger_revised"] = current_code
                rev_filename = f"06b_debugger_revision_{round_num}.md"
                (session_path / rev_filename).write_text(current_code, encoding="utf-8")
                self._delay()
            except Exception as e:
                self.on_phase_error("coder", "Coder (revision)", str(e)[:200])
                return current_code
        
        return current_code
    
    def run(self, task, session_path):
        self.phase_index = 0
        
        if self.mode == "thorough":
            brief = self._run_kickoff_meeting(task, session_path)
            effective_task = f"Project Brief from Kickoff Meeting:\n\n{brief}\n\n---\n\nOriginal user request:\n{task}"
        else:
            effective_task = task
        
        # Implementation phases
        if self._check_stop(): return self.outputs
        self._run_phase_generic(IMPL_PHASES[0], effective_task, session_path)
        
        if self._check_stop(): return self.outputs
        self._run_phase_generic(IMPL_PHASES[1],
            f"Project Brief:\n{self.outputs['pm_kickoff']}\n\nUser Requirement:\n{effective_task}",
            session_path)
        
        if self._check_stop(): return self.outputs
        self._run_phase_generic(IMPL_PHASES[2],
            f"System Design:\n{self.outputs['architect']}", session_path)
        
        if self._check_stop(): return self.outputs
        self._run_phase_generic(IMPL_PHASES[3],
            f"Architecture:\n{self.outputs['architect']}\n\nDatabase:\n{self.outputs['db_admin']}",
            session_path)
        
        if self._check_stop(): return self.outputs
        self._run_phase_generic(IMPL_PHASES[4],
            f"Architecture:\n{self.outputs['architect']}\n\nBackend Code:\n{self.outputs['coder']}",
            session_path)
        
        if self._check_stop(): return self.outputs
        combined = f"Backend:\n{self.outputs['coder']}\n\nFrontend:\n{self.outputs['frontend']}"
        self._run_phase_generic(IMPL_PHASES[5], combined, session_path)
        
        if self._check_stop(): return self.outputs
        current_code = self.outputs["debugger"]
        self._run_judge_loop(task, current_code, session_path)
        final_code = self.outputs.get("debugger_revised", self.outputs["debugger"])
        self.outputs["final_code"] = final_code
        
        if self._check_stop(): return self.outputs
        self._run_phase_generic(IMPL_PHASES[7],
            f"Final Code:\n{final_code}\n\nOriginal Requirements:\n{effective_task}",
            session_path)
        
        if self._check_stop(): return self.outputs
        self._run_phase_generic(IMPL_PHASES[8],
            f"System Architecture:\n{self.outputs['architect']}\n\nFinal Code:\n{final_code}",
            session_path)
        
        if self._check_stop(): return self.outputs
        summ_input = (
            f"Task: {effective_task[:2000]}\n\n"
            f"Architecture: {self.outputs['architect'][:1500]}\n"
            f"Backend: {self.outputs['coder'][:1500]}\n"
            f"Frontend: {self.outputs['frontend'][:1500]}\n"
            f"Final Code: {final_code[:2000]}\n"
            f"Tests: {self.outputs['tester'][:1500]}\n"
            f"Infrastructure: {self.outputs['devops'][:1500]}"
        )
        self._run_phase_generic(IMPL_PHASES[9], summ_input, session_path)
        
        if self._check_stop(): return self.outputs
        self._run_phase_generic(IMPL_PHASES[10],
            f"Project completed.\nTask: {task}\n\nSummary:\n{self.outputs['summarizer']}",
            session_path)
        
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