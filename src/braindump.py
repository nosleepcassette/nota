# maps · cassette.help · MIT
"""
nota braindump — LLM-powered freeform text → structured tasks.

Provider priority (auto-detected, sources keys from ~/.env + hermes config):
  1. NVIDIA API (NVIDIA_API_KEY) — default model: glm (z-ai/glm4.7, fast)
  2. Gemini API (GEMINI_API_KEY)  — fallback: gemini-2.0-flash
  3. Local ollama                 — last resort offline fallback

Usage:
  nota braindump "i need to clean my room, reply to pick n pull which requires finding stamps..."
  nota braindump --model deepseek "..."
  nota braindump --model gemini "..."
  nota braindump --model ollama/qwen3.5 "..."
  nota braindump --dry-run "..."    # print tasks without inserting

Model aliases map to full API model IDs — e.g. "glm" → "z-ai/glm4.7" on NVIDIA NIM.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

# ── dotenv loader ─────────────────────────────────────────────────────────────

def _load_dotenv() -> None:
    """Load ~/.env into os.environ for any keys not already set. Never overwrites."""
    env_file = Path.home() / ".env"
    if not env_file.exists():
        return
    for raw in env_file.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:]
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        # Strip surrounding quotes
        val = val.strip()
        if (val.startswith('"') and val.endswith('"')) or \
           (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        if key and key not in os.environ:
            os.environ[key] = val

# Load .env at import time so all downstream checks see the keys
_load_dotenv()

# ── model registry ─────────────────────────────────────────────────────────────
# Keys here are short aliases. The "model" field is the full API model ID that
# gets sent in the request body — never the alias itself.

NVIDIA_BASE  = "https://integrate.api.nvidia.com/v1"
GEMINI_BASE  = "https://generativelanguage.googleapis.com/v1beta/openai"
OLLAMA_BASE  = "http://localhost:11434/v1"

MODELS = {
    # ── NVIDIA NIM (NVIDIA_API_KEY) ──────────────────────────────────────────
    # Alias         full API model ID (sent to NVIDIA NIM)
    "glm":          {"base_url": NVIDIA_BASE, "model": "z-ai/glm4.7",                              "key_env": "NVIDIA_API_KEY"},
    "deepseek":     {"base_url": NVIDIA_BASE, "model": "deepseek-ai/deepseek-v3.2",                "key_env": "NVIDIA_API_KEY"},
    "qwen-coder":   {"base_url": NVIDIA_BASE, "model": "qwen/qwen3-coder-480b-a35b-instruct",      "key_env": "NVIDIA_API_KEY"},
    "kimi":         {"base_url": NVIDIA_BASE, "model": "moonshotai/kimi-k2-instruct",              "key_env": "NVIDIA_API_KEY"},
    "kimi-think":   {"base_url": NVIDIA_BASE, "model": "moonshotai/kimi-k2-thinking",              "key_env": "NVIDIA_API_KEY"},
    "qwen3.5":      {"base_url": NVIDIA_BASE, "model": "qwen/qwen3.5-397b-a17b",                  "key_env": "NVIDIA_API_KEY"},
    # ── Gemini (GEMINI_API_KEY) ──────────────────────────────────────────────
    "gemini":       {"base_url": GEMINI_BASE, "model": "gemini-2.0-flash",                        "key_env": "GEMINI_API_KEY"},
    "gemini-pro":   {"base_url": GEMINI_BASE, "model": "gemini-2.5-pro",                          "key_env": "GEMINI_API_KEY"},
    # ── Local ollama (no key) ────────────────────────────────────────────────
    "ollama/qwen3.5": {"base_url": OLLAMA_BASE, "model": "kiwi_kiwi/qwen3.5-abliterated:9b",      "key_env": None},
    "ollama/gemma4":  {"base_url": OLLAMA_BASE, "model": "gemma4:31b",                             "key_env": None},
    "ollama":         {"base_url": OLLAMA_BASE, "model": "kiwi_kiwi/qwen3.5-abliterated:9b",      "key_env": None},
}

VALID_SCOPES = {"meatspace","digital","server","opencassette","appointment","recurring","waiting","creative","admin","errand"}


def _confirm_and_filter(parsed: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Interactive confirm flow. Returns filtered/edited task list."""
    if not sys.stdout.isatty():
        print("(non-interactive: skipping confirm, inserting all)", file=sys.stderr)
        return parsed

    print(f"\nParsed {len(parsed)} task(s):\n")
    for i, t in enumerate(parsed, 1):
        parts = [f"  [{i}] {t.get('description', '')}"]
        if t.get("project"):    parts.append(f"@{t['project']}")
        if t.get("scope"):      parts.append(f"scope:{t['scope']}")
        if t.get("priority"):   parts.append(t["priority"])
        if t.get("due"):        parts.append(f"due:{t['due']}")
        if t.get("depends_on"): parts.append(f"(depends on: {', '.join(t['depends_on'])})")
        print("  ".join(parts))

    print("\nInsert all? [Y/n/e]  (e = edit individual)")
    choice = input("> ").strip().lower()

    if choice == "n":
        print("cancelled.")
        return []

    if choice == "e":
        kept = []
        for t in parsed:
            desc = t.get("description", "")
            print(f"\n  {desc}")
            print("  [enter=keep  new text=rename  'skip'=drop]")
            val = input("  > ").strip()
            if val.lower() == "skip":
                continue
            if val:
                t = dict(t, description=val)
            kept.append(t)
        if not kept:
            print("no tasks kept.")
            return []
        print(f"\n{len(kept)} task(s) to insert:")
        for t in kept:
            print(f"  · {t['description']}")
        print("Insert? [Y/n]")
        if input("> ").strip().lower() == "n":
            return []
        return kept

    return parsed  # Y or empty = insert all


