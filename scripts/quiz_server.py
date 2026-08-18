#!/usr/bin/env python3
"""Static quiz host + result collector with resubmit-safe storage.

Usage:
    python3 quiz_server.py [port] [quiz_dir] [results_dir]

- Serves static files from quiz_dir (default /tmp/quiz-host)
- POST /submit {quiz_id, client_id, timestamp, answers:[...]} -> saves
- GET  /results?quiz=<quiz_id> -> JSON list of attempts (one per client)

Resubmit semantics: one record per (quiz_id, client_id); a resubmit
OVERWRITES that record (auto-update). Full history appended to
history.jsonl for audit. Attempt number returned in the POST response.
"""
import datetime
import json
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

QUIZ_DIR = "/tmp/quiz-host"
RESULTS_ROOT = os.path.expanduser("~/gre-quiz-results")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=QUIZ_DIR, **kw)

    def _send_json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if urlparse(self.path).path != "/submit":
            self._send_json(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", 0))
        try:
            data = json.loads(self.rfile.read(length).decode())
        except Exception:
            self._send_json(400, {"error": "bad json"})
            return
        quiz_id = str(data.get("quiz_id", "default")).replace("/", "_").replace("..", "_")
        client_id = str(data.get("client_id", "anon")).replace("/", "_").replace("..", "_")
        answers = data.get("answers", [])
        attempt = {
            "quiz_id": quiz_id,
            "client_id": client_id,
            "timestamp": data.get("timestamp")
            or datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "answers": answers,
            "score": sum(1 for a in answers if a.get("correct")),
            "total": len(answers),
        }
        qdir = os.path.join(RESULTS_ROOT, quiz_id)
        os.makedirs(qdir, exist_ok=True)
        # overwrite per client -> resubmit auto-updates the record
        with open(os.path.join(qdir, client_id + ".json"), "w") as f:
            json.dump(attempt, f, indent=2)
        with open(os.path.join(qdir, "history.jsonl"), "a") as f:
            f.write(json.dumps(attempt) + "\n")
        n = sum(1 for _ in open(os.path.join(qdir, "history.jsonl")))
        self._send_json(200, {
            "saved": True,
            "attempt": n,
            "score": attempt["score"],
            "total": attempt["total"],
        })

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/results":
            q = parse_qs(urlparse(self.path).query).get("quiz", ["default"])[0]
            qdir = os.path.join(RESULTS_ROOT, q)
            attempts = []
            if os.path.isdir(qdir):
                for fn in sorted(os.listdir(qdir)):
                    if fn.endswith(".json") and fn != "history.jsonl":
                        with open(os.path.join(qdir, fn)) as f:
                            attempts.append(json.load(f))
            self._send_json(200, {"quiz_id": q, "attempts": attempts})
            return
        super().do_GET()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        PORT = int(sys.argv[1])
    else:
        PORT = 8130
    if len(sys.argv) > 2:
        QUIZ_DIR = sys.argv[2]
    if len(sys.argv) > 3:
        RESULTS_ROOT = sys.argv[3]
    os.makedirs(RESULTS_ROOT, exist_ok=True)
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"quiz server :{PORT} dir={QUIZ_DIR} results={RESULTS_ROOT}", flush=True)
    srv.serve_forever()
