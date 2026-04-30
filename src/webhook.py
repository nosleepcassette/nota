# maps · cassette.help · MIT
"""nota webhook -- minimal HTTP inbound capture server."""

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

try:
    from src.braindump import _load_dotenv

    _load_dotenv()
except Exception:
    pass


def _check_auth(request_headers: dict) -> bool:
    """Check bearer token from ~/.env NOTA_WEBHOOK_TOKEN. Skip auth if token not set."""
    token = os.environ.get("NOTA_WEBHOOK_TOKEN", "")
    if not token:
        return True  # no token configured = local-only, skip auth
    auth = request_headers.get("Authorization", "")
    return auth == f"Bearer {token}"


def run_server(port: int = 5555, host: str = "127.0.0.1") -> None:
    try:
        from flask import Flask, jsonify, request
    except ImportError:
        print("flask required: pip install flask", file=sys.stderr)
        sys.exit(1)

    from src.tw import _run, task_add

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
        print(f"+ [{task.get('id', '?')}] {task.get('description', '')}", file=sys.stderr)
        return jsonify({"id": task.get("id"), "description": task.get("description")}), 201

    @app.get("/nota/next")
    def next_tasks():
        if not _check_auth(dict(request.headers)):
            return jsonify({"error": "unauthorized"}), 401
        import json as _json

        r = _run("status:pending", "export")
        try:
            tasks = _json.loads(r or "[]")
        except Exception:
            tasks = []
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

    @app.post("/nota/push-check")
    def push_check():
        """Called by cron. Returns tasks due within threshold_minutes."""
        if not _check_auth(dict(request.headers)):
            return jsonify({"error": "unauthorized"}), 401

        import datetime
        from src.tw import task_list

        threshold = int(request.args.get("minutes", 120))
        now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
        cutoff = now + datetime.timedelta(minutes=threshold)

        tasks = task_list(status="pending", limit=200)
        due_soon = []
        for t in tasks:
            due = t.get("due") or ""
            if not due:
                continue
            try:
                if due[:8].isdigit():
                    dt = datetime.datetime.strptime(due[:15], "%Y%m%dT%H%M%S")
                else:
                    dt = datetime.datetime.fromisoformat(due[:19])
                if now <= dt <= cutoff:
                    due_soon.append({
                        "id": t.get("id"),
                        "description": t.get("description", ""),
                        "due": due,
                        "project": t.get("project", ""),
                    })
            except Exception:
                continue

        return jsonify({
            "due_soon": due_soon,
            "count": len(due_soon),
            "checked_at": now.isoformat(),
        })

    print(f"nota webhook running on {host}:{port}", file=sys.stderr)
    print(f"  POST {host}:{port}/nota/capture", file=sys.stderr)
    print(f"  GET  {host}:{port}/nota/next", file=sys.stderr)
    app.run(host=host, port=port)
