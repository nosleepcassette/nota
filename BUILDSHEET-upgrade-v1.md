# maps · cassette.help · MIT
# BUILDSHEET: nota Todoist-replacement upgrade — v1
# Author: Claude (Vesper) · 2026-04-29
# For: Codex

Parts are ordered by dependency. Parts 0 and 11 are bene TUI fixes — do Part 0 first
since it's the foundation for usability. Full spec at ~/dev/nota/NOTA_UPGRADE_SPEC.md.

---

## PART 1: NLP-forward `nota add`

### Goal

When `nota add` receives natural language input (no inline syntax tokens), auto-detect
and route through Gemini 2.0 Flash to infer project/scope/due/tags. Explicit syntax
still works exactly as before — this is additive.

### Files

1. `~/dev/nota/src/braindump.py`
2. `~/dev/nota/src/parse.py`
3. `~/dev/nota/bin/nota`

### braindump.py — add fast provider detection and single-task NLP

Add after the existing `_detect_provider()` function:

```python
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


def nlp_single_task(text: str, model: Optional[str] = None) -> Dict[str, Any]:
    """
    Parse one freeform sentence into a single task dict via LLM.
    Returns a task dict (not a list). Raises on failure.
    """
    model_alias = model or _detect_fast_provider()
    cfg = MODELS.get(model_alias)
    if not cfg:
        raise ValueError(f"Unknown model alias: {model_alias}")

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
            {"role": "system", "content": SINGLE_TASK_PROMPT},
            {"role": "user", "content": f"Parse this task:\n\n{text}"},
        ],
        "temperature": 0.1,
        "max_tokens": 512,
    }
    timeout = 30 if cfg["base_url"] == OLLAMA_BASE else 60
    resp = httpx.post(f"{cfg['base_url']}/chat/completions", json=body, headers=headers, timeout=timeout)
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"].strip()
    if content.startswith("```"):
        content = "\n".join(l for l in content.splitlines() if not l.startswith("```")).strip()
    return json.loads(content)
```

### parse.py — add freeform detection heuristic

Add at module level after imports:

```python
def _looks_freeform(text: str) -> bool:
    """
    True if text looks like natural language rather than nota inline syntax.
    Triggers NLP routing in nota add.
    """
    t = text.strip()
    has_syntax = (
        "@" in t
        or "::" in t
        or "->" in t
        or "scope:" in t.lower()
        or any(f" {p}" in t.lower() or t.lower().startswith(f"{p} ") for p in ("p1","p2","p3","p4"))
    )
    return not has_syntax and len(t.split()) >= 4
```

### bin/nota — update cmd_add

Find `cmd_add` (around line 200-250). Update so that when `_looks_freeform` returns
True and a cloud key is available, it routes through NLP.

Replace the `cmd_add` function body with:

```python
def cmd_add(args):
    from src.parse import parse_inline, _looks_freeform
    from src.tw import task_add, task_depend, task_relate

    text = args.description
    use_nlp = not args.no_nlp and _looks_freeform(text)

    if use_nlp:
        try:
            from src.braindump import nlp_single_task, _detect_fast_provider, _get_api_key, MODELS
            model_alias = _detect_fast_provider()
            cfg = MODELS.get(model_alias, {})
            # Only use NLP if a cloud key is available (don't block on slow ollama for add)
            key_env = cfg.get("key_env")
            if key_env and not _get_api_key(key_env):
                use_nlp = False
        except Exception:
            use_nlp = False

    if use_nlp:
        try:
            from src.braindump import nlp_single_task, _priority_map
            t = nlp_single_task(text)
            # Map LLM priority back to p1-p4
            priority_str = str(t.get("priority", "M")).upper()
            p_num = {"H": 1, "M": 3, "L": 4}.get(priority_str, 3)
            from src.scopes import is_valid_scope
            scope = t.get("scope", "")
            if not is_valid_scope(scope):
                scope = None
            task = task_add(
                description=t.get("description", text.strip()),
                project=t.get("project") or "inbox",
                priority_p=_priority_map(priority_str),
                due=t.get("due") or None,
                tags=t.get("tags") or [],
                scope=scope,
            )
            print(f"+ [{task.get('id','?')}] {task.get('description','')}  (nlp)")
            return
        except Exception as e:
            # Fall through to inline syntax parser on NLP failure
            print(f"  [nlp failed: {e}, using inline parser]", file=sys.stderr)

    # Original inline syntax path (unchanged)
    parsed = parse_inline(text)
    # ... rest of existing cmd_add logic unchanged
```

Add `--no-nlp` flag to the add subparser (around line 150 in bin/nota):

```python
p_add.add_argument("--no-nlp", action="store_true",
    help="Skip NLP inference, use inline syntax only")
```

### Test

```bash
nota add "call my mom tomorrow"
# → + [N] call my mom  @comms meatspace due:tomorrow  (nlp)

