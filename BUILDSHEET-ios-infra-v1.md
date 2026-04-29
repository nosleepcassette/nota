# BUILDSHEET: nota iOS + Infra + TUI QOL
# maps · cassette.help · MIT
# Target: Codex (autonomous execution)
# Prereqs: nota installed at ~/dev/nota, symlink at ~/.bin/nota, cloudflared tunnel "sextile" running

---

## CONTEXT

`nota webhook` is a Flask capture server already built at `src/webhook.py`.
Cloudflare tunnel `sextile` (ID: 29b902b6-5bd2-4664-aaa3-ba90391ce107) currently proxies
`api.cassette.quest → https://127.0.0.1:4284`. Config at `~/.cloudflared/config.yml`.

We need to:
1. Generate a webhook auth token → `~/.env`
2. Add `nota.cassette.quest` ingress rule to the tunnel config
3. Add DNS route for `nota.cassette.quest`
4. Create launchd plist for persistent webhook server
5. TUI QOL upgrades in `~/dev/nota/src/tui/app.py`
6. Smoke test everything

---

## PART 1 — Token generation + ~/.env

**File:** `~/.env`

Generate a 32-byte hex token and append to `~/.env` if `NOTA_WEBHOOK_TOKEN` is not already set:

```python
import os, secrets, re
from pathlib import Path

env_path = Path.home() / ".env"
content = env_path.read_text() if env_path.exists() else ""

if "NOTA_WEBHOOK_TOKEN" not in content:
    token = secrets.token_hex(32)
    with open(env_path, "a") as f:
        f.write(f"\nexport NOTA_WEBHOOK_TOKEN={token}\n")
    print(f"Token written to ~/.env: {token[:8]}...")
else:
    print("NOTA_WEBHOOK_TOKEN already set — skipping")
```

Run this as a Python script: `python3 /tmp/gen_token.py`

Also source it so the current shell has it:
```zsh
source ~/.env
```

---

## PART 2 — Cloudflare tunnel: add nota.cassette.quest

### 2a. Edit `~/.cloudflared/config.yml`

Current ingress block:
```yaml
ingress:
  - hostname: api.cassette.quest
    service: https://127.0.0.1:4284
    originRequest:
      noTLSVerify: true
      connectTimeout: 10s
  - service: http_status:404
```

Add nota ingress **before** the catch-all `http_status:404` line:
```yaml
ingress:
  - hostname: api.cassette.quest
    service: https://127.0.0.1:4284
    originRequest:
      noTLSVerify: true
      connectTimeout: 10s
  - hostname: nota.cassette.quest
    service: http://127.0.0.1:5055
  - service: http_status:404
```

Edit the file at `~/.cloudflared/config.yml` to insert the nota block exactly as above.

### 2b. Add DNS route

```zsh
cloudflared tunnel route dns sextile nota.cassette.quest
```

Expected output: `Added CNAME nota.cassette.quest...`

### 2c. Reload cloudflared (send SIGHUP to running tunnel)

```zsh
# Find the running cloudflared pid from its pidfile or pgrep
PID=$(pgrep -f "cloudflared tunnel run" | head -1)
if [ -n "$PID" ]; then
    kill -HUP "$PID" && echo "cloudflared reloaded (pid $PID)"
else
    echo "cloudflared not running — start with: cloudflared tunnel run sextile"
fi
```

---

## PART 3 — launchd plist for persistent nota webhook

**File to create:** `~/Library/LaunchAgents/help.cassette.nota.webhook.plist`

Write this file:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>help.cassette.nota.webhook</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/env</string>
    <string>zsh</string>
    <string>-c</string>
    <string>source ~/.env; /Users/maps/.bin/nota webhook --port 5055</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>/tmp/nota-webhook.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/nota-webhook.err</string>
  <key>ThrottleInterval</key>
  <integer>5</integer>
</dict>
</plist>
```

Load it:
```zsh
launchctl load ~/Library/LaunchAgents/help.cassette.nota.webhook.plist
```

Verify it started:
```zsh
sleep 2 && curl -s http://localhost:5055/nota/health && echo ""
# Expected: {"status": "ok"} or similar
```

---

## PART 4 — Smoke test webhook end-to-end

Source the token:
```zsh
source ~/.env
```

Test capture locally:
```zsh
curl -s -X POST http://localhost:5055/nota/capture \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $NOTA_WEBHOOK_TOKEN" \
  -d '{"text": "webhook smoke test @admin #quick"}' | python3 -m json.tool
```

Expected: task created, JSON response with `id` and `description`.

Test via tunnel (run after DNS propagates, may take a few minutes):
```zsh
curl -s -X POST https://nota.cassette.quest/nota/capture \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $NOTA_WEBHOOK_TOKEN" \
  -d '{"text": "tunnel smoke test from codex"}' | python3 -m json.tool
```

Test nota next:
```zsh
curl -s https://nota.cassette.quest/nota/next \
  -H "Authorization: Bearer $NOTA_WEBHOOK_TOKEN"
```

---

## PART 5 — TUI QOL upgrades

**File:** `~/dev/nota/src/tui/app.py`

Read the entire file before making any changes. Make all changes in a single coherent edit pass.

### 5a. Due date countdown column

In `render_tasks_table()`, find where the table columns are defined. Add a `DUE` column (width 6) between PRIORITY and DESCRIPTION (or after DESCRIPTION, before SCOPE).

For each task, compute `due_display`:
```python
import datetime

