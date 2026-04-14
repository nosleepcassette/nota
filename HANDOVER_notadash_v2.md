# Handoff: notadash — OpenCode → Claude

**Date:** 2026-04-14  
**From:** OpenCode  
**To:** Claude  
**Task:** Live test and fix notadash tmux dashboard  

---

## What Was Done by Vesper (Previous Agent)

- Created `/Users/maps/dev/nota/bin/notadash` — zsh script with 7-pane tmux layout
- Symlinked to `~/.bin/notadash`
- Design documented in `HANDOVER_notadash.md`

---

## What OpenCode Did

### 1. Verified script syntax
```zsh
zsh -n ~/dev/nota/bin/notadash  # passed
```

### 2. Verified dependencies
- tmux: `/usr/local/bin/tmux` ✓
- task: `/usr/local/bin/task` ✓
- mapsOS: `~/dev/mapsOS/bin/maps` ✓

### 3. Attempted to live-test notadash

**Problem:** Cannot run `notadash` from non-tty context (this agent runs headless).  
Tried multiple approaches:
- Running `notadash` directly → `open terminal failed: not a terminal`
- Using `script` command → macOS version lacks `-c` flag
- Using `tmux-bridge` to send to existing pane → works but need real terminal to see output

### 4. Manually reconstructed the split sequence to test layout math

```bash
tmux new-session -d -s notadash -n dash -x 220 -y 59

# Sequence from script:
tmux split-window -v -l 8 -t notadash:dash.1   # P2 calendar
tmux select-pane -t notadash:dash.1
tmux split-window -h -l 121 -t notadash:dash.1 # P3 summary
tmux split-window -v -l 19 -t notadash:dash.1   # P4 next
tmux split-window -v -l 20 -t notadash:dash.3   # P5 overdue
tmux split-window -h -l 48 -t notadash:dash.3   # P6 maps
tmux split-window -h -l 36 -t notadash:dash.5   # P7 shell
```

**Result:** 7 panes created, but sizes are wrong:
```
1: 1x0    (should be ~80x14 — **BROKEN**)
2: 78x14  (calendar, looks correct)
3: 80x8   (summary, looks correct)
4: 1x0    (should be ~80x9 — **BROKEN**)
5: 41x13  (overdue, looks correct)
6: 36x13  (maps, looks correct)
7: 80x8   (shell, looks correct)
```

---

## Root Cause Identified

**The split ordering is incorrect.** When you split vertically from P1, tmux creates a new pane below but **keeps the new pane active**. Subsequent horizontal splits then split from the wrong pane.

The script assumes:
1. Split P1 vertically → P2 created, P1 stays active
2. Split P1 horizontally → P3 created, P1 stays active

Reality:
1. Split P1 vertically → P2 created, **P2** is active
2. Select back to P1
3. Split P1 horizontally → P3 created, **P3** is active
4. Split P1 vertically (for P4) → **no longer splits from P1**, it splits from whatever was last active

The script's logic is sound *if* the pane selection happens correctly between each split, but the order of splits matters.

---

## What Needs Doing (For Claude)

### 1. Live test from a real iTerm terminal
Run `notadash` from your actual terminal and observe:
- All 7 panes with reasonable proportions
- Each command outputting correctly
- Shell pane focused on launch

### 2. If panes are wrong, fix the split order in `/Users/maps/dev/nota/bin/notadash`

The core fix: **Change split order to work with tmux's pane behavior**:
1. Horizontal split first (creates right column) → keep left active
2. Vertical split on left (creates bottom-left) → keep top-left active  
3. etc.

Or: explicitly `select-pane -t` before every split.

### 3. Commit when working
```zsh
cd ~/dev/nota
git add bin/notadash HANDOVER_notadash.md
git commit -m 'Add notadash: 7-pane tmux dashboard for nota + mapsOS'
```
No Co-Authored-By. No push.

---

## Files

| File | Status |
|------|--------|
| `/Users/maps/dev/nota/bin/notadash` | Written, syntax OK, needs live test |
| `~/.bin/notadash` | Symlink exists |
| `/Users/maps/dev/nota/HANDOVER_notadash.md` | Documentation |

---

**— OpenCode, 2026-04-14**