nota add "pick up adderall if refill ready"
# → + [N] pick up adderall if refill ready  @health meatspace  (nlp)

nota add "reply to sean p1 @comms scope:digital"
# → uses inline parser (has syntax tokens), no nlp

nota add "call dentist" --no-nlp
# → uses inline parser
```

---

## PART 2: `nota capture` — instant inbox drop

### Goal

`nota capture "..."` — zero friction capture. No LLM. No confirm. No syntax parsing.
Raw text → `@inbox p3`. Returns task ID. Fast enough to use from scripts, Shortcuts, agents.

Also: `nota c "..."` as alias.

### File

`~/dev/nota/bin/nota`

### Add capture subparser and cmd_capture

Add near the bottom of the subparser block:

```python
p_cap = sub.add_parser("capture", aliases=["c"], help="Instantly drop text into inbox (no LLM, no confirm)")
p_cap.add_argument("text", help="What to capture")
p_cap.add_argument("--project", default="inbox", help="Project (default: inbox)")
p_cap.add_argument("--scope", default=None, help="Scope")
p_cap.add_argument("--priority", default="p3", help="Priority p1-p4 (default: p3)")
p_cap.set_defaults(func=cmd_capture)
```

Add the handler:

```python
def cmd_capture(args):
    from src.tw import task_add
    task = task_add(
        description=args.text.strip(),
        project=args.project or "inbox",
        priority_p=args.priority or "p3",
        due=None,
        tags=[],
        scope=args.scope or None,
    )
    tid = task.get("id", "?")
    print(f"+ [{tid}] {task.get('description','')}")
```

### Test

```bash
nota capture "pick up stamps"
# → + [42] pick up stamps

nota c "call sarah back"
# → + [43] call sarah back
```

---

## PART 3: `nota triage` — inbox processing

### Goal

Process `@inbox` tasks one at a time with NL input. GTD-style triage ritual.

### Files

1. `~/dev/nota/src/triage.py` (new)
2. `~/dev/nota/bin/nota`

### src/triage.py

```python
# maps · cassette.help · MIT
"""nota triage — interactive inbox processing."""

import sys
from typing import List, Dict, Any

from src.tw import task_list, task_modify, task_done
from src.parse import parse_inline
from src.scopes import is_valid_scope


def _fmt_task(t: Dict[str, Any]) -> str:
    parts = [f"[{t.get('id','?')}] {t.get('description','')}"]
    if t.get('project') and t['project'] != 'inbox':
        parts.append(f"@{t['project']}")
    if t.get('scope'):
        parts.append(f"scope:{t['scope']}")
    if t.get('priority'):
        parts.append(t['priority'])
    due = t.get('due', {})
    if due:
        parts.append(f"due:{due}")
    return "  ".join(parts)


def run_triage(limit: int = 50) -> None:
    """Interactive inbox triage loop."""
    tasks = task_list(project="inbox", status="pending")
    if not tasks:
        print("inbox clear.")
        return

    total = len(tasks)
    print(f"\n⟡ inbox: {total} task(s) to triage\n")
    print("  For each task: type updates in nota syntax, or:")
    print("  enter = keep as-is   s = skip   d = delete   q = quit\n")

    processed = 0
    for i, t in enumerate(tasks[:limit], 1):
        tid = t.get('id')
        desc = t.get('description', '')
        print(f"[{i}/{total}] {_fmt_task(t)}")

        try:
            val = input("  > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nquit.")
            break

        if val.lower() == "q":
            print("quit.")
            break
        elif val.lower() == "s":
            print("  skipped.")
            continue
        elif val.lower() == "d":
            from src.tw import _run
            _run(["task", str(tid), "delete"], input_str="yes\n")
            print("  deleted.")
            processed += 1
            continue
        elif val == "":
            print("  kept.")
            continue
        else:
            # Parse the input as inline syntax updates
            parsed = parse_inline(val)
            modify_args: Dict[str, Any] = {}
            if parsed.get("project") and parsed["project"] != "inbox":
                modify_args["project"] = parsed["project"]
            if parsed.get("scope") and is_valid_scope(parsed["scope"]):
                modify_args["scope"] = parsed["scope"]
            if parsed.get("priority"):
                from src.tw import _PRIORITY_MAP
                p = _PRIORITY_MAP.get(parsed["priority"])
                if p:
                    modify_args["priority"] = p
            if parsed.get("due_date"):
                modify_args["due"] = parsed["due_date"]
            if parsed.get("tags"):
                modify_args["tags"] = parsed["tags"]
            # If they typed a full description, use it
            if parsed.get("title") and parsed["title"] != val:
                modify_args["description"] = parsed["title"]

            if modify_args:
                task_modify(tid, **modify_args)
                print(f"  updated → {' '.join(f'{k}:{v}' for k,v in modify_args.items())}")
            else:
                print("  no changes parsed, kept.")
            processed += 1

    print(f"\ntriage complete. {processed} updated.")