# ── prompt ────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a task management assistant. Parse freeform text into structured tasks.

Output ONLY a JSON array. No prose, no markdown fences, no explanation.

Each task object:
{
  "description": "short action title",
  "project": "single word project name (inbox if unclear)",
  "scope": "one of: meatspace digital server opencassette appointment recurring waiting creative admin errand (blank if unclear)",
  "priority": "H, M, or L",
  "due": "YYYY-MM-DD or natural language like 'friday' 'eom' 'tomorrow' — null if none",
  "tags": ["array", "of", "tags"],
  "depends_on": ["description of prerequisite task if any — must match another task's description exactly"]
}

Rules:
- Break compound tasks into subtasks. "reply to email which requires finding stamps" → two tasks with depends_on
- Infer scope: physical actions = meatspace, computer work = digital, sysadmin = server
- Infer project from context: cleaning/groceries/home = home, work tasks = work, code = the repo name, etc.
- Priority: urgent/deadline/blocking = H, normal = M, someday/low-stakes = L
- Keep descriptions as short imperative phrases: "call dentist", "push nota to github", "find stamps"
- depends_on: if task A cannot be started until task B is done, A.depends_on = [B.description]
- Do not invent tasks not mentioned in the input. Do not add filler.
"""

USER_TEMPLATE = """Parse this into tasks:

{text}"""


# ── provider auto-detection ───────────────────────────────────────────────────

def _detect_provider() -> str:
    """Return best available model alias. Checks env + ~/.env + hermes config."""
    if _get_api_key("NVIDIA_API_KEY"):
        return "kimi"         # moonshotai/kimi-k2-instruct — reliable default
    if _get_api_key("GEMINI_API_KEY"):
        return "gemini"       # gemini-2.0-flash — good fallback
    return "ollama"           # local last resort


def _detect_fast_provider() -> str:
    """Prefer fast models for single-task NLP. Gemini first, GLM backup."""
    if _get_api_key("GEMINI_API_KEY"):
        return "gemini"      # gemini-2.0-flash — ~800ms, sufficient
    if _get_api_key("NVIDIA_API_KEY"):
        return "glm"         # z-ai/glm4.7 — lighter than kimi
    return "ollama"


SINGLE_TASK_PROMPT = """Extract ONE task from the text. Output ONLY a JSON object (not an array).

{
  "description": "short imperative action title",
  "project": "single word (inbox if unclear)",
  "scope": "meatspace|digital|server|opencassette|appointment|recurring|waiting|creative|admin|errand or empty string",
  "priority": "H, M, or L",
  "due": "YYYY-MM-DD or natural language like 'friday' 'tomorrow' or null",
  "tags": ["array", "of", "tags"]
}

