"""Cross-platform entry point for the SPC Watchdog demo server."""

from __future__ import annotations

import argparse
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path
from urllib.request import urlopen

import uvicorn

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from spc_watchdog.app import create_app  # noqa: E402


def parse_args() -> argparse.Namespace:
    """Parse the deliberately small public runner surface."""

    parser = argparse.ArgumentParser(description="Run SPC Watchdog.")
    parser.add_argument("--mode", choices=("live", "replay"), default="live")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Boot the HTTP server, verify health, and exit.",
    )
    return parser.parse_args()


def _available_port() -> int:
    """Reserve a likely-free loopback port for the short CI smoke test."""

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def smoke_test(mode: str) -> None:
    """Prove that a credential-free server reaches its health endpoint."""

    port = _available_port()
    # A disposable DB lets live and replay smoke checks run concurrently in CI.
    with tempfile.TemporaryDirectory(prefix="spc-watchdog-smoke-") as temp_dir:
        app = create_app(mode=mode, data_path=Path(temp_dir) / "world.db")
        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
        server = uvicorn.Server(config)
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()

        deadline = time.monotonic() + 10
        try:
            while time.monotonic() < deadline:
                try:
                    with urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1) as response:
                        if response.status == 200:
                            print(f"SPC Watchdog {mode} boot smoke test passed.")
                            return
                except OSError:
                    time.sleep(0.1)
            raise RuntimeError("SPC Watchdog did not become healthy within 10 seconds.")
        finally:
            server.should_exit = True
            thread.join(timeout=5)


def main() -> None:
    """Start the selected demo mode or execute its boot smoke test."""

    args = parse_args()
    if args.smoke_test:
        smoke_test(args.mode)
        return

    app = create_app(mode=args.mode, data_path=ROOT / "data" / "spc-watchdog.db")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