```

### bin/nota — add triage command

Add subparser:

```python
p_triage = sub.add_parser("triage", help="Process @inbox tasks one at a time")
p_triage.add_argument("--limit", type=int, default=50, help="Max tasks to show")
p_triage.set_defaults(func=cmd_triage)
```

Add handler:

```python
def cmd_triage(args):
    from src.triage import run_triage
    run_triage(limit=args.limit)
```

### Also: inbox badge in `nota next` output

In `bin/nota`, find `cmd_next` and add inbox badge at the top:

```python
def cmd_next(args):
    from src.tw import task_list, task_next
    
    # Inbox badge
    inbox = task_list(project="inbox", status="pending")
    if inbox:
        print(f"⟡ inbox: {len(inbox)} unprocessed  →  nota triage\n")
    
    # Overdue badge
    from src.query import build_filter
    overdue_filter = build_filter(status="pending") + ["due.before:today"]
    from src.tw import _run
    import json as _json
    r = _run(["task"] + overdue_filter + ["export"])
    try:
        overdue = _json.loads(r.stdout or "[]")
        if overdue:
            print(f"⟡ overdue: {len(overdue)} tasks\n")
    except Exception:
        pass
    
    # ... rest of existing cmd_next unchanged
```

### Test

```bash
nota capture "random thought 1"
nota capture "random thought 2"
nota next
# → ⟡ inbox: 2 unprocessed  →  nota triage

nota triage
# → [1/2] [43] random thought 1
# → > @dev scope:digital p2
# → updated → project:dev scope:digital priority:p2
```

---

## PART 4: `nota find` NLP query

### Goal

`nota find "show me everything overdue in comms"` → LLM translates to filter →
`task_list()`. Currently `nota find` takes raw taskwarrior expressions.

### Files

1. `~/dev/nota/src/query.py`
2. `~/dev/nota/bin/nota`

### query.py — add nlp_to_filter

```python
def nlp_to_filter(text: str) -> Dict[str, Any]:
    """
    Convert a natural language query to nota filter kwargs.
    Returns dict suitable for passing to build_filter().
    Calls Gemini via braindump._detect_fast_provider.
    """
    NL_FILTER_PROMPT = """Convert a natural language task search query to a JSON filter object.

Output ONLY a JSON object with these optional keys:
{
  "project": "project name or null",
  "scope": "scope name or null",
  "priority": 1|2|3|4 or null,
  "extra": "raw taskwarrior expression or null (e.g. 'due.before:today' for overdue)",
  "status": "pending|completed|all (default: pending)"
}

Examples:
"overdue tasks" → {"extra": "due.before:today", "status": "pending"}
"health tasks" → {"project": "health"}
"everything in comms scope digital" → {"project": "comms", "scope": "digital"}
"urgent meatspace" → {"scope": "meatspace", "priority": 1}

Output ONLY the JSON. No prose."""

    try:
        from src.braindump import _detect_fast_provider, _call_with_prompt
        result = _call_with_prompt(NL_FILTER_PROMPT, f"Query: {text}")
        import json
        return json.loads(result)
    except Exception:
        return {}  # fallback: empty filter = show all
```

Note: add `_call_with_prompt(system, user)` helper to `braindump.py`:

```python
def _call_with_prompt(system_prompt: str, user_text: str, model: Optional[str] = None) -> str:
    """Call LLM with custom system/user prompts. Returns raw content string."""
    model_alias = model or _detect_fast_provider()
    cfg = MODELS.get(model_alias)
    if not cfg:
        raise ValueError(f"Unknown model: {model_alias}")
    import httpx
    api_key = _get_api_key(cfg["key_env"])
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
```

### bin/nota — update cmd_find

Find `cmd_find`. Add NLP detection before the existing filter path:

```python
def cmd_find(args):
    text = " ".join(args.query) if isinstance(args.query, list) else args.query
    
    # If it looks like a sentence (no : operators), try NLP
    is_sentence = ":" not in text and len(text.split()) >= 3
    filter_kwargs = {}
    
    if is_sentence and not args.no_nlp:
        try:
            from src.query import nlp_to_filter
            filter_kwargs = nlp_to_filter(text)
        except Exception:
            pass
    
    if filter_kwargs:
        from src.tw import task_list
        from src.query import build_filter
        status = filter_kwargs.pop("status", "pending")
        extra = filter_kwargs.pop("extra", None)
        filters = build_filter(status=status, extra=extra, **filter_kwargs)
        # ... render tasks with existing formatter
    else:
        # ... existing raw taskwarrior expression path unchanged
