"""Integrity probes beyond the public traps, independent of variant names."""

import copy

import pytest

from lab9.gate import integrity_check, slice_check
from lab9.stats import pass_at_k, pass_hat_k

pytestmark = pytest.mark.student


@pytest.fixture
def clean():
    spec = {"eval_set_version": "v2", "metrics": [
        {"id": "pass_rate", "kind": "capability", "blocking": True,
         "threshold": {"min": 0.8, "no_significant_drop": True}}],
        "slices": [{"name": "money", "metric": "pass_rate", "min": 0.9,
                    "no_significant_drop": True, "blocking": True}]}
    report = {"manifest": {"items": 3, "seeds": [11, 22], "eval_set_sha": "same"},
              "evaluator_failures": [], "metrics": {"pass_rate": 1.0},
              "rows": [{"item_id": f"I-{i}", "seed": s, "pass_rate": True,
                        "slices": ["money"]} for i in range(3) for s in (11, 22)]}
    return report, spec


@pytest.mark.parametrize("attack", ["duplicate", "error", "missing", "slice", "summary", "seeds", "infinity"])
def test_tampered_report_is_rejected(clean, attack):
    base, spec = clean
    pr = copy.deepcopy(base)
    if attack == "duplicate":
        pr["rows"][0] = copy.deepcopy(pr["rows"][1])
    elif attack == "error":
        pr["evaluator_failures"] = ["grader crashed on an otherwise green trial"]
    elif attack == "missing":
        pr["rows"][0]["pass_rate"] = None
    elif attack == "slice":
        pr["rows"][0]["slices"] = []
    elif attack == "summary":
        pr["rows"][0]["pass_rate"] = False
    elif attack == "seeds":
        pr["manifest"]["seeds"] = [11]
        pr["rows"] = [r for r in pr["rows"] if r["seed"] == 11]
    else:
        pr["metrics"]["pass_rate"] = float("inf")
    assert integrity_check(pr, base, spec)


@pytest.mark.parametrize("attack", ["metric", "blocking", "paired", "slice", "slice_floor", "slice_blocking"])
def test_ratchet_blocks_removed_protections(clean, attack):
    base, spec = clean
    loose = copy.deepcopy(spec)
    if attack == "metric":
        loose["metrics"] = []
    elif attack == "blocking":
        loose["metrics"][0]["blocking"] = False
    elif attack == "paired":
        loose["metrics"][0]["threshold"].pop("no_significant_drop")
    elif attack == "slice":
        loose["slices"] = []
    elif attack == "slice_floor":
        loose["slices"][0]["min"] = 0.5
    else:
        loose["slices"][0]["blocking"] = False
    assert integrity_check(base, base, loose, spec)


def test_unchanged_baseline_is_accepted(clean):
    base, spec = clean
    assert integrity_check(base, base, spec, spec) == []
    assert slice_check(base, base, spec)[0] == []


def test_slice_paired_decline_blocks_even_when_floor_is_met(clean):
    base, spec = clean
    pr = copy.deepcopy(base)
    for row in pr["rows"]:
        row["pass_rate"] = False
    spec["slices"][0]["min"] = 0.0
    assert slice_check(pr, base, spec)[0] == ["slice:money/pass_rate"]


@pytest.mark.parametrize("args", [(0, 0, 1), (5, -1, 1), (5, 6, 1), (5, 1, 6),
                                  (5, 1, 0), (5.0, 1, 1), (True, 1, 1)])
def test_pass_k_invalid_for_both_estimators(args):
    for fn in (pass_at_k, pass_hat_k):
        with pytest.raises(ValueError):
            fn(*args)


def test_pass_k_probability_order():
    for n in range(1, 10):
        for c in range(n + 1):
            for k in range(1, n + 1):
                assert 0 <= pass_hat_k(n, c, k) <= c / n + 1e-12
                assert c / n <= pass_at_k(n, c, k) + 1e-12 <= 1 + 1e-12
