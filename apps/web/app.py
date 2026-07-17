"""Web entry — prefer stdlib server: `python -m known_path.webapp` or `kp web`.

Optional FastAPI wrapper kept for environments that already install fastapi.
"""

from __future__ import annotations

try:
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse

    from known_path.webapp import DEFAULT_INTENT, _html_page
    from known_path.runner import run_modes

    app = FastAPI(title="known-path demo", version="0.1.0")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return _html_page()

    @app.get("/api/run")
    def api_run(
        mode: str = Query("known-path"),
        intent: str = Query(DEFAULT_INTENT),
    ) -> dict:
        return run_modes(intent, mode, no_commit=False).model_dump()

    @app.get("/api/demo")
    def api_demo(intent: str = Query(DEFAULT_INTENT)) -> list:
        return [
            run_modes(intent, "baseline", no_commit=False).model_dump(),
            run_modes(intent, "known-path", no_commit=False).model_dump(),
            run_modes(intent, "blocked", no_commit=False).model_dump(),
        ]

except ImportError:
    app = None  # type: ignore


def main() -> None:
    from known_path.webapp import main as stdlib_main

    stdlib_main()


if __name__ == "__main__":
    main()