```

Add `--no-nlp` flag to find subparser.

### Test

```bash
nota find "overdue tasks in comms"
nota find "urgent health stuff"
nota find "everything due this week"
nota find "due.before:today" --no-nlp  # raw tw expression still works
```

---

## PART 5: bene TUI sort modes

### Goal

`o` key in bene cycles through sort modes: urgency, due, priority, alpha, scope, added.
Current behavior (urgency sort) stays as default.

### File

`~/dev/bene/src/tui/app.py`

### Step 1: Add sort mode state

After the existing `scope_filter: reactive[str] = reactive("")` line (around line 596):

```python
SORT_MODES = ["urgency", "due", "priority", "alpha", "scope", "added"]
sort_mode: reactive[str] = reactive("urgency")
```

### Step 2: Add binding

In `BeneApp.BINDINGS`, add:

```python
Binding("o", "cycle_sort", "", show=False),
```

### Step 3: Add action_cycle_sort

Add after `action_cycle_scope`:

```python
def action_cycle_sort(self) -> None:
    idx = SORT_MODES.index(self.sort_mode) if self.sort_mode in SORT_MODES else 0
    self.sort_mode = SORT_MODES[(idx + 1) % len(SORT_MODES)]
    self.notify(f"sort: {self.sort_mode}")
    self.action_refresh()
```

### Step 4: Pass sort_mode through to TaskTableView

In the method that builds `TaskTableView` (find where `tb.scope_filter = self.scope_filter`
is set, around line 688), also add:

```python
tb.sort_mode = self.sort_mode
```

Add `sort_mode: reactive[str] = reactive("urgency")` to `TaskTableView` class.

### Step 5: Apply sort in TaskTableView._render_tasks or render method

Find where tasks are sorted/grouped for rendering. Add a `_sort_tasks(tasks, mode)` helper:

```python
def _sort_tasks(tasks: list, mode: str) -> list:
    import time
    if mode == "due":
        # Tasks with due date first (nearest), then no-due at bottom
        has_due = [t for t in tasks if t.due]
        no_due  = [t for t in tasks if not t.due]
        has_due.sort(key=lambda t: t.due.timestamp() if t.due else float("inf"))
        no_due.sort(key=lambda t: -t.urgency)
        return has_due + no_due
    elif mode == "priority":
        p_order = {"H": 0, "M": 1, "L": 2, None: 3, "": 3}
        return sorted(tasks, key=lambda t: (p_order.get(t.priority, 3), -t.urgency))
    elif mode == "alpha":
        return sorted(tasks, key=lambda t: t.description.lower())
    elif mode == "scope":
        from collections import defaultdict
        by_scope = defaultdict(list)
        for t in tasks:
            by_scope[t.scope or ""].append(t)
        result = []
        for scope in sorted(by_scope):
            result.extend(sorted(by_scope[scope], key=lambda t: -t.urgency))
        return result
    elif mode == "added":
        return sorted(tasks, key=lambda t: -(t.id or 0))
    else:  # urgency (default)
        return sorted(tasks, key=lambda t: -t.urgency)
```

Call `_sort_tasks(tasks, self.sort_mode)` before rendering the task list.

For grouped sorts (scope, project): suppress the existing project grouping when
sort_mode is one of ("urgency", "due", "priority", "alpha", "added") — render as
flat list. Keep project grouping only when sort_mode == "scope" or default project view.

### Step 6: Update statusbar

Find where the scope filter label is rendered (around line 220):

```python
f"{sep}[#c87800]⊙ sort:{self.sort_mode}[/#c87800]"
if self.sort_mode != "urgency" else ""
```

Show sort mode only when it's not the default (urgency), so the bar doesn't get noisy.

### Test

```
nota bene
# o → sort: due
# o → sort: priority
# o → sort: alpha
# o → sort: scope
# o → sort: added
# o → sort: urgency (back to default)
```

---

## PART 6: Energy tag rendering in bene

### Goal

Render curated energy tags (`#quick #easy #deep #call #errand #waiting`) with color
coding next to task descriptions in the bene task list. Add to bene and nota.

### Files

1. `~/dev/nota/src/labels.py` (new)
2. `~/dev/bene/src/tui/app.py`

### src/labels.py

```python
# maps · cassette.help · MIT
"""Energy/context label taxonomy for nota tasks."""

ENERGY_TAGS = {
    "quick":   {"desc": "under 5 minutes",           "color": "#a07800"},
    "easy":    {"desc": "low cognitive load",         "color": "#a07800"},
    "deep":    {"desc": "requires uninterrupted focus","color": "#ffb000"},
    "call":    {"desc": "phone or video required",    "color": "#e8e8e8"},
    "errand":  {"desc": "requires leaving the house", "color": "#c87800"},
    "waiting": {"desc": "blocked on someone else",    "color": "#666666"},
    "anywhere":{"desc": "location-independent",       "color": "#a07800"},
    "creative":{"desc": "creative output required",   "color": "#ffb000"},
    "admin":   {"desc": "paperwork/forms/bureaucracy","color": "#a07800"},
}


def is_energy_tag(tag: str) -> bool:
    return tag.lower() in ENERGY_TAGS


def energy_tag_color(tag: str) -> str:
    return ENERGY_TAGS.get(tag.lower(), {}).get("color", "#a07800")
```

