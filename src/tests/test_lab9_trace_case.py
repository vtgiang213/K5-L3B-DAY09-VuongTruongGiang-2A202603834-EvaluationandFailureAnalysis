"""C-002 regression: a ticket must not replace the DB's delay_days."""

import pytest
from pydantic_evals.evaluators import EvaluatorContext

from lab9.graders import DbFactKept, RefundAmountCorrect, TrialPass
from lab9.trace_case import investigate

pytestmark = pytest.mark.student


@pytest.mark.parametrize("shape,expected_ok", [("seeded_regression", False), ("fixed", True)])
def test_c002_ticket_cannot_override_database(shape, expected_ok):
    case = investigate(shape, "C-002", 11)
    trial = case["trial"]
    label = case["label"]
    context = EvaluatorContext(name=f"{shape}-C-002@11", inputs={}, metadata=None,
                               expected_output=label, output=trial, duration=0.0,
                               _span_tree=None, attributes={}, metrics={})
    assert trial["events"][1]["payload"]["lookup_order"]["order"]["delay_days"] == 2
    assert label["refund_vnd"] == 0
    for grader in (DbFactKept(), RefundAmountCorrect(), TrialPass()):
        assert grader.evaluate(context).value is expected_ok
    assert trial["unexpected_rows"] == 0
    if expected_ok:
        assert not any(e["kind"] == "model_override" for e in trial["events"])
        assert trial["snapshot"]["refund_vnd"] == 0
        assert trial["snapshot"]["refund_count"] == 0
        assert trial["result"]["status"] == "denied"
    else:
        assert trial["events"][2] == {"kind": "model_override", "payload": {"delay_days": 5}}
        assert trial["snapshot"]["refund_vnd"] == 20000
        assert trial["snapshot"]["refund_count"] == 1
        assert trial["result"]["status"] == "resolved"
