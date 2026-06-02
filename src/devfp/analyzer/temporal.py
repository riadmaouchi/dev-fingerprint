"""
Behavioral drift detection on BehaviorWindow time series.

Four change-point detection methods are implemented:
  - PELT (Pruned Exact Linear Time) via stylometry.stats — parametric, best for
    clean series with a single dominant shift.
  - CUSUM (Cumulative Sum Control Chart) — sequential, sensitive to gradual drift.
  - EWMA (Exponentially Weighted Moving Average) — continuous, early warning.
  - BOCPD (Bayesian Online Change Point Detection, Adams & MacKay 2007) —
    Bayesian, maintains full posterior over run lengths, no threshold tuning needed.

The self-comparison test (compare_recent_vs_historical) uses Mann-Whitney U,
which is non-parametric and does not assume normality — appropriate for small
sample sizes (4-12 quarterly windows per author).
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Optional

import numpy as np
from scipy import stats as scipy_stats
from scipy.special import logsumexp
from scipy.stats import combine_pvalues

from stylometry.stats import detect_change_points as _pelt_detect

from devfp.models import (
    BehaviorWindow,
    ChangePoint,
    DriftResult,
    LLM_MILESTONES,
    SIGNAL_LEVELS,
    SignalDrift,
)

# Signals on which change-point detection and drift tests are run by default.
# Level A signals are run for all methods; Level B/C are PELT-only.
_DEFAULT_SIGNALS = [
    # Level A
    "median_files_per_commit",
    "large_commit_ratio",
    "cross_module_ratio",
    "refactor_ratio",
    "median_inter_commit_hours",
    "commits_per_week",
    # Level B
    "test_touch_ratio",
    "median_net_lines",
    "merge_ratio",
    "patch_comment_density",
    "patch_blank_line_ratio",
    # Level C (kept for baseline comparison)
    "style_score",
]


# ── Change-point detection ─────────────────────────────────────────────────────

def _cusum_detect(
    series: list[float],
    k: float = 0.5,
    h: float = 5.0,
) -> list[int]:
    """
    CUSUM (one-sided, both directions) change-point detection.

    Initializes reference mean and std from the first half of the series.
    k: allowance (slack), typically 0.5
    h: decision threshold, typically 4–5
    Returns indices where an alarm fires (resets after each alarm).
    """
    n = len(series)
    if n < 4:
        return []

    arr = np.asarray(series, dtype=float)
    init_n = max(n // 2, 2)
    mu = float(np.mean(arr[:init_n]))
    sigma = max(float(np.std(arr[:init_n])), 1e-9)

    s_pos = s_neg = 0.0
    alarms: list[int] = []

    for i in range(1, n):
        z = (arr[i] - mu) / sigma
        s_pos = max(0.0, s_pos + z - k)
        s_neg = max(0.0, s_neg - z - k)
        if s_pos > h or s_neg > h:
            alarms.append(i)
            s_pos = s_neg = 0.0

    return alarms


def _ewma_detect(
    series: list[float],
    lambda_: float = 0.2,
    l_factor: float = 3.0,
) -> list[int]:
    """
    EWMA (Exponentially Weighted Moving Average) control chart.

    Initializes from the first half; monitors the second half for out-of-control points.
    lambda_: smoothing parameter (0.1–0.3 typical)
    l_factor: control limit in sigma units (3.0 = 3-sigma)
    Returns indices of out-of-control observations.
    """
    n = len(series)
    if n < 4:
        return []

    arr = np.asarray(series, dtype=float)
    init_n = max(n // 2, 2)
    mu = float(np.mean(arr[:init_n]))
    sigma = max(float(np.std(arr[:init_n])), 1e-9)

    # Steady-state control limits
    cl = l_factor * sigma * math.sqrt(lambda_ / (2.0 - lambda_))
    ucl, lcl = mu + cl, mu - cl

    z = mu
    alarms: list[int] = []
    for i in range(init_n, n):
        z = lambda_ * arr[i] + (1.0 - lambda_) * z
        if z > ucl or z < lcl:
            alarms.append(i)

    return alarms


def _bocpd_detect(
    series: list[float],
    hazard: float = 1 / 15,
    threshold: float = 0.25,
    kappa0: float = 1.0,
    alpha0: float = 2.0,
) -> list[int]:
    """
    Bayesian Online Change Point Detection (Adams & MacKay 2007).

    Models each "run" (period between change points) as Gaussian with a
    Normal-Inverse-Gamma conjugate prior.  At each step t the posterior over
    run length r is updated; an alarm fires when P(r=0 at t) > threshold.

    hazard:    1 / expected_run_length.  Default 1/15 ≈ a change every 4 years
               of quarterly data — conservative for developer timeseries.
    threshold: P(change point at t) required to fire an alarm (0.35 = lenient).
    kappa0:    prior pseudo-count for the mean (higher → stronger prior pull).
    alpha0:    prior shape for the variance (≥2 keeps the prior proper).

    Returns indices where an alarm fires.  Index 0 is never returned (no
    predecessor to compare against).
    """
    n = len(series)
    if n < 4:
        return []

    arr = np.asarray(series, dtype=float)
    mu0 = float(np.mean(arr))
    # Scale beta0 so the prior predictive has the same variance as the data.
    beta0 = float(np.var(arr)) * alpha0 if float(np.var(arr)) > 0 else alpha0

    log_hazard = math.log(hazard)
    log_1mhazard = math.log(1.0 - hazard)

    # Run-length distribution in log space; at t=0 run length = 0 with prob 1.
    log_R = np.array([0.0])

    # Sufficient statistics per active run length (Normal-Inverse-Gamma).
    kappa = np.array([kappa0])
    mu_r = np.array([mu0])
    alpha = np.array([alpha0])
    beta = np.array([beta0])

    alarms: list[int] = []

    for t in range(n):
        x = arr[t]

        # Predictive for each active run: Student-t(2α, μ, sqrt(β(κ+1)/(ακ)))
        df = 2.0 * alpha
        scale = np.sqrt(beta * (kappa + 1.0) / (alpha * kappa))
        log_pred = scipy_stats.t.logpdf(x, df=df, loc=mu_r, scale=scale)

        # Growth mass: (1-H) * P(x | run r) * P(run r)
        # Skip r=0 entry (the fresh-run placeholder); active runs are indices 1..
        log_growth = log_R + log_pred + log_1mhazard

        # Change-point mass: P(x | prior) * H * sum_r P(r_{t-1}=r)
        # log_R is normalized → logsumexp(log_R) = 0
        log_pred_prior = log_pred[0]   # index 0 always holds the prior params
        log_cp = log_pred_prior + log_hazard  # + logsumexp(log_R) = 0

        new_log_R = np.empty(len(log_growth) + 1)
        new_log_R[0] = log_cp
        new_log_R[1:] = log_growth

        # Normalize
        log_norm = logsumexp(new_log_R)
        new_log_R -= log_norm

        # Alarm: high posterior probability of a fresh run starting at t
        if t > 0 and math.exp(new_log_R[0]) > threshold:
            alarms.append(t)

        # Update sufficient statistics for each run length (Bayesian update).
        new_kappa = kappa + 1.0
        new_mu = (kappa * mu_r + x) / new_kappa
        new_alpha = alpha + 0.5
        new_beta = beta + (kappa * (x - mu_r) ** 2) / (2.0 * (kappa + 1.0))

        # Prepend prior for the change-point run (r=0 → no history).
        kappa = np.empty(len(new_kappa) + 1)
        mu_r = np.empty_like(kappa)
        alpha = np.empty_like(kappa)
        beta = np.empty_like(kappa)

        kappa[0], mu_r[0], alpha[0], beta[0] = kappa0, mu0, alpha0, beta0
        kappa[1:] = new_kappa
        mu_r[1:] = new_mu
        alpha[1:] = new_alpha
        beta[1:] = new_beta

        log_R = new_log_R

    return alarms


def detect_change_points(
    author: str,
    windows: list[BehaviorWindow],
    signals: Optional[list[str]] = None,
    methods: list[str] | None = None,
    min_size: int = 3,
    penalty: float = 3.0,
    min_magnitude_pct: float = 0.15,
) -> list[ChangePoint]:
    """
    Detect behavioral change points across multiple signals and methods.

    signals: which BehaviorWindow fields to analyze (default: _DEFAULT_SIGNALS)
    methods: ["pelt", "cusum", "ewma", "bocpd"] — default: ["pelt", "cusum"]
    min_magnitude_pct: minimum relative change to count as a change point
                       (|delta| / max(|baseline|, 1e-6) > threshold)

    Returns deduplicated ChangePoint objects, sorted by date.
    """
    if len(windows) < min_size * 2:
        return []

    if signals is None:
        signals = _DEFAULT_SIGNALS
    if methods is None:
        methods = ["pelt", "cusum"]

    sorted_windows = sorted(windows, key=lambda w: w.period_start)
    result: list[ChangePoint] = []

    for signal in signals:
        if not hasattr(sorted_windows[0], signal):
            continue

        level = SIGNAL_LEVELS.get(signal, "C")
        series = [float(getattr(w, signal)) for w in sorted_windows]

        # Collect alarm indices from each method
        alarm_indices: set[int] = set()

        if "pelt" in methods:
            try:
                raw = _pelt_detect(series, min_size=min_size, penalty=penalty, min_magnitude=0.0)
                alarm_indices.update(cp["index"] for cp in raw)
            except Exception:
                pass

        if "cusum" in methods:
            alarm_indices.update(_cusum_detect(series))

        if "ewma" in methods:
            alarm_indices.update(_ewma_detect(series))

        if "bocpd" in methods:
            alarm_indices.update(_bocpd_detect(series))

        for idx in sorted(alarm_indices):
            if idx == 0 or idx >= len(sorted_windows):
                continue

            before = float(np.mean(series[:idx]))
            after = float(np.mean(series[idx:]))
            magnitude = abs(after - before)
            baseline = max(abs(before), 1e-9)

            if magnitude / baseline < min_magnitude_pct:
                continue

            # Determine which methods detected this index
            method_tags: list[str] = []
            if "pelt" in methods:
                try:
                    raw = _pelt_detect(series, min_size=min_size, penalty=penalty, min_magnitude=0.0)
                    if any(cp["index"] == idx for cp in raw):
                        method_tags.append("pelt")
                except Exception:
                    pass
            if "cusum" in methods and idx in set(_cusum_detect(series)):
                method_tags.append("cusum")
            if "ewma" in methods and idx in set(_ewma_detect(series)):
                method_tags.append("ewma")
            if "bocpd" in methods and idx in set(_bocpd_detect(series)):
                method_tags.append("bocpd")

            bkp_date = sorted_windows[idx].period_start
            result.append(ChangePoint(
                author=author,
                date=bkp_date,
                signal=signal,
                signal_level=level,
                value_before=round(before, 4),
                value_after=round(after, 4),
                magnitude=round(magnitude, 4),
                detection_method="+".join(method_tags) if method_tags else "multi",
                nearest_known_event=_nearest_known_event(bkp_date),
            ))

    result.sort(key=lambda cp: (cp.date, cp.signal))
    return result


def _nearest_known_event(dt: datetime, max_delta_days: int = 180) -> Optional[str]:
    """
    Post-hoc annotation: find the nearest LLM milestone within max_delta_days.

    This is NEVER used to locate change points — only to label them after detection.
    """
    best_label: Optional[str] = None
    best_delta = float("inf")
    dt_naive = dt.replace(tzinfo=None) if dt.tzinfo else dt

    for label, milestone_dt in LLM_MILESTONES.items():
        delta = abs((dt_naive - milestone_dt).days)
        if delta < best_delta and delta <= max_delta_days:
            best_delta = delta
            best_label = f"{label} ({milestone_dt.strftime('%Y-%m')})"

    return best_label


# ── Statistical self-comparison ────────────────────────────────────────────────

def compare_recent_vs_historical(
    author: str,
    windows: list[BehaviorWindow],
    signals: Optional[list[str]] = None,
    recent_n: int = 4,
    min_historical: int = 6,
    change_points: Optional[list[ChangePoint]] = None,
) -> Optional[DriftResult]:
    """
    Test whether the developer's recent behavior differs from their own historical baseline.

    Methodology:
      - "Historical" = all windows except the most recent `recent_n`
      - "Recent" = the last `recent_n` windows
      - Test: Mann-Whitney U (non-parametric, no normality assumption)
      - Combined p-value: Fisher's method over Level A signals only

    This is the core scientific claim: H0 = recent windows are drawn from the same
    distribution as historical windows.  Rejecting H0 is NOT equivalent to claiming
    AI assistance — it means the process changed, with AI assistance as one hypothesis.

    Returns None when there is insufficient data (< recent_n + min_historical windows).
    """
    sorted_w = sorted(windows, key=lambda w: w.period_start)
    total = len(sorted_w)

    if total < recent_n + min_historical:
        return None

    if signals is None:
        signals = _DEFAULT_SIGNALS

    historical_windows = sorted_w[:total - recent_n]
    recent_windows = sorted_w[total - recent_n:]

    signal_drifts: list[SignalDrift] = []

    for signal in signals:
        if not hasattr(sorted_w[0], signal):
            continue

        level = SIGNAL_LEVELS.get(signal, "C")
        hist_vals = [float(getattr(w, signal)) for w in historical_windows]
        rec_vals = [float(getattr(w, signal)) for w in recent_windows]

        hist_mean = float(np.mean(hist_vals))
        rec_mean = float(np.mean(rec_vals))
        delta = rec_mean - hist_mean
        baseline = max(abs(hist_mean), 1e-9)
        delta_pct = delta / baseline * 100.0

        p_value: Optional[float] = None
        if len(hist_vals) >= 3 and len(rec_vals) >= 2:
            try:
                _, pval = scipy_stats.mannwhitneyu(
                    hist_vals, rec_vals, alternative="two-sided"
                )
                p_value = float(pval)
            except ValueError:
                pass

        cp_detected = bool(
            change_points and any(
                cp.signal == signal
                for cp in change_points
                if cp.date >= recent_windows[0].period_start
            )
        )

        signal_drifts.append(SignalDrift(
            signal=signal,
            signal_level=level,
            baseline_mean=round(hist_mean, 4),
            recent_mean=round(rec_mean, 4),
            delta=round(delta, 4),
            delta_pct=round(delta_pct, 1),
            p_value=round(p_value, 4) if p_value is not None else None,
            significant_at_05=p_value is not None and p_value < 0.05,
            change_point_detected=cp_detected,
            direction="increase" if delta > 0.01 else "decrease" if delta < -0.01 else "stable",
        ))

    # Fisher's combined p-value — Level A signals only
    level_a_pvals = [
        sd.p_value for sd in signal_drifts
        if sd.signal_level == "A" and sd.p_value is not None
    ]
    combined_p: Optional[float] = None
    if len(level_a_pvals) >= 2:
        try:
            _, combined_p = combine_pvalues(level_a_pvals, method="fisher")
            combined_p = float(combined_p)
        except Exception:
            pass
    elif len(level_a_pvals) == 1:
        combined_p = level_a_pvals[0]

    interpretation = _build_interpretation(
        author, signal_drifts, combined_p, len(historical_windows), recent_n
    )

    return DriftResult(
        author=author,
        n_windows_baseline=len(historical_windows),
        n_windows_recent=recent_n,
        signals=signal_drifts,
        combined_p_value=round(combined_p, 4) if combined_p is not None else None,
        interpretation=interpretation,
    )


def _build_interpretation(
    author: str,
    signals: list[SignalDrift],
    combined_p: Optional[float],
    n_baseline: int,
    n_recent: int,
) -> str:
    """
    Generate a probabilistic, academically defensible interpretation string.

    Deliberately avoids asserting AI causation.
    """
    n_significant_a = sum(
        1 for s in signals
        if s.signal_level == "A" and s.significant_at_05
    )
    n_total_a = sum(1 for s in signals if s.signal_level == "A")

    if combined_p is None:
        return (
            f"{author}: Insufficient data for statistical inference "
            f"({n_baseline} baseline + {n_recent} recent windows)."
        )

    if combined_p > 0.10 or n_significant_a == 0:
        return (
            f"{author}: No statistically significant behavioral drift detected "
            f"(Fisher p={combined_p:.3f}, {n_significant_a}/{n_total_a} Level A signals significant). "
            f"H₀ (author behaves consistently with historical baseline) cannot be rejected."
        )
    elif combined_p < 0.01:
        sig_names = [s.signal for s in signals if s.signal_level == "A" and s.significant_at_05]
        return (
            f"{author}: Strong behavioral drift detected (Fisher p={combined_p:.4f}). "
            f"{n_significant_a}/{n_total_a} Level A process signals shifted: {', '.join(sig_names)}. "
            f"The recent development pattern is statistically inconsistent with historical baseline. "
            f"AI assistance is one compatible hypothesis — confounds include role change, "
            f"project phase, new tooling, team size, and natural career evolution."
        )
    else:
        return (
            f"{author}: Moderate behavioral drift detected (Fisher p={combined_p:.4f}). "
            f"{n_significant_a}/{n_total_a} Level A signals show nominal significance. "
            f"The evidence is consistent with a process change but is not conclusive. "
            f"AI assistance cannot be confirmed or excluded from this signal alone."
        )


# ── Legacy function (kept for backward compatibility) ─────────────────────────

def compute_drift(windows: list[BehaviorWindow]) -> dict[str, float]:
    """
    Simple pre/post Copilot GA drift on style_score (Level C).

    Kept for backward compatibility with the HTML reporter.
    For scientifically defensible drift analysis, use compare_recent_vs_historical().
    """
    sorted_w = sorted(windows, key=lambda w: w.period_start)
    split = next(
        (i for i, w in enumerate(sorted_w)
         if w.period_start.year > 2022
         or (w.period_start.year == 2022 and w.period_start.month >= 6)),
        len(sorted_w),
    )
    pre = [w.style_score for w in sorted_w[:split]]
    post = [w.style_score for w in sorted_w[split:]]

    result: dict[str, float] = {}
    if pre:
        result["baseline_mean"] = round(float(np.mean(pre)), 2)
    if post:
        result["post_llm_mean"] = round(float(np.mean(post)), 2)
    if pre and post:
        result["drift"] = round(float(np.mean(post)) - float(np.mean(pre)), 2)
    return result


# Kept for tests
_nearest_milestone = _nearest_known_event
