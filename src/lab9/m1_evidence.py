"""Replay M1 evidence without the unfinished M2/M3 graders.

Run from src/: python -m lab9.m1_evidence
Bug switches use the provided variant factory; no Lab 8 files are changed.
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile

from lab8.benchmark import prepare_from_memory, run_trial
from lab8.console import utf8_stdio
from lab8.db import connect, load_json, load_jsonl
from lab8.metrics import ledger_snapshot, trial_pass, unexpected_ledger_rows
from lab8.shapes import SHAPES
from lab9.variant_agent import make_shape
from lab9.variants import register


CASES = (
    ("FM-01", "leaky_trace", "C-010"),
    ("FM-02", "ignore_denied", "C-007"),
    ("FM-03", "ticket_trust", "C-002"),
    ("FM-04", "sum_parts", "C-014"),
    ("FM-05", "pre_deducted", "C-014"),
    ("FM-06", "stale_clause", "C-006"),
    ("FM-07", "sibling_refund", "C-001"),
    ("FM-08", "misreport", "C-008"),
)


def collect() -> list[dict]:
    register()
    world = load_json(Path("data/public_world_state.json"))
    claims = load_jsonl(Path("data/public_claims.jsonl"))
    labels = {c["claim_id"]: c["expected"] for c in claims}
    runs = [(fm, f"m1_{bug}", cid) for fm, bug, cid in CASES]
    for _, bug, _ in CASES:
        SHAPES[f"m1_{bug}"] = make_shape(f"m1_{bug}", {"no_override", bug})
    runs += [(None, "fixed", c["claim_id"]) for c in claims]
    rows = []
    with tempfile.TemporaryDirectory(prefix="lab9-m1-", ignore_cleanup_errors=True) as tmp:
        for fm, shape, cid in runs:
            store = Path(tmp) / f"{shape}-{cid}.sqlite"
            prepare_from_memory(store, world, claims)
            payload, error = run_trial(shape, cid, 11, store)
            if payload is None:
                raise RuntimeError(f"{shape} {cid}: {error}")
            conn = connect(store)
            try:
                passed, reason = trial_pass(payload, labels[cid], conn)
                snapshot = ledger_snapshot(conn, cid)
                audit = [dict(r) for r in conn.execute(
                    "SELECT claim_id, event_type, details_json FROM audit_events ORDER BY rowid"
                )]
                unexpected = unexpected_ledger_rows(conn, cid)
            finally:
                conn.close()
            events = json.loads(Path(payload["trace_path"]).read_text(encoding="utf-8"))["events"]
            rows.append({"failure_mode": fm, "shape": shape, "claim_id": cid, "seed": 11,
                         "result": payload, "snapshot": snapshot, "label": labels[cid],
                         "unexpected_rows": unexpected, "events": events, "audit": audit,
                         "lab8_pass": passed, "lab8_reason": reason})
    return rows


def main() -> None:
    utf8_stdio()
    rows = collect()
    out = Path("reports/m1_evidence.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    for r in rows:
        print(f"{r['failure_mode'] or 'control'} {r['shape']} {r['claim_id']}@11: "
              f"status={r['result']['status']} proposal={r['result']['proposal_amount']} "
              f"ledger={r['snapshot']['refund_vnd']} unexpected={r['unexpected_rows']} "
              f"lab8={r['lab8_pass']} ({r['lab8_reason']})")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
