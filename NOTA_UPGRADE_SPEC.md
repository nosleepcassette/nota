# maps · cassette.help · MIT
# NOTA UPGRADE SPEC — Todoist replacement vision
# Author: Claude (Vesper) · 2026-04-29

nota is already the bones of a real Todoist replacement. taskwarrior does the heavy
lifting; nota is the human surface. This spec closes the gap.

The goal: drop Todoist entirely. Natural language input everywhere. Fast, ambient,
context-aware. Never ask the user to remember syntax.

---

## Current state (what works today)

- `nota add` with inline syntax: `@project #tag scope:X due:X p1 -> depends :: relates`
- `nota braindump "..."` — LLM parses freeform text → structured tasks, `--confirm` flow
- `nota next` / `nota list` / `nota show` / `nota done` / `nota find`
- `nota bene` — bene TUI (Textual, full-featured)
- `nota mcp` — MCP server for Hermes/Claude Code agents
- Habits via harsh: `nota did / nota track / nota log / nota habits`
- Dependencies: `nota depend`, tree view
- Date parsing: `dateparser` for NL dates on `due:` tokens
- Cart integration: `cart daily-brief` includes nota next; `cart nota next/list`
- `nota edit` — modify a task inline
- scopes: meatspace/digital/server/opencassette/appointment/recurring/waiting/creative/admin/errand

## Gaps vs Todoist (what's missing)

