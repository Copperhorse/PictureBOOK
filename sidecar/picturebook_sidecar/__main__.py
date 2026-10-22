"""Entry point: bind a loopback socket on a free port, serve, print one JSON 'ready' line, exit when the parent goes away.

The core process passes the token in PICTUREBOOK_TOKEN and keeps this process's stdin open; when stdin reaches EOF
(the parent exited or crashed) the sidecar shuts itself down so it never outlives the app."""
import argparse
import json
import os
import socket
import sys
import threading

import uvicorn

from .app import create_app


def main() -> None:
    ap = argparse.ArgumentParser(description="PictureBOOK sidecar")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=0, help="0 = pick a free port")
    ap.add_argument("--no-stdin-watchdog", action="store_true", help="do not exit when stdin closes (manual debugging)")
    args = ap.parse_args()
    token = os.environ.get("PICTUREBOOK_TOKEN", "")
    if args.host not in ("127.0.0.1", "::1", "localhost"):
        sys.exit("refusing to bind to a non-loopback address")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((args.host, args.port))
    port = sock.getsockname()[1]
    server: uvicorn.Server

    def stop() -> None:
        server.should_exit = True

    def announce() -> None:
        print(json.dumps({"event": "ready", "port": port, "pid": os.getpid()}), flush=True)

    app = create_app(token, on_shutdown=stop, on_startup=announce)

    server = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
    if not args.no_stdin_watchdog:
        def watch() -> None:
            try:
                while sys.stdin.read(1024):
                    pass
            except Exception:
                pass
            stop()
        threading.Thread(target=watch, daemon=True).start()
    server.run(sockets=[sock])


if __name__ == "__main__":
    main()