### bene app.py — render energy tags inline

Find where task rows are rendered in `TaskTableView` (the loop that builds each row).
After rendering the description, add energy tag badges:

```python
from src.labels import is_energy_tag, energy_tag_color

# In the task row render function, after description:
energy = [t for t in (task.tags or []) if is_energy_tag(t)]
tag_str = ""
if energy:
    tag_parts = []
    for tag in energy[:3]:  # max 3 shown
        color = energy_tag_color(tag)
        tag_parts.append(f"[{color}]#{tag}[/{color}]")
    tag_str = " " + " ".join(tag_parts)
```

Append `tag_str` to the description cell.

### Also: `nota add` NLP should infer energy tags

In `SINGLE_TASK_PROMPT` (Part 1, braindump.py), already includes:
> Tags: use energy labels where obvious — quick, easy, deep, call, errand, waiting

No additional change needed.

### Test

```bash
nota add "pay electric bill" --no-nlp  # tag manually: nota tag <id> admin quick
# in bene: task shows "[#a07800]#admin[/] [#a07800]#quick[/]" after description
nota add "pick up prescription tomorrow"
# → NLP should infer: #errand (meatspace, quick)
```

---

## PART 7: nota webhook — HTTP inbound capture

### Goal

`nota webhook [--port 5555]` starts a minimal Flask server.

- `POST /nota/capture` — insert task (nota capture equivalent)
- `GET /nota/next` — returns nota next output as JSON
- Designed to be tunneled through `api.cassette.quest` for iOS Shortcuts

### Files

1. `~/dev/nota/src/webhook.py` (new)
2. `~/dev/nota/bin/nota`

### src/webhook.py

```python
# maps · cassette.help · MIT
"""nota webhook — minimal HTTP inbound capture server."""

import os
import sys
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))


def _check_auth(request_headers: dict) -> bool:
    """Check bearer token from ~/.env NOTA_WEBHOOK_TOKEN. Skip auth if token not set."""
    token = os.environ.get("NOTA_WEBHOOK_TOKEN", "")
    if not token:
        return True  # no token configured = local-only, skip auth
    auth = request_headers.get("Authorization", "")
    return auth == f"Bearer {token}"


def run_server(port: int = 5555, host: str = "127.0.0.1") -> None:
    try:
        from flask import Flask, request, jsonify
    except ImportError:
        print("flask required: pip install flask", file=sys.stderr)
        sys.exit(1)

    from src.tw import task_add, task_next

    app = Flask("nota-webhook")

    @app.post("/nota/capture")
    def capture():
        if not _check_auth(dict(request.headers)):
            return jsonify({"error": "unauthorized"}), 401
        data = request.get_json(force=True, silent=True) or {}
        text = (data.get("text") or "").strip()
        if not text:
            return jsonify({"error": "text required"}), 400
        task = task_add(
            description=text,
            project=data.get("project", "inbox"),
            priority_p=data.get("priority", "p3"),
            due=data.get("due") or None,
            tags=data.get("tags") or [],
            scope=data.get("scope") or None,
        )
        print(f"+ [{task.get('id','?')}] {task.get('description','')}", file=sys.stderr)
        return jsonify({"id": task.get("id"), "description": task.get("description")}), 201

    @app.get("/nota/next")
    def next_tasks():
        if not _check_auth(dict(request.headers)):
            return jsonify({"error": "unauthorized"}), 401
        from src.tw import _run
        import json as _json
        r = _run(["task", "status:pending", "export"])
        try:
            tasks = _json.loads(r.stdout or "[]")
        except Exception:
            tasks = []
        # Sort by urgency, return top 20
        tasks.sort(key=lambda t: -(t.get("urgency") or 0))
        result = [
            {
                "id": t.get("id"),
                "description": t.get("description"),
                "project": t.get("project"),
                "urgency": t.get("urgency"),
                "due": t.get("due"),
                "priority": t.get("priority"),
            }
            for t in tasks[:20]
        ]
        return jsonify(result)

    @app.get("/nota/health")
    def health():
        return jsonify({"status": "ok", "service": "nota-webhook"}), 200

    print(f"nota webhook running on {host}:{port}", file=sys.stderr)
    print(f"  POST {host}:{port}/nota/capture", file=sys.stderr)
    print(f"  GET  {host}:{port}/nota/next", file=sys.stderr)
    app.run(host=host, port=port)
```