### UX gaps
- No quick-add from anywhere (no global hotkey, no web clipper, no share target)
- No inbox processing flow (GTD-style: review inbox, triage, assign project/scope/due)
- No recurring task creation UX (taskwarrior supports it; nota add doesn't expose it)
- `nota add` requires remembering inline syntax — NLP should make it optional
- No bulk operations (done/delete/move multiple tasks at once)
- bene TUI has no search/filter bar (have to restart with different scope/project)
- No quick date picker in TUI (type "friday" and have it resolve visually)
- No note/annotation view inline in task list (currently requires `nota show <id>`)
- No way to snooze/defer a task ("remind me tomorrow")

### Observability gaps
- No weekly review / summary view (what did I complete this week? what's overdue?)
- No project velocity or task throughput stats
- No habit completion trend view (harsh has raw data; no visualization)
- No "focus mode" — single project/scope fullscreen view

### Integration gaps
- No SMS/iMessage quick-add (you can already write a webhook)
- No email-to-task (forward to an address)
- bene braindump modal passes `--dry-run` by default? — confirm passes `--confirm`
- No `nota capture "URL or text"` for link/reading queue (tsundoku adjacent)
- No IFTTT/webhook inbound hook for automation

### Natural language gaps
- `nota add` still requires inline syntax for project/scope/due — NLP should handle
  "call my mom tomorrow meatspace" fully without requiring `@` and `scope:` prefixes
- `nota find "show me everything overdue in comms"` — NL query → filter (LLM-powered)
- `nota move` / `nota edit` don't support NL — "change the clean room task to due friday"

---

## Upgrade plan

### PHASE 1 — NLP-forward input (high leverage, low effort)

#### 1A. `nota add` NLP mode

When input doesn't contain `@project` or `scope:` tokens, run it through the LLM
inline-parser instead of the regex parser. Threshold: if 5+ words and no syntax tokens,
treat as freeform and infer.

This makes `nota add "call my mom tomorrow"` work the same as braindump but for a
single task — fast, no confirmation prompt by default.

**File:** `src/parse.py` + `bin/nota cmd_add`

Add `--nlp` flag (or make it auto-detect). If `--nlp` or auto-detected:
- Call a lightweight LLM single-task extraction (same MODELS priority as braindump)
- Return a single task dict (not an array)
- Insert via existing `task_add`

For auto-detect heuristic: if input has no `@`, no `scope:`, no `p1/p2/p3/p4`,
no `->`, and word count > 4 → treat as NLP mode.

#### 1B. `nota find` NL query

`nota find "show me everything overdue in comms"` → LLM translates to filter args →
`build_filter()` call → `task_list()`.

**File:** `src/query.py` — add `nlp_to_filter(text) → dict` that calls LLM
**File:** `bin/nota cmd_find` — if input looks like a sentence (no `:`), route through NLP

#### 1C. `nota edit` NL

`nota edit 24 "make this due friday"` → LLM parses the instruction → applies field updates.

Currently `nota edit` opens a field-by-field flow. Add NL shortcut:
`nota edit <id> "instruction"` → infer what to change, call `task_modify`.

---

### PHASE 2 — inbox triage UX

#### 2A. `nota triage` command

Shows all `@inbox` tasks one at a time. For each:
- title + current metadata
- Prompt: project? scope? due? priority? (or just Enter to keep)
- NL input: "comms digital tomorrow p1" → parse inline → apply

Flow:
```
[1/12] respond to b
  project: inbox  scope: digital  due: —  priority: !!
  > comms meatspace p1
  ✓ moved to @comms  scope:meatspace  priority:p1

[2/12] ...
```

Tab-completion on project names and scopes. `s` to skip, `d` to delete, `q` to quit.

**File:** `bin/nota` + new `src/triage.py`

#### 2B. Inbox badge in `nota next`

If inbox count > 0, show at top of `nota next` output:
```
⟡ inbox: 4 unprocessed  →  nota triage
```

---

### PHASE 3 — bene TUI upgrades

#### 3A. Search/filter bar

Press `/` in bene → opens inline filter bar at bottom of task list.
Type project name, scope, partial title, or a NL phrase.

For NL: debounce 500ms → call `nota find` NLP → update list.
For syntax: immediate filter via existing `build_filter`.

**File:** `~/dev/bene/src/tui/app.py`

Add `FilterBar` widget (Textual Input, initially hidden).
On `/` keypress: show FilterBar, focus it.
On Escape: hide FilterBar, restore full list.
On submit: apply filter, keep FilterBar visible with current query.

#### 3B. Snooze/defer key

Press `z` on a task → modal: "snooze until?" (NL input, "tomorrow", "friday", "next week")
→ `task <id> modify due:<parsed>`.

#### 3C. Inline annotation view

Press `a` on a task → show annotations below the task row inline (toggle, not a new screen).

#### 3D. Focus mode

Press `f` → fullscreen view of currently selected project, sorted by urgency.
Esc returns to full list.

---

### PHASE 4 — review / stats

#### 4A. `nota review` — weekly review

Shows:
- Completed this week (from `task log`)
- Still open and overdue
- Inbox count
- Habits streak summary

Single read-only view. No editing.

**File:** `bin/nota` + `src/review.py`

#### 4B. `nota stats` — throughput

Shows per-project task completion counts (last 7d, 30d, all-time).
Simple table from `task log export`.

#### 4C. Habit trend in `nota habits`

Current: shows today's status only.
Add: `nota habits --week` → shows last 7 days as a grid (habit × day, ✓/✗/—).

---

### PHASE 5 — capture / inbound

#### 5A. `nota capture "..."` 

Saves to inbox without LLM. Instant. No confirmation. Designed for fast ambient capture
("I'll deal with this later").

Difference from `nota add`: no inline syntax processed, no LLM. Raw text → inbox p3.

Alias: `nota c "..."` for speed.

#### 5B. HTTP webhook inbound

Minimal Flask/aiohttp endpoint. POST to `http://localhost:5555/capture` with
`{"text": "..."}` → same as `nota capture`.

Enables:
- iOS Shortcut → quick-add from phone
- IFTTT / Zapier / email forward → inbox

One-liner server, no auth (localhost only), logs captures to stderr.

**File:** `bin/nota webhook` subcommand  +  `src/webhook.py`

#### 5C. `nota capture --url URL`

Fetch URL title + domain → auto-generate task description.
"read: {title} ({domain})" added to inbox.

Optional: pass to tsundoku instead if available (`tsundoku add URL`).

---

### PHASE 6 — agent habits

These are changes to how Hermes/Claude Code agents use nota:

#### 6A. MCP: `nota_triage` tool

Expose triage as MCP: returns next inbox task, accepts field updates.
Lets Hermes do morning triage from `cart daily-brief`.

#### 6B. MCP: `nota_capture` tool

Fastest-path add: one string, no confirmation, returns task ID.
Agents should use this for anything they notice but don't need to process immediately.

#### 6C. Hermes braindump in daily-brief

`cart daily-brief` currently includes `nota next`. Also include habit reminder:
if unlogged habits exist for today, show them with `nota track` prompt.

---

---

## LLM routing for NLP features

### Why Gemini primary (not NVIDIA/kimi)

braindump.py currently detects NVIDIA first (kimi-k2-instruct) because braindump is a
heavy multi-task parse that benefits from a stronger model. For single-task NLP
(nota add, nota find, nota edit NL), that's overkill — and kimi is slow (~5-15s).

**New routing for single-task NLP:**
```
Primary:   gemini-2.0-flash  (GEMINI_API_KEY)    ~800ms, sufficient for task parsing
Backup:    glm (z-ai/glm4.7) via NVIDIA NIM       slower but reliable
Fallback:  ollama                                  local, last resort
```

braindump keeps its existing routing (kimi first, heavier task). The single-task path
gets its own `_detect_fast_provider()` that prefers Gemini.

```python
def _detect_fast_provider() -> str:
    """Prefer fast models for single-task NLP parsing."""
    if _get_api_key("GEMINI_API_KEY"):
        return "gemini"     # fast enough, no need for kimi-class models here
    if _get_api_key("NVIDIA_API_KEY"):
        return "glm"        # z-ai/glm4.7 — lighter than kimi
    return "ollama"
```

Prompt for single-task extraction is much simpler than braindump — one task in, one
task dict out. ~200 token round trip. Gemini handles this in under a second.

---

## PHASE 3 additions — bene TUI sort modes

### 3E. Sort cycling (new, add to Phase 3)

Key: `o` — cycle through sort modes (o for "order")
Current bene: all task views sort by urgency within project groups.

Sort modes:
```
urgency    (default — taskwarrior urgency score, desc)
due        (nearest due date first, no-due at bottom)
priority   (p1 → p4, then unset)
alpha      (A→Z on description)
scope      (grouped by scope, urgency within)
project    (grouped by project, urgency within — current default for list view)
added      (newest first — task entry order)
```

Cycle indicator shown in statusbar:
```
[next] [scope: all] [sort: due ↑]
```

Implementation in bene app.py:
- Add `sort_mode: reactive[str] = reactive("urgency")` to BeneApp
- Add `SORT_MODES = ["urgency","due","priority","alpha","scope","added"]`
- Add `Binding("o", "cycle_sort", "", show=False)` 
- Add `action_cycle_sort()` — cycles through SORT_MODES, notifies
- Pass `sort_mode` into TaskTableView render; apply sort before rendering rows

For grouped sorts (scope, project): use existing grouping logic, sort within groups by urgency.
For flat sorts (urgency, due, priority, alpha, added): render flat list, no group headers.

---

## Tag system — energy labels

### Problem with current tags

Tags exist (`#quick #easy`) but are free-form, not surfaced in the UI, and not
filterable in bene. Todoist has "labels" as a first-class concept — effectively curated
tags with color coding and filter shortcuts.

### Curated energy/context tag set

These complement scopes (which describe WHERE/HOW a task happens) by describing
HOW MUCH ENERGY it requires:

```
quick      — under 5 minutes, no context-switching cost
easy       — low cognitive load, can do while tired
deep       — requires uninterrupted focus
call       — phone/video required
errand     — requires leaving the house (overlaps scope:meatspace, but is more specific)
waiting    — blocked on someone else's response (use alongside scope:waiting)
anywhere   — fully location-independent, can do on mobile
creative   — creative output required (distinct from scope:creative)
admin      — paperwork, forms, bureaucracy
```

This overlaps with scopes deliberately — tags are stackable, scopes aren't.
`scope:meatspace #errand #call` means "leave the house to make a call."

### Implementation

1. `src/scopes.py` or new `src/labels.py` — define `ENERGY_TAGS` set for validation/autocomplete
2. `nota add` NLP mode — infer energy tags from freeform text ("this is a quick 5 minute thing" → `#quick`)
3. bene TUI — render energy tags with distinct color next to task description:
   - `#quick` → dim amber
   - `#deep` → bright amber (attention)
   - `#waiting` → gray (deprioritize visually)
   - `#call` → white
4. bene filter: `f` key opens tag filter (in addition to scope filter)
5. `nota find "everything quick and easy"` → NL query → `#quick #easy` filter

### Tag parity with Todoist

| Todoist label | nota equivalent |
|--------------|-----------------|
| @quick       | #quick          |
| @low-effort  | #easy           |
| @deep-work   | #deep           |
| @phone       | #call           |
| @errand      | #errand (or scope:meatspace) |
| @waiting-for | scope:waiting or #waiting   |

---

## iOS surface via api.cassette.quest

Hermetica is already on your phone and already connects to sextile through the
Cloudflare tunnel. It's not the right host for nota because its scope is Hermes
sessions — adding a task manager would bloat it.

### Your options

**Option A — Capture webhook + iOS Shortcut** (minimal, ~30min build)

Deploy a Flask endpoint on sextile behind the tunnel:
```
POST api.cassette.quest/nota/capture
Body: {"text": "..."}
→ nota capture "..."
→ returns {"id": 42, "description": "..."}
```

Build an iOS Shortcut: "Ask for input → POST to URL → show notification."
Lives on your home screen or in Share Sheet. One tap + type + done.

No web UI. Just capture. Fast. No auth beyond Cloudflare tunnel.

**Option B — Mobile PWA at api.cassette.quest/nota** (medium, ~2-3h build)

A simple single-page web app served from sextile, tunneled through Cloudflare:
- Big text input at top: "What do you need to do?" → POSTs to capture
- `nota next` output below, auto-refreshed
- Tap a task → mark done / snooze
- Works in iOS Safari, installable as PWA (Add to Home Screen)
- ~200 lines vanilla HTML/CSS/JS + ~100 lines Flask backend

No Swift. No Xcode. Updates instantly when you update sextile.
This is the recommended path — gives you the full Todoist "quick add from anywhere" UX.

**Option C — Hermetica integration** — ruled out (scope bloat).

**Option D — New native Swift app** — too much effort for current phase.

### Recommendation

Ship A first (one afternoon), adds immediate mobile capture.
Ship B in Phase 5 alongside the webhook spec already in the plan.

### Auth for api.cassette.quest

The Cloudflare tunnel already enforces mTLS or Cloudflare Access. If Access is
protecting it with one-time PINs to your email, you're fine. If the `/nota` route needs
to be open to Shortcuts without auth, add a static bearer token in the request header:
```
Authorization: Bearer <token>
```
Flask checks `request.headers.get("Authorization")` == configured token.
Token lives in `~/.env` on sextile.

---

## Multi-agent wiring improvements

### Current state

| Agent | Reads from nota | Writes to nota |
|-------|----------------|----------------|
| Hermes (wizard profile) | ✅ MCP tools | ✅ nota_add |
| Claude Code | ✅ MCP tools | ✅ nota_add |
| Cart daily-brief | ✅ nota next | ✗ |
| polycule | ✗ | ✗ |
| bene | ✅ full TUI | ✅ full TUI |

### Gaps and fixes

**1. The "ambient capture" convention — most impactful**

No agent currently uses nota as a reflexive task capture mechanism. They mention
follow-ups in prose and then they're lost. The fix is a convention, not just code:

> Any agent that identifies an action item, TODO, or follow-up SHOULD call
> `nota_capture` to log it, rather than only mentioning it in conversation.

This means:
- Claude Code reviews code and sees a FIXME → `nota_capture "fix auth token expiry handling in auth.py"`
- Hermes processes an email and sees a required response → `nota_capture "reply to [person] re: [topic]"`
- Hermes finishes a daily-brief and generates a task suggestion → `nota_capture`

Requires: adding `nota_capture` MCP tool (already planned in Phase 6B), and adding
the convention to `~/.hermes/skills/agent-independent/nota/SKILL.md`.

**2. polycule agents**

polycule runs a TCP broker where agents communicate. None of the polycule adapters
currently have nota access. Fix: add nota MCP as a tool available in polycule sessions,
or expose `nota_capture` as a simple HTTP endpoint that polycule agents can hit via
the webhook (Option A above) without needing MCP at all.

**3. Cart daily-brief enhancements**

Already added: nota next block.
Missing:
- Habit reminder: if unlogged habits exist for today → show them with `nota did` suggestion
- Overdue count: "⟡ 3 tasks overdue — nota next" 
- Inbox badge: "⟡ inbox: 7 unprocessed — nota triage"

Add these to `_nota_next_block()` or as separate helpers in `daily_brief.py`.

**4. Hermes morning routine trigger**

Hermes wizard profile could run a morning triage as part of startup when invoked
before noon: auto-call `nota_next`, surface overdue, suggest `nota triage` if
inbox > 3.

This is a SKILL.md behavior change, not code. Add to wizard profile instructions.

**5. Post-commit task capture**

A git post-commit hook that scans the diff for `TODO`, `FIXME`, `HACK` comments and
calls `nota_capture "fix: [comment]  @dev scope:digital"` for each new one.

Lives in a global git hook (`~/.config/git/hooks/post-commit` via `core.hooksPath`).
Makes "I'll deal with this later" TODOs actually trackable.

---

## PHASE 7 — Private git backup for tasks

### Why

- Taskwarrior data lives at `~/.task/` — single point of failure on sextile
- No offsite backup currently
- History/audit trail: know when you added/completed tasks
- Portable: restore full task list on a new machine with `git clone + task import`
- Accountability: optional shared visibility for accountability partner

### Implementation

**7A. `nota sync` command**

```bash
nota sync   # exports + commits + pushes ~/.task/ to private remote
```

Under the hood:
```bash
task export > ~/.task/export.json
cd ~/.task && git add -A && git commit -m "sync $(date -u +%Y-%m-%dT%H:%M:%SZ)"
git push origin main
```

Create `~/.task/.git` repo on first run. Private GitHub repo: `nosleepcassette/tasks`
(or keep it unconnected from your public GitHub identity — use a separate account or
self-hosted Gitea on sextile).

**7B. Auto-sync cron**

Via cart or cron: run `nota sync` once daily (midnight or morning briefing trigger).
No noise unless it fails.

**7C. Restore**

```bash
nota sync --restore  # clone remote, run task import on export.json
```

### Privacy note

Task descriptions may contain sensitive content (health, legal, financial).
Use a **private** repo. GitHub private repos are fine. If you want zero cloud
exposure: self-hosted Gitea at `git.cassette.quest` (same tunnel infrastructure).

---

## Updated priority order

| Item | Value | Effort | Ship order |
|------|-------|--------|-----------|
| 1A — NLP add (Gemini primary)   | ★★★★★ | low    | 1st |
| 5A — nota capture + 5B webhook  | ★★★★☆ | low    | 2nd (enables iOS) |
| iOS Option A (Shortcut)         | ★★★★☆ | low    | 2nd (same session) |
| 3E — bene sort modes            | ★★★★☆ | low    | 3rd |
| Tag system (energy labels)      | ★★★★☆ | medium | 3rd |
| 2A — inbox triage               | ★★★★☆ | medium | 4th |
| 3A — bene search bar            | ★★★☆☆ | medium | 5th |
| 7A — nota sync (git backup)     | ★★★☆☆ | low    | 5th |
| 1B — NL find                    | ★★★☆☆ | low    | 6th |
| iOS Option B (PWA)              | ★★★☆☆ | medium | 6th |
| Multi-agent convention          | ★★★☆☆ | low    | 6th (SKILL.md + convention) |
| 4A — weekly review              | ★★☆☆☆ | medium | 7th |
| Cart daily-brief enhancements   | ★★☆☆☆ | low    | 7th |
| 3B — snooze key                 | ★★☆☆☆ | low    | 7th |
| 6A/B — MCP nota_capture/triage  | ★★☆☆☆ | low    | 8th |
| polycule integration            | ★★☆☆☆ | medium | 8th |
| post-commit TODO capture        | ★★☆☆☆ | low    | 8th |
| 1C — NL edit                    | ★★☆☆☆ | medium | 9th |
| 4B/C — stats                    | ★★☆☆☆ | low    | 9th |

---

## What this achieves

When Phase 1-3 + iOS Option A ships:

```bash
nota add "call my mom tomorrow"                # NLP → @comms meatspace due:tomorrow
nota add "clean the bathroom before friday"    # @house meatspace due:friday
nota triage                                    # GTD-style inbox processing
nota find "what's overdue in health"           # NL query
# iOS: tap Shortcut → type "pick up adderall" → in nota instantly
# bene: o → cycles to due-date sort
# bene: o o → cycles to priority sort
```

That's the Todoist UX surface. The backend is already stronger (dependencies, scopes,
urgency scoring, habits, MCP). This closes the front-end gap.