def _due_display(task: dict) -> tuple:
    """Returns (display_str, style) for due date column."""
    due = task.get("due") or task.get("dueDate") or ""
    if not due:
        return "-", ""
    try:
        # taskwarrior ISO format: 20260502T000000Z
        if "T" in due:
            dt = datetime.datetime.strptime(due[:8], "%Y%m%d").date()
        else:
            dt = datetime.date.fromisoformat(due[:10])
        today = datetime.date.today()
        delta = (dt - today).days
        if delta < 0:
            return f"{abs(delta)}d ago", "bold red"
        elif delta == 0:
            return "today", "bold yellow"
        elif delta == 1:
            return "tmrw", "yellow"
        elif delta <= 7:
            return f"{delta}d", "rgb(255,176,0)"
        else:
            return dt.strftime("%m/%d"), ""
    except Exception:
        return due[:5], ""
```

Add this function near the top of the file (after `AMBER_DIM` constants).

In the Rich table, add a `DUE` column with `style=""` (dynamic per-row) and width 7. Populate it using `_due_display(task)` per row. Apply the style to the cell.

### 5b. Project filter (f key)

Add state variable: `filter_project: str = ""`

In the main loop where `display_tasks` is filtered by `search_query`, also apply:
```python
if filter_project:
    display_tasks = [t for t in display_tasks
                     if (t.get("project") or "").lower() == filter_project.lower()]
```

Add key handler for `f`:
```python
elif key == "f":
    show_cursor()
    text, cancelled = read_line("  \033[33mfilter project (blank=all): \033[0m")
    hide_cursor()
    if not cancelled and text is not None:
        filter_project = text.strip()
    cursor = 0
    pending_key = ""
```

Show active filter in the status bar (append to status_line if `filter_project` is set):
```python
if filter_project:
    status_line += f"  │ project: {filter_project}  (F to clear)"
```

Add `F` (shift-f) to clear filter:
```python
elif key == "F":
    filter_project = ""
    cursor = 0
    pending_key = ""
```

Update help text to include `f / F` entries.

### 5c. Annotations in detail view

In `render_task_detail()`, find where the task fields are rendered. After the existing fields, add:

```python
annotations = task.get("annotations") or []
if annotations:
    lines.append(f"  [bold {AMBER}]Notes[/{AMBER}]")
    for ann in annotations:
        # taskwarrior annotation shape: {"entry": "...", "description": "..."}
        desc = ann.get("description") or str(ann)
        entry = ann.get("entry") or ""
        date_str = ""
        if entry:
            try:
                dt = datetime.datetime.strptime(entry[:8], "%Y%m%d")
                date_str = f"[{AMBER_DIM}]{dt.strftime('%m/%d')}[/{AMBER_DIM}]  "
            except Exception:
                pass
        lines.append(f"    {date_str}{desc}")
```

### 5d. Sort persistence

**File:** `~/dev/nota/src/tui/app.py`

Add two helper functions near the top (after imports):

```python
import json
from pathlib import Path

_TUI_STATE_PATH = Path.home() / ".config" / "nota" / "tui_state.json"

def _load_tui_state() -> dict:
    try:
        if _TUI_STATE_PATH.exists():
            return json.loads(_TUI_STATE_PATH.read_text())
    except Exception:
        pass
    return {}

def _save_tui_state(state: dict) -> None:
    try:
        _TUI_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _TUI_STATE_PATH.write_text(json.dumps(state))
    except Exception:
        pass
```

In `run()`, load state at start:
```python
_state = _load_tui_state()
sort_by = _state.get("sort_by", "id")
sort_reverse = _state.get("sort_reverse", False)
```

Save state when sort changes (after any sort_by or sort_reverse mutation, add):
```python
_save_tui_state({"sort_by": sort_by, "sort_reverse": sort_reverse})
```

### 5e. Update help text

Update `render_full_help()` and `render_help()` to reflect:
- `f` / `F`: filter by project / clear filter
- `DUE` column explained briefly
- Annotations shown in detail view

---

## PART 6 — Smoke tests for new nota commands

After all builds, run each and confirm no traceback:

```zsh
source ~/.env

# NLP add (freeform, no syntax)
nota add "remind me to call the pharmacy on monday morning" --dry-run 2>/dev/null || \
  nota add "remind me to call the pharmacy on monday morning"

# Inline syntax (should NOT trigger NLP)
nota add "check voicemail @health #quick scope:digital"

# capture
nota capture "quick test from smoke test"

# triage (just check it launches, q to exit)
echo "q" | nota triage 2>/dev/null || true

# sync
nota sync 2>&1 | head -5

# webhook health
curl -s http://localhost:5055/nota/health

# bene smoke (just check it exits cleanly)
timeout 3 nota bene < /dev/null 2>/dev/null; true
```

Report any tracebacks or non-zero exits for each command.

---

## PART 7 — Git commit

After all parts complete:

```zsh
cd ~/dev/nota
git add -A
git status --short
git commit -m "infra: iOS webhook launchd + cloudflare + TUI due/filter/annotations/sort-persist"
```

Do NOT run `git push`.

---

## DELIVERABLE

Report back with:
1. Token generated? (first 8 chars only)
2. Cloudflare DNS route added? (y/n + output)
3. launchd loaded? `curl http://localhost:5055/nota/health` result
4. Tunnel curl result (y/n — may need DNS propagation time)
5. TUI parts: which of 5a–5e completed, any that failed
6. Smoke test results: pass/fail per command
7. Git commit hash

Any part that fails: include the exact error.
