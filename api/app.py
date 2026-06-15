"""REST surface and the trust dial dashboard.

The same gate, exposed over HTTP for clients that prefer REST and for an IT or
operations lead to watch what each task class has earned the right to do. The
dashboard reads the live trust matrix and renders one dial per task class.

Run it with:  uvicorn api.app:app --reload
"""

from __future__ import annotations

import os
from typing import Any, Dict

from core.event_log import FileEventLog
from core.gatekeeper import Gatekeeper

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    from pydantic import BaseModel
except ImportError as error:  # pragma: no cover
    raise RuntimeError(
        "fastapi and pydantic are required to run the Understudy API. "
        "Install them with: pip install fastapi uvicorn pydantic"
    ) from error


EVENT_LOG_PATH = os.environ.get("UNDERSTUDY_EVENT_LOG", "understudy_events.jsonl")

event_log = FileEventLog(EVENT_LOG_PATH)
gatekeeper = Gatekeeper(event_log)

app = FastAPI(title="Understudy", version="0.1.0")


class EvaluateRequest(BaseModel):
    domain: str
    verb: str
    payload: Dict[str, Any]


class VerdictRequest(BaseModel):
    task_id: str
    bucket_key: str
    reviewer_id: str
    verdict: str
    edit_distance: float = 0.0


class OutcomeRequest(BaseModel):
    task_id: str
    bucket_key: str
    outcome: str


@app.post("/gate/evaluate")
def gate_evaluate(request: EvaluateRequest) -> Dict[str, Any]:
    decision = gatekeeper.evaluate(request.domain, request.verb, request.payload)
    return {
        "bucket_key": decision.bucket_key,
        "autonomy_level": decision.autonomy_level.name,
        "requires_human": decision.requires_human,
        "trust_lower_bound": round(decision.trust_lower_bound, 4),
        "target_confidence": decision.target_confidence,
        "task_count": decision.task_count,
        "failed_closed": decision.failed_closed,
        "reason": decision.reason,
    }


@app.post("/gate/verdict")
def gate_verdict(request: VerdictRequest) -> Dict[str, Any]:
    recorded = gatekeeper.record_verdict(
        request.task_id, request.bucket_key, request.reviewer_id, request.verdict, request.edit_distance
    )
    return {"recorded": recorded}


@app.post("/gate/outcome")
def gate_outcome(request: OutcomeRequest) -> Dict[str, Any]:
    recorded = gatekeeper.record_outcome(request.task_id, request.bucket_key, request.outcome)
    return {"recorded": recorded}


@app.get("/trust/matrix")
def trust_matrix() -> Dict[str, Any]:
    return {"rows": gatekeeper.list_trust()}


DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>Understudy trust dial matrix</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 2rem; color: #1a1a1a; }
  h1 { font-weight: 600; }
  table { border-collapse: collapse; width: 100%; max-width: 880px; }
  th, td { text-align: left; padding: 8px 12px; border-bottom: 1px solid #e5e5e5; }
  .bar { background: #eee; border-radius: 6px; height: 10px; width: 160px; overflow: hidden; }
  .fill { height: 100%; background: #2563eb; }
  .level { font-weight: 600; }
  .empty { color: #888; }
</style>
</head>
<body>
<h1>Trust dial matrix</h1>
<p>What each task class has earned the right to do, measured from real decisions.</p>
<table id="grid">
  <thead><tr><th>Task class</th><th>Trust</th><th>Target</th><th>Level</th><th>Samples</th></tr></thead>
  <tbody><tr><td class="empty" colspan="5">Loading the trust matrix.</td></tr></tbody>
</table>
<script>
async function load() {
  const response = await fetch("/trust/matrix");
  const data = await response.json();
  const body = document.querySelector("#grid tbody");
  if (!data.rows.length) {
    body.innerHTML = '<tr><td class="empty" colspan="5">No task classes recorded yet.</td></tr>';
    return;
  }
  body.innerHTML = data.rows.map(function (row) {
    const pct = Math.round(row.trust_lower_bound * 100);
    return '<tr><td>' + row.bucket_key + '</td>'
      + '<td><div class="bar"><div class="fill" style="width:' + pct + '%"></div></div> ' + pct + '%</td>'
      + '<td>' + Math.round(row.target_confidence * 100) + '%</td>'
      + '<td class="level">' + row.autonomy_level + '</td>'
      + '<td>' + row.task_count + '</td></tr>';
  }).join("");
}
load();
setInterval(load, 4000);
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    return DASHBOARD_HTML
