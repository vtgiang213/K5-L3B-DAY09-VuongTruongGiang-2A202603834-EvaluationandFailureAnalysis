"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, aggregate, load_spec, per_item
from lab9.graders import GRADERS


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems = []
    graded = [m["id"] for m in spec["metrics"] if m["id"] in GRADERS]

    def finite(value):
        return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)

    for entries, slice_mode in ((spec["metrics"], False), (spec.get("slices", []), True)):
        identities = [(e["name"], e["metric"]) if slice_mode else e["id"] for e in entries]
        if len(identities) != len(set(identities)):
            problems.append("spec: duplicate metric or slice definition")
        for entry in entries:
            threshold = entry if slice_mode else entry.get("threshold", {})
            if any(field in threshold and not finite(threshold[field])
                   for field in ("min", "max", "max_increase")):
                problems.append("spec: nonfinite threshold")

    def inspect(report, name):
        start = len(problems)
        rows = report.get("rows", [])
        manifest = report.get("manifest", {})
        seeds, items = manifest.get("seeds", []), manifest.get("items", 0)
        if report.get("evaluator_failures"):
            problems.append(f"{name}: evaluator_failures present")
        if not seeds or len(seeds) != len(set(seeds)) or items <= 0:
            problems.append(f"{name}: invalid manifest items/seeds")
        if len(rows) != items * len(seeds):
            problems.append(f"{name}: row count differs from items x seeds")
        pairs = [(r.get("item_id"), r.get("seed")) for r in rows]
        ids = {p[0] for p in pairs}
        if len(pairs) != len(set(pairs)):
            problems.append(f"{name}: duplicate item/seed rows")
        if None in ids or len(ids) != items or set(pairs) != {(i, s) for i in ids for s in seeds}:
            problems.append(f"{name}: incomplete item x seed grid")
        for mid, value in report.get("metrics", {}).items():
            if not finite(value):
                problems.append(f"{name}: nonfinite/missing metric {mid}")
        for metric in spec["metrics"]:
            if not finite(report.get("metrics", {}).get(metric["id"])):
                problems.append(f"{name}: missing metric {metric['id']}")
        for row in rows:
            for mid in graded:
                if not isinstance(row.get(mid), bool):
                    problems.append(f"{name}: missing/invalid row grade {row.get('item_id')} {mid}")
            if "cost_per_success" in {m["id"] for m in spec["metrics"]}:
                if not finite(row.get("cost")) or row["cost"] < 0:
                    problems.append(f"{name}: invalid row cost")
        # Recompute summaries: editing a metric while keeping its rows must fail too.
        if len(problems) == start and rows:
            normalized = [{"cost": 0, **r} for r in rows]
            recomputed = aggregate(normalized, graded, k_values=spec.get("pass_k", []))
            for metric in spec["metrics"]:
                mid = metric["id"]
                if mid in recomputed:
                    expected, got = recomputed[mid], report["metrics"][mid]
                    if expected is None or not math.isclose(expected, got, abs_tol=1e-4, rel_tol=0):
                        problems.append(f"{name}: metric {mid} disagrees with rows")
        return set(pairs), {p: frozenset(r.get("slices") or []) for p, r in zip(pairs, rows)}

    pr_pairs, pr_slices = inspect(pr, "PR")
    base_pairs, base_slices = inspect(base, "baseline")
    if pr_pairs != base_pairs:
        problems.append("PR item/seed set differs from baseline")
    if pr.get("manifest", {}).get("items") != base.get("manifest", {}).get("items"):
        problems.append("PR manifest item count differs from baseline")
    if set(pr.get("manifest", {}).get("seeds", [])) != set(base.get("manifest", {}).get("seeds", [])):
        problems.append("PR manifest seeds differ from baseline")
    if any(pr_slices[p] != base_slices[p] for p in pr_pairs & base_pairs):
        problems.append("PR slice labels differ from baseline")
    if "seeds" in spec and set(spec["seeds"]) != set(pr.get("manifest", {}).get("seeds", [])):
        problems.append("PR seeds differ from spec")

    if base_spec and spec.get("eval_set_version") == base_spec.get("eval_set_version"):
        def ratchet(old_entries, new_entries, slice_mode=False):
            key = (lambda m: (m["name"], m["metric"])) if slice_mode else (lambda m: m["id"])
            current = {key(m): m for m in new_entries}
            for old in old_entries:
                ident = key(old)
                new = current.get(ident)
                if new is None:
                    problems.append(f"ratchet: removed {ident}")
                    continue
                if old.get("blocking") and not new.get("blocking"):
                    problems.append(f"ratchet: disabled blocking {ident}")
                old_th = old if slice_mode else old.get("threshold", {})
                new_th = new if slice_mode else new.get("threshold", {})
                for field in ("min", "max", "max_increase"):
                    if field in old_th:
                        value = new_th.get(field)
                        if (not finite(value) or (value < old_th[field] if field == "min"
                                                  else value > old_th[field])):
                            problems.append(f"ratchet: loosened {ident}/{field}")
                if old_th.get("no_significant_drop") and not new_th.get("no_significant_drop"):
                    problems.append(f"ratchet: removed paired check {ident}")
                if not slice_mode and any(old.get(f) != new.get(f) for f in ("kind", "grader") if f in old):
                    problems.append(f"ratchet: changed grader/kind {ident}")
        ratchet(base_spec.get("metrics", []), spec.get("metrics", []))
        ratchet(base_spec.get("slices", []), spec.get("slices", []), slice_mode=True)
        if not set(base_spec.get("pass_k", [])) <= set(spec.get("pass_k", [])):
            problems.append("ratchet: removed pass_k estimates")
        for field in ("eval_set", "labels", "seeds", "adversarial_pack", "bootstrap"):
            if field in base_spec and spec.get(field) != base_spec[field]:
                problems.append(f"ratchet: changed {field} on same eval-set version")
    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for entry in spec.get("slices", []):
        name, metric = entry["name"], entry["metric"]
        ident = f"slice:{name}/{metric}"
        a, b = per_item(pr, metric, name), per_item(base, metric, name)
        value = sum(a.values()) / len(a) if a else None
        failed = value is None or set(a) != set(b)
        note = ""
        if value is not None and "min" in entry and value < entry["min"]:
            failed = True
        if entry.get("no_significant_drop") and a and set(a) == set(b):
            keys = sorted(a)
            if len(keys) < 2 and a != b:
                failed, note = True, "insufficient paired items"
            else:
                d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                    n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027),
                    confidence=bs.get("confidence", 0.95))
                note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                failed |= hi < 0
        if failed and entry.get("blocking"):
            blocked.append(ident)
        verdict = "BLOCK" if failed and entry.get("blocking") else ("warn" if failed else "ok")
        lines.append(f"  {ident} {value} {note} {verdict}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid) is not None:
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027),
                                               confidence=bs.get("confidence", 0.95))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