### bin/nota — add webhook command

```python
p_wh = sub.add_parser("webhook", help="Start HTTP capture server (for iOS Shortcuts, automation)")
p_wh.add_argument("--port", type=int, default=5555, help="Port to listen on (default: 5555)")
p_wh.add_argument("--host", default="127.0.0.1", help="Host (default: 127.0.0.1, localhost only)")
p_wh.set_defaults(func=cmd_webhook)
```

```python
def cmd_webhook(args):
    from src.webhook import run_server
    run_server(port=args.port, host=args.host)
```

### Test

```bash
nota webhook &
curl -X POST http://127.0.0.1:5555/nota/capture \
  -H "Content-Type: application/json" \
  -d '{"text": "test webhook capture"}'
# → {"id": 44, "description": "test webhook capture"}

curl http://127.0.0.1:5555/nota/next
# → JSON array of top 20 tasks
```

---

## PART 8: `nota sync` — private git backup

### Goal

`nota sync` commits and pushes `~/.task/` to a private git remote.
Auto-creates local git repo on first run. Separate from the nota code repo.

### File

`~/dev/nota/bin/nota`

### Add sync command

```python
p_sync = sub.add_parser("sync", help="Backup tasks to private git remote")
p_sync.add_argument("--restore", action="store_true", help="Restore from remote (task import)")
p_sync.add_argument("--remote", default=None, help="Git remote URL (set once; saved to ~/.taskrc-sync)")
p_sync.set_defaults(func=cmd_sync)
```

```python
def cmd_sync(args):
    import subprocess, shutil, json as _json
    from pathlib import Path
    from datetime import datetime, timezone

    task_dir = Path.home() / ".task"
    sync_cfg  = Path.home() / ".taskrc-sync"

    # Load or save remote URL
    remote_url = args.remote
    if not remote_url and sync_cfg.exists():
        remote_url = sync_cfg.read_text().strip()
    if args.remote and args.remote != remote_url:
        sync_cfg.write_text(args.remote.strip())
        remote_url = args.remote
        print(f"saved remote: {remote_url}")

    def _git(*git_args, cwd=task_dir, check=True):
        return subprocess.run(["git"] + list(git_args), cwd=cwd, capture_output=True, text=True, check=check)

    if args.restore:
        if not remote_url:
            print("restore requires --remote URL", file=sys.stderr)
            return
        print(f"restoring from {remote_url}…")
        subprocess.run(["git", "clone", remote_url, str(task_dir / "_restore")], check=True)
        export_file = task_dir / "_restore" / "export.json"
        if export_file.exists():
            subprocess.run(["task", "import", str(export_file)], check=True)
            print("restored.")
        return

    # Export current tasks
    r = subprocess.run(["task", "export"], capture_output=True, text=True)
    export_path = task_dir / "export.json"
    export_path.write_text(r.stdout)

    # Init git repo if needed
    if not (task_dir / ".git").exists():
        _git("init")
        gitignore = task_dir / ".gitignore"
        gitignore.write_text("*.lock\n")
        if remote_url:
            _git("remote", "add", "origin", remote_url)
        print("initialized git repo in ~/.task/")

    # Ensure remote is set
    if remote_url:
        remotes = _git("remote", "-v", check=False).stdout
        if "origin" not in remotes:
            _git("remote", "add", "origin", remote_url)

    # Commit
    _git("add", "-A")
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = _git("commit", "-m", f"sync {timestamp}", check=False)
    if result.returncode != 0 and "nothing to commit" in result.stdout + result.stderr:
        print("nothing to sync.")
        return

    # Push if remote configured
    if remote_url:
        _git("push", "-u", "origin", "main", check=False) or \
        _git("push", "-u", "origin", "master", check=False)
        print(f"synced to {remote_url}")
    else:
        print("synced locally (no remote configured — use --remote URL to set one)")
```

### Setup (one-time, maps runs this manually)

```bash
# Create private repo on GitHub first, then:
nota sync --remote git@github.com:nosleepcassette/tasks.git
nota sync   # subsequent syncs
```

### Test

```bash
nota sync
# → synced locally (no remote configured…)

nota sync --remote git@github.com:nosleepcassette/tasks.git
nota sync
# → synced to git@github.com:…
```

---

## PART 9: Cart daily-brief enhancements

### Goal

Add habit reminder and inbox badge to `cart daily-brief` alongside the existing
nota next block.

### File

`~/dev/cartographer/cartographer/daily_brief.py`

### Update `_nota_next_block()`

Replace the existing `_nota_next_block()` function:

```python
import shutil, subprocess, json as _json

def _nota_next_block() -> list[str]:
    """Call nota and return lines for the daily brief. Returns [] if nota not found."""
    if not shutil.which("nota"):
        return []
    lines = []
    try:
        # Next tasks
        r = subprocess.run(["nota", "next", "--limit", "10"],
                          capture_output=True, text=True, timeout=10)
        if r.returncode == 0 and r.stdout.strip():
            lines.append("## nota: urgent")
            for line in r.stdout.strip().splitlines():
                lines.append(line)
    except Exception:
        pass

    try:
        # Inbox badge
        r = subprocess.run(["task", "project:inbox", "status:pending", "export"],
                          capture_output=True, text=True, timeout=10)
        inbox = _json.loads(r.stdout or "[]")
        if inbox:
            lines.append(f"\n⟡ inbox: {len(inbox)} unprocessed  →  nota triage")
    except Exception:
        pass

    try:
        # Habit reminder: unlogged habits today
        r = subprocess.run(["nota", "habits"],
                          capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            unlogged = [l for l in r.stdout.splitlines() if "·" not in l and l.strip() and not l.startswith("──")]
            if unlogged:
                lines.append(f"\n⟡ habits: {len(unlogged)} unlogged today  →  nota bene (t)")
    except Exception:
        pass

    return lines
```

---

## PART 10: Multi-agent convention — SKILL.md update

### Goal

Document the ambient capture convention in nota's SKILL.md so all agents
(Hermes, Claude Code) know to call `nota_capture` for any identified action item.

### File

`~/.hermes/skills/agent-independent/nota/SKILL.md`

### Add after the "Tools" section

```markdown
## Ambient Capture Convention

When you identify an action item, follow-up, TODO, or blocker during any task,
call `nota_capture` (MCP) or run `nota capture "..."` (CLI) to log it immediately.

Do NOT just mention it in prose. If it's something that needs to happen, it
goes in nota.

Examples:
- Claude Code reviews code, sees a FIXME → `nota capture "fix auth token expiry handling in auth.py @dev scope:digital"`
- Hermes processes email, finds action item → `nota capture "reply to [name] re: [topic] @comms scope:digital"`
- Any agent notices a dependency or blocker → `nota capture "unblocked by: [thing] @[project]"`

Use `nota c "..."` (alias) when speed matters.
```

---

## Do NOT across all parts

- Do NOT change default behavior of any existing command
- Do NOT add NLP calls to commands that don't explicitly opt in
- Do NOT require network for any operation that previously worked offline
- Do NOT add new required dependencies — only optional ones with graceful fallback
- Do NOT modify taskwarrior data directly — always go through `src/tw.py`
- Do NOT add `--nlp` as default in non-interactive contexts (scripts, MCP calls)

## Tests (run after all parts)

```bash
# Part 1
nota add "call my mom tomorrow"
nota add "pick up adderall" --no-nlp

# Part 2
nota c "random thought"
nota capture "another thing" --project health --scope meatspace

# Part 3
nota triage
nota next  # check inbox badge appears

# Part 4
nota find "overdue health stuff"
nota find "urgent digital tasks"

# Part 5 (bene)
nota bene
# → o key cycles sort modes

# Part 7
nota webhook &
curl -X POST http://127.0.0.1:5555/nota/capture -d '{"text":"webhook test"}' -H "Content-Type: application/json"

# Part 8
nota sync

# Part 9
cart daily-brief | grep -A10 "nota:"
```

---

## PART 11: bene TUI — usability fixes

### Goal

Fix four broken/missing UX issues in bene:

1. **`c` = complete** — `d` conflicts with vim muscle memory for "done"; add `c` as
   the mark-complete key. Keep `x` as well (already there). Keep `d` = delete.
2. **Arrow key navigation** — DataTable must have focus to receive `up`/`down`. Also,
   `left`/`right` view-switching bindings get swallowed by DataTable's horizontal scroll
   handler. Fix focus management and change view-switch to `[`/`]`.
3. **`space` / `enter` to open detail** — `enter` is already bound but may not fire if
   DataTable intercepts it. Add `space` as a second detail key. Both need DataTable
   focus to work.
4. **Update key hints bar** — KEYHINTS string must reflect the new bindings.

### File

`~/dev/bene/src/tui/app.py`

### Step 1: Add `c` = mark_done, fix view-switch keys

In `BeneApp.BINDINGS`, make these changes:

```python
# REMOVE:
Binding("left",  "prev_view",    "", show=False),
Binding("right", "next_view",    "", show=False),

# ADD in their place:
Binding("bracketleft",  "prev_view",    "", show=False),   # [
Binding("bracketright", "next_view",    "", show=False),   # ]

# ADD alongside existing x = mark_done:
Binding("c",    "mark_done",     "", show=False),

# ADD space = detail:
Binding("space", "detail",       "", show=False),
```

