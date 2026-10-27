"""HTTP-обёртка над handle_review. Запуск: python -m app.server [port]."""

import argparse
import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from app.llm import FakeLLM
from app.review import handle_review

INDEX_PATH = Path(__file__).resolve().parent / "static" / "index.html"


class ReviewHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/":
            self.send_error(404)
            return
        try:
            data = INDEX_PATH.read_bytes()
        except FileNotFoundError:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if self.path != "/api/reviews":
            self.send_error(404)
            return
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        status, payload = handle_review(body, self.server.llm, deadline_s=10.0)
        data = json.dumps(payload, ensure_ascii=False).encode()
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, format, *args):
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Локальный API ревью")
    parser.add_argument("port", nargs="?", type=int, default=8000)
    parser.add_argument("--llm", choices=("ok", "slow", "fail"), default="ok")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    with ThreadingHTTPServer(("127.0.0.1", args.port), ReviewHandler) as server:
        if args.llm == "slow":
            server.llm = FakeLLM(delay_s=12.0)
        elif args.llm == "fail":
            server.llm = FakeLLM(error=RuntimeError("demo failure"))
        else:
            server.llm = FakeLLM()
        server.serve_forever()


if __name__ == "__main__":
    main()
