"""M2 calibration boundaries and rejection of the overly lenient judge."""

from pathlib import Path

import pytest

from lab9 import stats
from lab9.judge import calibrate

pytestmark = pytest.mark.student


def test_confusion_counts_fail_as_positive():
    assert stats.confusion(["FAIL", "PASS", "FAIL", "PASS"],
                           ["FAIL", "FAIL", "PASS", "PASS"]) == {
                               "tp": 1, "fp": 1, "fn": 1, "tn": 1}


def test_empty_and_zero_denominators():
    assert stats.precision_recall([], []) == (0.0, 0.0)
    assert stats.precision_recall(["FAIL"], ["PASS"]) == (0.0, 0.0)
    with pytest.raises(ValueError):
        stats.cohen_kappa([], [])


@pytest.mark.parametrize("human,judge", [(["FAIL"], []), (["UNKNOWN"], ["PASS"])])
def test_invalid_labels_rejected(human, judge):
    with pytest.raises(ValueError):
        stats.confusion(human, judge)


def test_kappa_perfect_and_opposite():
    assert stats.cohen_kappa(["PASS", "FAIL"], ["PASS", "FAIL"]) == 1.0
    assert stats.cohen_kappa(["PASS", "FAIL"], ["FAIL", "PASS"]) == -1.0


def test_rogan_gladen_upper_clip_and_undefined():
    assert stats.rogan_gladen(1.0, 0.8, 0.9) == 1.0
    with pytest.raises(ValueError):
        stats.rogan_gladen(0.5, 0.5, 0.5)
    with pytest.raises(ValueError):
        stats.rogan_gladen(float("nan"), 0.8, 0.9)


def test_helpful_judge_must_not_pass_calibration():
    result = calibrate(Path("data/eval/judge_helpful_public.csv"))
    assert result["confusion"] == {"tp": 9, "fp": 0, "fn": 21, "tn": 70}
    assert result["precision"] == 1.0
    assert result["recall"] == 0.3
    assert result["kappa"] == 0.375
    assert result["passed"] is False
