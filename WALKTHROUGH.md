# nota — getting started walkthrough
**Names:** `nota` / `telos` / `errant` (all identical, pick your vibe)

---

## 0. Is taskwarrior initialized?

If `~/.task/taskchampion.sqlite3` exists, you're good — no init needed.
Check: `ls ~/.task/`. If empty or missing, run `task version` and it initializes automatically.

Your setup: **already initialized** as of 2026-04-05.

---

## 1. First-time setup (run once)

```bash
nota setup
```

Installs the `scope` UDA and nota contexts into `~/.taskrc`. Idempotent — safe to re-run.

Verify:
```bash
task udas          # should show scope UDA
task context list  # should show meatspace, digital, server, waiting, blocked, ready
```

---

## 2. Add your first tasks

### Simple task
```bash
nota add "reply to Pick n Pull about the part"
```

### With priority and project
```bash
nota add "reply to Pick n Pull p2 @admin"
```

### With scope (where does this task live?)
```bash
nota add "reply to Pick n Pull p2 @admin scope:meatspace"
```

### With due date (taskwarrior parses natural language)
```bash
nota add "file taxes @admin scope:digital due:eom"   # end of month
nota add "call dentist scope:meatspace due:friday"
nota add "push nota to github due:tomorrow"
```

### With dependencies (→ means "I can't do X until Y is done")
```bash
nota add "reply to Pick n Pull -> find stamps"
# Creates: "reply to Pick n Pull" (blocked) + "find stamps" (prerequisite)
```

### With related tasks (:: means loosely connected)
```bash
nota add "reply to Pick n Pull -> find stamps :: clean room"
# Creates all three, links them
```

### Full syntax combined
```bash
nota add "submit job application p1 @work scope:digital due:friday -> update resume -> write cover letter"
```

---

## 3. View your tasks

```bash
nota list              # all pending, grouped by project
nota next              # most urgent actionable tasks (not blocked)
nota blocked           # what's stuck waiting on something else
nota projects          # project breakdown with counts
```

### Filter views
```bash
nota list --project admin
nota list --scope meatspace
nota list --priority 1
```

---

## 4. Taskwarrior context (scoped sessions)

Context auto-assigns your project when you add tasks. Useful for focus sessions.

```bash
task context meatspace     # all adds go to scope:meatspace
task context digital
task context none           # clear context
task context show           # what's active
```

---

## 5. Complete and manage tasks

```bash
nota show 1            # full detail for task #1
nota done 1            # mark task 1 complete
nota depend 3 --on 4   # task 3 can't be done until task 4 is done
nota annotate 2 "called them, left voicemail"
```

---

## 6. Braindump (once braindump.py is built — Step 6)

```bash
nota braindump "i need to clean my room, do laundry, reply to that email about the car part which requires me to find my stamps first, fix the bug in nota's parser, push the gardener fixes to github, and call my landlord about the leak before thursday"
```

This sends the text to an LLM, gets back structured tasks, and adds them all at once with correct projects, scopes, priorities, and dependencies inferred.

---

## 7. Agent interface (MCP)

Agents (Claude Code, Codex, Hermes) can call nota directly:

- `nota_add` — add a task
- `nota_list` — list open tasks
- `nota_next` — most urgent actionable
- `nota_blocked` — blocked tasks
- `nota_show` — full detail
- `nota_done` — mark complete
- `nota_braindump` — LLM-parsed bulk add

In Hermes: "add a task: call dentist scope:meatspace due:friday" → agent calls `nota_add`.

---

## 8. Sample project dump

Establish a few projects now:

```bash
nota add "clean room scope:meatspace @home p2"
nota add "do laundry @home scope:meatspace"
nota add "buy groceries @home scope:meatspace #urgent due:tomorrow p1"
nota add "fix nota braindump parser @nota scope:digital p1"
nota add "push gardener fixes to github @nota scope:digital"
nota add "write hermes skill for nota @nota scope:digital"
nota add "reply to Pick n Pull @admin scope:meatspace -> find stamps"
nota add "call landlord about leak @admin scope:meatspace due:thursday p1"
nota add "file taxes @admin scope:digital due:eom"
```

Then:
```bash
nota projects       # see: admin, home, nota
nota next           # what to do right now
nota list --scope meatspace   # physical world tasks only
```

---

## 9. Aliases

All three names are identical:
```bash
nota add "..."
telos add "..."    # Greek: toward the goal
errant add "..."   # wandering errands, hermes-style
```

Add to PATH if not already there:
```bash
export PATH="$PATH:$HOME/dev/nota/bin"
# or add to ~/.zshrc
```

---

*maps · cassette.help · MIT*
