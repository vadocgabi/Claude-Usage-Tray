"""Demo data for the Claude usage endpoint (loopback only), values drift slowly so the tray icon changes."""
import http.server
import json
import time

START = time.time()


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        now = time.time()
        iso = lambda delta: time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(now + delta))
        drift = min(30.0, (now - START) / 60.0)          # +1 % per minute, up to +30
        body = json.dumps({
            "five_hour": {"utilization": 52.0 + drift, "resets_at": iso(2.5 * 3600)},
            "seven_day": {"utilization": 41.0 + drift / 6, "resets_at": iso(3 * 86400 + 4 * 3600)},
            "seven_day_sonnet": {"utilization": 28.0, "resets_at": iso(3 * 86400)},
            "seven_day_opus": {"utilization": 73.0, "resets_at": iso(3 * 86400)},
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


http.server.ThreadingHTTPServer(("127.0.0.1", 18765), Handler).serve_forever()
