"""Read-only API over stored results. Entry point for `make serve`.

A thin layer: it validates requests and reads what the run stored. It opens the
database read-only, so it can never change results, and never reads truth.
"""

import json
from pathlib import Path

import duckdb
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from geo_risk_service.contracts.config import load_settings
from geo_risk_service.contracts.models import Assessment
from geo_risk_service.contracts.schema import from_db_time


def _not_ready(reason: str) -> JSONResponse:
    """503, so load balancers keep traffic away until results exist (Q-S1)."""
    return JSONResponse(
        status_code=503, content={"status": "not_ready", "reason": reason}
    )


def create_app(db_path: Path) -> FastAPI:
    """Build the API over the results database at db_path."""
    db_path = Path(db_path)
    app = FastAPI(title="Geospatial Risk Intelligence Service")

    def latest_run() -> tuple[dict | None, str]:
        """The most recent run summary, or None and the reason it is missing.

        A missing, empty, damaged or locked database is "not ready", never a
        server error.
        """
        if not db_path.is_file():
            return None, f"no results database at {db_path}; run make demo"
        try:
            with duckdb.connect(str(db_path), read_only=True) as con:
                cursor = con.execute(
                    "SELECT * FROM run_summary ORDER BY run_at DESC LIMIT 1"
                )
                row = cursor.fetchone()
                names = [d[0] for d in cursor.description]
        except duckdb.Error as error:
            return None, f"results database at {db_path} not readable: {error}"
        if row is None:
            return None, f"no completed run in {db_path}; run make demo"
        return dict(zip(names, row, strict=True)), ""

    @app.get("/health")
    def health():
        """Ready with the latest run's details, or 503 with the reason."""
        run, reason = latest_run()
        if run is None:
            return _not_ready(reason)
        return {
            "status": "ready",
            "policy_version": run["policy_version"],
            "seed": run["seed"],
            "loaded": run["loaded"],
            "rejected": run["rejected"],
            "rejected_by_reason": json.loads(run["rejected_by_reason"]),
            "decisions_by_outcome": json.loads(run["decisions_by_outcome"]),
            "run_at": from_db_time(run["run_at"]).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    @app.get("/assessments/{login_id}", response_model=Assessment)
    def get_assessment(login_id: str):
        """One login's decision, reason, evidence and policy version."""
        run, reason = latest_run()
        if run is None:
            return _not_ready(reason)
        try:
            with duckdb.connect(str(db_path), read_only=True) as con:
                cursor = con.execute(
                    "SELECT * FROM assessments WHERE login_id = ?", [login_id]
                )
                row = cursor.fetchone()
                names = [d[0] for d in cursor.description]
        except duckdb.Error as error:
            return _not_ready(f"results database at {db_path} not readable: {error}")
        if row is None:
            raise HTTPException(status_code=404, detail=f"unknown login_id: {login_id}")
        record = dict(zip(names, row, strict=True))
        record["event_time"] = from_db_time(record["event_time"])
        return Assessment(**record)

    return app


def default_app() -> FastAPI:
    """The app over the database named in config/settings.yaml (`make serve`)."""
    return create_app(load_settings(Path("config/settings.yaml")).db_path)
