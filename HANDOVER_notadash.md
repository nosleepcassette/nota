# Handover: notadash
**Date:** 2026-04-14
**From:** Vesper (Claude Code / Sonnet 4.6)
**To:** OpenCode (Codex)
**Project:** `/Users/maps/dev/nota`
**Task:** Build `notadash` — a tmux dashboard for nota/taskwarrior + mapsOS

---

## What Was Done

Created `/Users/maps/dev/nota/bin/notadash` — a zsh script that launches a 7-pane tmux dashboard.
Symlinked to `~/.bin/notadash` (maps' local bin path).

### Layout (as designed)

```
+---------------------------+---------------------+-----------+
|  P1  task burndown.daily  |  P3  task summary   | P6  maps  |
|  (left ~45%, top ~62%)    |  (~60% of right)    | (~40%)    |
+---------------------------+---------------------+-----------+
|  P4  task next            |  P5  task overdue   | P7  shell |
|  (left ~45%, bottom ~38%) |  (~50% of right)    | (~50%)    |
+---------------------------+---------------------+-----------+
|  P2  task calendar (full width, bottom 8 lines)             |
+-------------------------------------------------------------+
```

### Key design decisions
- **pane-base-index 1**: maps' tmux.conf uses 1-based pane indexing. All pane refs are `dash.1` through `dash.7`.
- **Absolute sizes, not percentages**: `-p N%` fails in detached tmux sessions. `-l N` (absolute lines/cols) used throughout.
- **`stty size` for terminal dimensions**: Script reads actual terminal geometry before creating the session, passes to `tmux new-session -x/-y`. Falls back to 220x60 if no tty.
- **Shell loops, not `watch`**: `watch` is not installed. All refresh loops: `while true; do clear; COMMAND; sleep N; done`
- **Session name**: `notadash`
- **tmux status bar**: 1 row reserved (`ROWS -= 1`)

### Commands per pane
| Pane | Content | Refresh |
|------|---------|---------|
| P1 | `task burndown.daily` | 60s |
| P2 | `task calendar` | 3600s |
| P3 | `task summary` | 60s |
| P4 | `task next` | 30s |
| P5 | `task overdue` | 30s |
| P6 | `python3 ~/dev/mapsOS/bin/maps check` + `maps survival` | 120s |
| P7 | bare `zsh` shell | interactive |

### Keybinds (session-scoped)
- `prefix+R` → runs `notadash refresh` (respawns all data panes)
- `prefix+S` → focuses P7 (shell pane)

### Subcommands
```zsh
notadash          # launch or re-attach
notadash kill     # kill session
notadash refresh  # respawn all data panes without restarting
```

---

## Current State

- Script: written, syntax-checked (`zsh -n` passes)
- Symlink: confirmed at `~/.bin/notadash`
- Split logic: verified via headless test (7 panes created correctly)
- **NOT yet tested from a real iTerm terminal** — this is the next step

---

## What Needs Doing (for OpenCode)

### 1. Live test from iTerm
Run `notadash` from a real terminal and verify:
- All 7 panes appear with reasonable proportions
- Each pane renders its command output (task commands are colorized)
- mapsOS pane shows output from `maps check` + `maps survival`
- Shell pane (P7) is focused on launch
- `prefix+R` correctly respawns data panes

### 2. Fix anything broken in the live test
Common failure modes to check:
- Pane too small to display output → adjust layout percentages in the math block
- mapsOS path wrong → update `MAPS_BIN` variable
- `task calendar` output too wide for calendar pane → might need a wider bottom strip or different command

### 3. Optional enhancements maps mentioned
- mapsOS integration depth: currently shows `check` + `survival`. Could also add `maps eval` output rotated in the same pane, or reduce to just today's state tag as a header
- Consider adding `nota projects` as an alternative to `task summary` if it renders better

### 4. Commit
```zsh
cd ~/dev/nota
git add bin/notadash HANDOVER_notadash.md
git commit -m "Add notadash: 7-pane tmux dashboard for nota + mapsOS"
```
Do NOT add Co-Authored-By. Do NOT git push.

---

## File Locations

| File | Purpose |
|------|---------|
| `/Users/maps/dev/nota/bin/notadash` | Main script |
| `~/.bin/notadash` | Symlink (maps' local bin) |
| `~/.bin/taskdash` | Original legacy script (reference only, do not modify) |
| `~/dev/nota/taskwarrior.jpg` | Screenshot of original dashboard layout |
| `~/dev/nota/taskwarrior2.jpg` | Screenshot of original dashboard layout (alt) |
| `~/dev/mapsOS/bin/maps` | mapsOS CLI |

---

## Relevant Context

- **tmux config**: `~/.tmux.conf` — has `base-index 1`, `pane-base-index 1`, amber theme
- **taskwarrior**: v3.4.2, installed at `/usr/local/bin/task`
- **mapsOS**: `~/dev/mapsOS/` — life tracking system. `maps check` gives current state + patterns. `maps survival` shows if survival mode is active.
- **nota**: `~/dev/nota/` — task CLI wrapping taskwarrior. `nota next`, `nota list`, etc. work but the dashboard uses raw `task` commands for richer output (burndown, calendar, summary).

---

## What Vesper is Handling Next

- Codex review of both Vesper's work + OpenCode's output
- Maps is handing off to save Claude spend on implementation; design decisions come back to Vesper if needed

---

*Vesper — 2026-04-14*
