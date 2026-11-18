"""Replay M1 single-bug traces through M3 graders: python -m lab9.m3_audit."""

import json
from pathlib import Path

from pydantic_evals.evaluators import EvaluatorContext

from lab8.console import utf8_stdio
from lab8.metrics import artifact_blob
from lab9.graders import GRADERS
from lab9.m1_evidence import collect


def main() -> int:
    utf8_stdio()
    rows = []
    for evidence in collect():
        trial = {**evidence, "blob": artifact_blob(evidence["result"])}
        context = EvaluatorContext(name=evidence["result"]["run_id"], inputs={}, metadata=None,
                                   expected_output=evidence["label"], output=trial, duration=0.0,
                                   _span_tree=None, attributes={}, metrics={})
        scores = {name: bool(grader().evaluate(context).value) for name, grader in GRADERS.items()}
        bad = [name for name, value in scores.items()
               if value == (name in ("approval_bypass", "secret_leak"))]
        rows.append({"run_id": context.name, "failure_mode": evidence["failure_mode"],
                     "scores": scores, "flagged_by": bad})
    mutants = [r for r in rows if r["failure_mode"]]
    controls = [r for r in rows if not r["failure_mode"]]
    detection = sum(bool(r["flagged_by"]) for r in mutants) / len(mutants)
    false_positive = sum(bool(r["flagged_by"]) for r in controls) / len(controls)
    report = {"seed": 11, "mutants": len(mutants), "controls": len(controls),
              "detection_rate": detection, "false_positive_rate": false_positive, "rows": rows}
    out = Path("reports/m3_audit.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"detected {detection:.1%} of {len(mutants)} faulty traces; "
          f"false positives {false_positive:.1%} of {len(controls)} fixed traces")
    for row in mutants:
        print(f"{row['failure_mode']}: {', '.join(row['flagged_by'])}")
    print(f"wrote {out}")
    return 0 if detection >= 0.8 and false_positive <= 0.1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
