"""
Validation framework for dev-fingerprint.

Modules:
  ground_truth  — Declared AI-assisted commits/periods for calibration datasets
  calibration   — Probability calibration (Platt scaling / isotonic regression)
  cross_validate — Leave-one-developer-out cross-validation

Scientific note:
  Ground truth in this domain is extremely rare.  The only reliable labels
  are self-declarations by developers (e.g. "I used Copilot for this commit").
  Absent such declarations, all labels are assumptions, not ground truth.
"""
