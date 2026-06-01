"""
Leave-one-developer-out cross-validation.

The key validation question is:
  "Does the drift detection system fire on developers we KNOW changed behavior,
   and NOT fire on developers we KNOW did not?"

Without ground truth declarations, this reduces to:
  "Does the system detect known confounds (role changes, project phases)
   as false positives?"

This module implements:
  1. LODO (Leave-One-Developer-Out) cross-validation framework
  2. Confusion matrix estimation when labeled data is available
  3. False positive rate estimation from "stable" developers (declared no-AI)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from devfp.models import DevProfile
from devfp.validation.ground_truth import Declaration, get_label


@dataclass
class ValidationResult:
    n_profiles: int
    n_labeled: int               # profiles with ground truth labels
    n_ai_declared: int
    n_no_ai_declared: int

    # Only valid when n_labeled > 0
    true_positives: int = 0
    false_positives: int = 0
    true_negatives: int = 0
    false_negatives: int = 0

    notes: list[str] = field(default_factory=list)

    @property
    def precision(self) -> Optional[float]:
        denom = self.true_positives + self.false_positives
        return self.true_positives / denom if denom > 0 else None

    @property
    def recall(self) -> Optional[float]:
        denom = self.true_positives + self.false_negatives
        return self.true_positives / denom if denom > 0 else None

    @property
    def false_positive_rate(self) -> Optional[float]:
        denom = self.false_positives + self.true_negatives
        return self.false_positives / denom if denom > 0 else None

    def summary(self) -> str:
        lines = [
            f"Profiles evaluated: {self.n_profiles}",
            f"  With ground truth: {self.n_labeled} "
            f"({self.n_ai_declared} AI-declared, {self.n_no_ai_declared} no-AI)",
        ]
        if self.n_labeled > 0:
            lines += [
                f"  True positives:  {self.true_positives}",
                f"  False positives: {self.false_positives}",
                f"  True negatives:  {self.true_negatives}",
                f"  False negatives: {self.false_negatives}",
            ]
            if self.precision is not None:
                lines.append(f"  Precision: {self.precision:.2f}")
            if self.recall is not None:
                lines.append(f"  Recall: {self.recall:.2f}")
            if self.false_positive_rate is not None:
                lines.append(f"  False positive rate: {self.false_positive_rate:.2f}")
        else:
            lines.append(
                "  No ground truth available — confusion matrix cannot be computed.\n"
                "  Add declarations to data/ground_truth/declared.yaml to enable validation."
            )
        for note in self.notes:
            lines.append(f"  Note: {note}")
        return "\n".join(lines)


def evaluate_profiles(
    profiles: list[DevProfile],
    declarations: list[Declaration],
    p_threshold: float = 0.05,
) -> ValidationResult:
    """
    Evaluate drift detection against available ground truth.

    p_threshold: Fisher combined p below which a profile is classified as "drifted".

    A "drifted" profile is NOT the same as "AI-assisted" — it means the statistical
    test detected a behavioral change.  The precision/recall metrics only make sense
    if the ground truth labels represent the BEHAVIORAL change, not AI usage per se.
    """
    result = ValidationResult(
        n_profiles=len(profiles),
        n_labeled=0,
        n_ai_declared=0,
        n_no_ai_declared=0,
    )

    if not declarations:
        result.notes.append(
            "No declarations loaded. Run validation/ground_truth.py to create declared.yaml."
        )
        return result

    for profile in profiles:
        dr = profile.drift_result
        if dr is None:
            result.notes.append(
                f"{profile.github_login}: insufficient data for drift test (skipped)"
            )
            continue

        # Get the label for the most recent period analyzed
        last_date = profile.last_commit_date
        if last_date is None:
            continue

        label = get_label(profile.github_login, last_date, declarations)
        if label is None:
            continue

        result.n_labeled += 1
        predicted_drift = (
            dr.combined_p_value is not None
            and dr.combined_p_value < p_threshold
        )

        if label == "ai_assisted":
            result.n_ai_declared += 1
            if predicted_drift:
                result.true_positives += 1
            else:
                result.false_negatives += 1
        elif label == "no_ai":
            result.n_no_ai_declared += 1
            if predicted_drift:
                result.false_positives += 1
            else:
                result.true_negatives += 1

    return result


def lodo_cross_validate(
    profiles: list[DevProfile],
    declarations: list[Declaration],
    p_threshold: float = 0.05,
) -> list[ValidationResult]:
    """
    Leave-One-Developer-Out (LODO) cross-validation.

    For each developer d:
      - Train: all other developers' behavioral patterns
      - Test: can we correctly classify d?

    Since there is no training step in the current drift detection
    (it is a pure statistical test against the developer's own history),
    LODO here tests for cross-developer consistency:
    - Do developers we know changed behavior all get flagged?
    - Do stable developers all pass?

    Returns one ValidationResult per fold (one per profile).
    """
    results = []
    for i, held_out in enumerate(profiles):
        remaining = [p for j, p in enumerate(profiles) if j != i]
        fold_result = evaluate_profiles([held_out], declarations, p_threshold)
        fold_result.notes.insert(0, f"Held out: {held_out.github_login}")
        results.append(fold_result)
    return results


def stability_analysis(
    profiles: list[DevProfile],
    declarations: list[Declaration],
    p_thresholds: Optional[list[float]] = None,
) -> dict[float, ValidationResult]:
    """
    Evaluate detection sensitivity across multiple p-value thresholds.

    Useful for:
    - Choosing an operating point (precision/recall trade-off)
    - Estimating false positive rate at different sensitivity levels
    """
    if p_thresholds is None:
        p_thresholds = [0.01, 0.05, 0.10, 0.20]

    return {
        threshold: evaluate_profiles(profiles, declarations, p_threshold=threshold)
        for threshold in p_thresholds
    }
