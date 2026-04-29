# maps · cassette.help · MIT
"""nota triage -- interactive inbox processing."""

from typing import Any, Dict

from src.parse import parse_inline
from src.scopes import is_valid_scope
from src.tw import task_delete, task_list, task_modify


def _fmt_task(t: Dict[str, Any]) -> str:
    parts = [f"[{t.get('id', '?')}] {t.get('description', '')}"]
    if t.get("project") and t["project"] != "inbox":
        parts.append(f"@{t['project']}")
    if t.get("scope"):
        parts.append(f"scope:{t['scope']}")
    if t.get("priority"):
        parts.append(t["priority"])
    due = t.get("due")
    if due:
        parts.append(f"due:{due}")
    return "  ".join(parts)


def run_triage(limit: int = 50) -> None:
    """Interactive inbox triage loop."""
    tasks = task_list(project="inbox", status="pending", limit=limit)
    if not tasks:
        print("inbox clear.")
        return

    total = len(tasks)
    print(f"\n⟡ inbox: {total} task(s) to triage\n")
    print("  For each task: type updates in nota syntax, or:")
    print("  enter = keep as-is   s = skip   d = delete   q = quit\n")

    processed = 0
    for i, t in enumerate(tasks[:limit], 1):
        tid = t.get("id")
        desc = t.get("description", "")
        print(f"[{i}/{total}] {_fmt_task(t)}")

        try:
            val = input("  > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nquit.")
            break

        if val.lower() == "q":
            print("quit.")
            break
        if val.lower() == "s":
            print("  skipped.")
            continue
        if val.lower() == "d":
            if tid and task_delete(int(tid)):
                print("  deleted.")
                processed += 1
            else:
                print("  delete failed.")
            continue
        if val == "":
            print("  kept.")
            continue

        parsed = parse_inline(val)
        modify_args: Dict[str, Any] = {}
        if parsed.get("project") and parsed["project"] != "inbox":
            modify_args["project"] = parsed["project"]
        if parsed.get("scope") and is_valid_scope(parsed["scope"]):
            modify_args["scope"] = parsed["scope"]
        if parsed.get("priority"):
            modify_args["priority_p"] = f"p{parsed['priority']}"
        if parsed.get("due_date"):
            modify_args["due"] = parsed["due_date"]
        if parsed.get("tags"):
            modify_args["tags_add"] = parsed["tags"]
        if parsed.get("title") and parsed["title"] != desc:
            modify_args["description"] = parsed["title"]

        if modify_args and tid:
            task_modify(int(tid), **modify_args)
            print(f"  updated -> {' '.join(f'{k}:{v}' for k, v in modify_args.items())}")
        else:
            print("  no changes parsed, kept.")
        processed += 1

    print(f"\ntriage complete. {processed} updated.")