Rules:
- Keep description short: "call dentist", "clean bathroom", "reply to Sean"
- Infer scope from context: physical = meatspace, computer = digital
- Infer project from context
- Tags: use energy labels where obvious — quick, easy, deep, call, errand, waiting
- Output ONLY the JSON object. No prose, no markdown fences, no array wrapper."""


def _get_api_key(key_env: Optional[str]) -> str:
    if not key_env:
        return "ollama"  # ollama doesn't need a real key
    val = os.environ.get(key_env, "")
    if not val:
        # Try reading from hermes config.yaml as fallback
        try:
            import re
            cfg = Path.home() / ".hermes" / "config.yaml"
            text = cfg.read_text()
            m = re.search(r'api_key:\s*(\S+)', text)
            if m and not m.group(1).startswith("$"):
                return m.group(1)
        except Exception:
            pass
    return val


# ── LLM call ─────────────────────────────────────────────────────────────────

def _call_llm(text: str, model_alias: str) -> List[Dict[str, Any]]:
    """Call LLM, return parsed list of task dicts."""
    try:
        import httpx
    except ImportError:
        raise RuntimeError("httpx required: python3 -m pip install httpx")

    cfg = MODELS.get(model_alias)
    if not cfg:
        raise ValueError(f"Unknown model alias '{model_alias}'. Available: {', '.join(MODELS)}")

    api_key = _get_api_key(cfg["key_env"])
    if not api_key and cfg["key_env"]:
        raise RuntimeError(f"API key not found. Set {cfg['key_env']} env var.")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    body = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_TEMPLATE.format(text=text)},
        ],
        "temperature": 0.2,
        "max_tokens": 4096,
    }

    # Shorter timeout for local ollama (fast fail if not running)
    timeout = 30 if cfg["base_url"] == OLLAMA_BASE else 120

    resp = httpx.post(
        f"{cfg['base_url']}/chat/completions",
        json=body,
        headers=headers,
        timeout=timeout,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"].strip()

    # Strip markdown fences if model ignored instructions
    if content.startswith("```"):
        content = "\n".join(
            line for line in content.splitlines()
            if not line.startswith("```")
        ).strip()

    return json.loads(content)


def _call_with_prompt(system_prompt: str, user_text: str, model: Optional[str] = None) -> str:
    """Call LLM with custom system/user prompts. Returns raw content string."""
    model_alias = model or _detect_fast_provider()
    cfg = MODELS.get(model_alias)
    if not cfg:
        raise ValueError(f"Unknown model: {model_alias}")
    try:
        import httpx
    except ImportError:
        raise RuntimeError("httpx required: pip install httpx")

    api_key = _get_api_key(cfg["key_env"])
    if not api_key and cfg["key_env"]:
        raise RuntimeError(f"API key not found. Set {cfg['key_env']} env var.")
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    body = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0.1,
        "max_tokens": 256,
    }
    timeout = 30 if cfg["base_url"] == OLLAMA_BASE else 60
    resp = httpx.post(f"{cfg['base_url']}/chat/completions", json=body, headers=headers, timeout=timeout)
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"].strip()
    if content.startswith("```"):
        content = "\n".join(l for l in content.splitlines() if not l.startswith("```")).strip()
    return content


def nlp_single_task(text: str, model: Optional[str] = None) -> Dict[str, Any]:
    """
    Parse one freeform sentence into a single task dict via LLM.
    Returns a task dict (not a list). Raises on failure.
    """
    content = _call_with_prompt(
        SINGLE_TASK_PROMPT,
        f"Parse this task:\n\n{text}",
        model=model,
    )
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise ValueError("single-task NLP returned non-object JSON")
    return parsed


# ── task creation from parsed output ─────────────────────────────────────────

def _priority_map(p: str) -> str:
    return {"H": "p1", "M": "p3", "L": "p4"}.get(str(p).upper(), "p3")


def insert_parsed_tasks(
    parsed: List[Dict[str, Any]],
    dry_run: bool = False,
    confirm: bool = False,
) -> List[Dict[str, Any]]:
    """
    Insert parsed tasks into taskwarrior.
    Resolves depends_on by description matching after all tasks are created.
    Returns list of created task dicts.
    """
    from src.tw import task_add, task_depend

    if dry_run:
        print(json.dumps(parsed, indent=2))
        return parsed

    if confirm:
        parsed = _confirm_and_filter(parsed)
        if not parsed:
            return []

    # First pass: create all tasks, build description→id map
    created: List[Dict[str, Any]] = []
    desc_to_id: Dict[str, int] = {}

    for t in parsed:
        desc = t.get("description", "").strip()
        if not desc:
            continue

        scope = t.get("scope", "")
        if scope not in VALID_SCOPES:
            scope = None

        task = task_add(
            description=desc,
            project=t.get("project") or "inbox",
            priority_p=_priority_map(t.get("priority", "M")),
            due=t.get("due") or None,
            tags=t.get("tags") or [],
            scope=scope or None,
        )
        tid = task.get("id")
        if tid:
            desc_to_id[desc.lower()] = tid
            created.append(task)

    # Second pass: resolve dependencies
    for t in parsed:
        desc = t.get("description", "").strip().lower()
        task_id = desc_to_id.get(desc)
        if not task_id:
            continue
        for dep_desc in (t.get("depends_on") or []):
            dep_id = desc_to_id.get(dep_desc.strip().lower())
            if dep_id:
                task_depend(task_id, dep_id)

    return created


# ── public API ────────────────────────────────────────────────────────────────

def braindump(
    text: str,
    model: Optional[str] = None,
    dry_run: bool = False,
    confirm: bool = False,
    verbose: bool = True,
) -> List[Dict[str, Any]]:
    """
    Parse freeform text into tasks and insert into taskwarrior.

    Args:
        text:     Freeform brain dump
        model:    Model alias (see MODELS dict). Auto-detected if None.
        dry_run:  Print JSON without inserting
        confirm:  Review parsed tasks before inserting
        verbose:  Print progress

    Returns:
        List of created task dicts
    """
    model_alias = model or _detect_provider()

    if verbose:
        cfg = MODELS.get(model_alias, {})
        print(f"Parsing with {cfg.get('model', model_alias)}...")

    try:
        parsed = _call_llm(text, model_alias)
    except Exception as e:
        # Try ollama fallback if cloud failed
        if model_alias != "ollama":
            if verbose:
                print(f"  {model_alias} failed ({e}), trying ollama fallback...")
            parsed = _call_llm(text, "ollama")
        else:
            raise

    if verbose:
        print(f"  {len(parsed)} task(s) parsed")

    created = insert_parsed_tasks(parsed, dry_run=dry_run, confirm=confirm)

    if verbose and not dry_run:
        for t in created:
            print(f"  + [{t.get('id','?')}] {t.get('description','')}")

    return created
