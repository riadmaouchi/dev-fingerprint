"""
Probability calibration for the behavioral drift score.

The raw Fisher p-value from compare_recent_vs_historical() is a frequentist
p-value, not a probability of AI assistance.  To produce a calibrated
P(AI-compatible activity | drift observed), we need:

  1. Ground truth labels (see ground_truth.py)
  2. A calibration model trained on labeled profiles

Without ground truth, raw p-values should NEVER be interpreted as
probabilities of AI assistance.  This module provides the infrastructure
to calibrate if/when labeled data becomes available.

Two calibration methods are offered:
  - Platt scaling (logistic regression on log-odds of the score)
  - Isotonic regression (non-parametric, requires more labeled data)

Minimum recommended labeled samples: 30 (15 per class).
With fewer samples, calibration is statistically unsound.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class CalibrationResult:
    method: str
    n_samples: int
    is_valid: bool              # False if insufficient data
    warning: str = ""

    def transform(self, raw_score: float) -> Optional[float]:
        """
        Map a raw Fisher p-value to a calibrated score.

        Returns None if calibration is not valid.
        p-values are inverted: low p (strong drift) → high calibrated score.
        """
        raise NotImplementedError


class PlattCalibration(CalibrationResult):
    """
    Platt scaling: sigmoid fit on (1 - p_value) as the predictor.

    Requires at least 10 positive and 10 negative labeled examples.
    """

    def __init__(self, coef: float, intercept: float, n_samples: int) -> None:
        super().__init__(
            method="platt",
            n_samples=n_samples,
            is_valid=n_samples >= 20,
            warning="" if n_samples >= 20 else f"Only {n_samples} samples — calibration unreliable",
        )
        self._coef = coef
        self._intercept = intercept

    def transform(self, raw_p: float) -> Optional[float]:
        if not self.is_valid:
            return None
        # Feature: (1 - p_value) — high drift → high score
        x = 1.0 - raw_p
        logit = self._coef * x + self._intercept
        return float(1.0 / (1.0 + np.exp(-logit)))


class IsotonicCalibration(CalibrationResult):
    """
    Isotonic regression calibration (non-parametric, monotone).

    Requires at least 30 samples and is sensitive to label noise.
    """

    def __init__(self, x_thresholds: list[float], y_values: list[float], n_samples: int) -> None:
        super().__init__(
            method="isotonic",
            n_samples=n_samples,
            is_valid=n_samples >= 30,
            warning="" if n_samples >= 30 else f"Only {n_samples} samples — isotonic calibration requires ≥30",
        )
        self._x = x_thresholds
        self._y = y_values

    def transform(self, raw_p: float) -> Optional[float]:
        if not self.is_valid:
            return None
        x = 1.0 - raw_p
        return float(np.interp(x, self._x, self._y))


def fit_platt(
    scores: list[float],    # raw Fisher p-values
    labels: list[int],      # 1 = AI-assisted declared, 0 = no-AI declared
) -> PlattCalibration:
    """
    Fit a Platt scaling calibrator.

    labels must be binary (0/1).  Requires at least 20 samples.
    """
    from sklearn.linear_model import LogisticRegression

    n = len(scores)
    if n < 20 or len(set(labels)) < 2:
        return PlattCalibration(coef=1.0, intercept=0.0, n_samples=n)

    X = np.array([[1.0 - s] for s in scores])
    y = np.array(labels)

    lr = LogisticRegression(C=1.0, solver="lbfgs")
    lr.fit(X, y)

    return PlattCalibration(
        coef=float(lr.coef_[0][0]),
        intercept=float(lr.intercept_[0]),
        n_samples=n,
    )


def fit_isotonic(
    scores: list[float],
    labels: list[int],
) -> IsotonicCalibration:
    """
    Fit an isotonic regression calibrator.

    Requires at least 30 samples.
    """
    from sklearn.isotonic import IsotonicRegression

    n = len(scores)
    if n < 30 or len(set(labels)) < 2:
        return IsotonicCalibration(x_thresholds=[0.0, 1.0], y_values=[0.0, 1.0], n_samples=n)

    X = np.array([1.0 - s for s in scores])
    y = np.array(labels, dtype=float)

    ir = IsotonicRegression(out_of_bounds="clip")
    ir.fit(X, y)

    return IsotonicCalibration(
        x_thresholds=list(ir.X_thresholds_),
        y_values=list(ir.y_thresholds_),
        n_samples=n,
    )


def uncalibrated_warning() -> str:
    return (
        "WARNING: No calibration applied. Raw Fisher p-values measure statistical "
        "deviation from the author's historical behavior — they do NOT measure "
        "probability of AI assistance. Without labeled ground truth data, "
        "calibration is impossible. Treat all scores as evidence of behavioral "
        "change only, with AI assistance as one unconfirmed hypothesis."
    )