Result BINDINGS list:
```python
BINDINGS = [
    Binding("1", "view('next')",     "", show=False),
    Binding("2", "view('all')",      "", show=False),
    Binding("3", "view('blocked')",  "", show=False),
    Binding("4", "view('habits')",   "", show=False),
    Binding("5", "view('projects')", "", show=False),
    Binding("6", "view('schedule')", "", show=False),
    Binding("7", "view('done')",     "", show=False),
    Binding("bracketleft",  "prev_view",    "", show=False),
    Binding("bracketright", "next_view",    "", show=False),
    Binding("plus", "add_task",      "", show=False),
    Binding("a",    "add_task",      "", show=False),
    Binding("x",    "mark_done",     "", show=False),
    Binding("c",    "mark_done",     "", show=False),
    Binding("d",    "delete_task",   "", show=False),
    Binding("e",    "edit_task",     "", show=False),
    Binding("enter","detail",        "", show=False),
    Binding("space","detail",        "", show=False),
    Binding("t",    "track_habit",   "", show=False),
    Binding("p",    "pomo",          "", show=False),
    Binding("B",    "braindump",     "", show=False),
    Binding("r",    "refresh",       "", show=False),
    Binding("slash","cycle_scope",   "", show=False),
    Binding("q",    "quit",          "", show=False),
]
```

### Step 2: Focus DataTable on mount and view switch

In `on_mount`, after `self.action_refresh()`, add:

```python
def on_mount(self) -> None:
    for tid in ("next", "all", "blocked"):
        tbl = self.query_one(f"#{tid}", DataTable)
        tbl.add_column("ID",   width=4)
        tbl.add_column("pri",  width=3)
        tbl.add_column("description",   width=42)
        tbl.add_column("project",       width=14)
        tbl.add_column("due",           width=8)
        tbl.add_column("tags",          width=16)
    self.action_refresh()
    self.set_interval(60, self.action_refresh)
    # Give initial focus to the task table
    self._focus_current_table()
```

Add the helper:

```python
def _focus_current_table(self) -> None:
    """Focus the DataTable for the current task view, if applicable."""
    if self.current_view in ("next", "all", "blocked"):
        try:
            self.query_one(f"#{self.current_view}", DataTable).focus()
        except Exception:
            pass
```

In `action_view`, call `_focus_current_table()` at the end:

```python
def action_view(self, name: str) -> None:
    self.current_view = name
    self.query_one(ContentSwitcher).current = name
    tb = self.query_one("#topbar", TopBar)
    tb.current_view = name
    if name == "projects":
        self.query_one("#projects", ProjectsView).update(
            self.query_one("#projects", ProjectsView).render_projects(self.store))
    elif name == "schedule":
        self.query_one("#schedule", ScheduleView).update(
            self.query_one("#schedule", ScheduleView).render_schedule(self.store))
    elif name == "done":
        self.query_one("#done", DoneView).update(
            self.query_one("#done", DoneView).render_done(self.store))
    elif name == "habits":
        self.query_one("#habits", HabitsView).update(
            self.query_one("#habits", HabitsView).render_habits(self.hstore))
    # Always refocus the table if switching to a task view
    self._focus_current_table()
```

Also call `_focus_current_table()` at the end of `action_refresh()`.

### Step 3: Update KEYHINTS

Replace the `KEYHINTS` constant:

```python
KEYHINTS = (
    f"  {_hint('[/]', ' views')}  {_hint('1-7', ' jump')}"
    f"{_SEP}{_hint('+/a', ' add')}  {_hint('c/x', ' done')}  {_hint('d', ' del')}"
    f"  {_hint('e', ' edit')}  {_hint('↵/spc', ' detail')}"
    f"{_SEP}{_hint('t', ' track')}  {_hint('p', ' pomo')}  {_hint('B', ' dump')}"
    f"{_SEP}{_hint('/', ' scope')}  {_hint('r', ' refresh')}  {_hint('q', ' quit')}"
)
```

Also update the docstring at the top of the file:

```python
"""
bene TUI — terminal-native task + habit dashboard
...
Keys:
  1-7        switch view
  [/]        prev/next view
  ↑↓         navigate tasks (arrow keys)
  spc/enter  task detail
  +/a        add task
  c/x        mark done
  d          delete task (with confirm)
  e          edit task description
  t          track habit (y)
  T          track habit (skip/n prompt)
  p          start pomo on selected task
  B          braindump
  r          refresh
  /          scope cycle
  q          quit
"""
```

### Do NOT

- Do NOT remove `x` as mark_done — keep both `x` and `c`
- Do NOT remove `enter` as detail — keep both `enter` and `space`
- Do NOT change `d` = delete or `e` = edit
- Do NOT use `priority=True` on bindings — changing keys is cleaner

### Test

```
nota bene
# ↑↓ — rows navigate (DataTable has focus)
# [ ] — switch between views
# space or enter on a task — opens detail modal
# c on a task — marks done (same as x)
# d on a task — opens delete confirm modal
# e on a task — opens edit modal
```
