"""Effect firewall inside a fork: an HTTP proxy that records every outgoing request and holds it."""
import http.server, json, sys, time
path = sys.argv[1]
class H(http.server.BaseHTTPRequestHandler):
    def _hold(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(n).decode("utf-8", "replace") if n else ""
        with open(path, "a") as f:
            f.write(json.dumps({"t": time.time(), "method": self.command, "url": self.path, "body": body}) + "\n")
        self.send_response(202); self.send_header("Content-Length", "0"); self.end_headers()
    do_POST = do_GET = do_PUT = do_DELETE = _hold
    def log_message(self, *a): pass
http.server.ThreadingHTTPServer(("127.0.0.1", 8899), H).serve_forever()
