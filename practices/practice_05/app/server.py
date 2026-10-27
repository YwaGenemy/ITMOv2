"""HTTP-обёртка над handle_review. Запуск: python -m app.server [port]."""

import json
import logging
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app.llm import FakeLLM
from app.review import handle_review

log = logging.getLogger("reviews")
LLM = FakeLLM()


class ReviewHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/api/reviews":
            self.send_error(404)
            return
        started = time.monotonic()
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        status, payload = handle_review(body, LLM)
        data = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
        # OBS-1: только метаданные, без diff и ответа модели
        log.info("request_id=%s duration_ms=%d status=%d", payload.get("request_id"),
                 (time.monotonic() - started) * 1000, status)

    def log_message(self, format, *args):
        pass


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    ThreadingHTTPServer(("127.0.0.1", port), ReviewHandler).serve_forever()


if __name__ == "__main__":
    main()
