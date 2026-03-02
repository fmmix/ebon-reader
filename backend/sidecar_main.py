from argparse import ArgumentParser
from datetime import datetime
import os
from pathlib import Path
import sys
from threading import Thread
import traceback

import uvicorn


def parse_args() -> tuple[str, int, str | None, str | None]:
    default_host = os.getenv("EBON_HOST", "127.0.0.1")
    default_port = int(os.getenv("EBON_PORT", "8000"))

    parser = ArgumentParser(description="Run eBon Reader FastAPI sidecar")
    parser.add_argument("--host", default=default_host, help="Host to bind")
    parser.add_argument("--port", type=int, default=default_port, help="Port to bind")
    parser.add_argument("--debug-log", help="Optional path for sidecar debug logs")
    parser.add_argument("--db-path", help="Optional path for SQLite database file")
    args = parser.parse_args()
    return args.host, args.port, args.debug_log, args.db_path


def append_debug_log(debug_log: Path, text: str) -> None:
    debug_log.parent.mkdir(parents=True, exist_ok=True)
    with debug_log.open("a", encoding="utf-8") as handle:
        handle.write(text)


def main() -> None:
    host, port, debug_log_path, db_path_arg = parse_args()
    debug_log = Path(debug_log_path) if debug_log_path else None

    if db_path_arg:
        resolved_db_path = Path(db_path_arg).expanduser().resolve()
        resolved_db_path.parent.mkdir(parents=True, exist_ok=True)
        os.environ["EBON_DB_PATH"] = str(resolved_db_path)

    resolved_db_path = (
        Path(os.environ.get("EBON_DB_PATH", "ebon_reader.db")).expanduser().resolve()
    )

    if debug_log:
        os.environ["EBON_DEBUG_LOG"] = str(debug_log)
        timestamp = datetime.now().isoformat(timespec="seconds")
        startup_text = (
            f"[{timestamp}] sidecar startup\n"
            f"cwd={Path.cwd()}\n"
            f"host={host} port={port}\n"
            f"db_path={resolved_db_path}\n"
            f"python={sys.executable}\n"
        )
        append_debug_log(debug_log, startup_text)

    try:
        from main import app

        config = uvicorn.Config(app, host=host, port=port, reload=False)
        server = uvicorn.Server(config)

        def watch_stdin_for_shutdown() -> None:
            if debug_log:
                timestamp = datetime.now().isoformat(timespec="seconds")
                append_debug_log(debug_log, f"[{timestamp}] stdin watcher started\n")

            for line in sys.stdin:
                if "exit" in line.lower():
                    if debug_log:
                        timestamp = datetime.now().isoformat(timespec="seconds")
                        append_debug_log(
                            debug_log,
                            f"[{timestamp}] received stdin exit signal\n",
                        )
                    server.should_exit = True
                    return

            if debug_log:
                timestamp = datetime.now().isoformat(timespec="seconds")
                append_debug_log(debug_log, f"[{timestamp}] stdin closed (EOF)\n")
            server.should_exit = True

        Thread(target=watch_stdin_for_shutdown, daemon=True).start()
        server.run()
    except Exception:
        if debug_log:
            timestamp = datetime.now().isoformat(timespec="seconds")
            error_text = (
                f"[{timestamp}] sidecar startup failed\n{traceback.format_exc()}\n"
            )
            append_debug_log(debug_log, error_text)
        raise


if __name__ == "__main__":
    main()
