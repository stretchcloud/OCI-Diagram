#!/usr/bin/env python3
"""
premium_metrics.py — reference implementations of the WHOOP paid-tier metrics
that are fully specified in the literature but MISSING from the common libraries.

See ../premium-metrics.md for the full research writeup and citations.

Why this file exists — three things you cannot just pip-install:

  1. BAEVSKY'S STRESS INDEX. Neither NeuroKit2 nor pyhrv implements it.
     NeuroKit2's `HRV_SI` is the *Slope Index* (an HRV asymmetry metric from
     Piskorski & Guzik), NOT Baevsky. Code claiming nk.hrv()["HRV_SI"] is
     Baevsky is wrong. There is also a buggy implementation circulating that
     substitutes the modal-bin COUNT where the modal RR VALUE belongs, and it
     is easy to get the seconds/milliseconds conversion wrong by 10^6.

  2. NIGHTSIGNAL. Stanford's illness-detection FSM (Alavi et al., Nat Med 2022).
     Best sensitivity of their three algorithms (78% vs CuSum 54%, RHRAD 44%);
     alerted 53/68 COVID-positive participants at or before symptom onset,
     median 3 days early. Parameters below are verified against the published
     source (yellow=3 bpm, red=4 bpm, two consecutive nights, EXPANDING-window
     median baseline — not a rolling window).

  3. GOMPERTZ HAZARD-RATIO -> EFFECTIVE AGE. The conversion underlying
     WHOOP Age. Trivial math, but easy to get the constant wrong.

Everything here operates on plain sequences — no BLE, no I/O — so it is unit
testable and drops into whatever pipeline you build.

Requires: Python 3.9+, numpy.       Run `python premium_metrics.py` for a demo.

Not a medical device. Not medical advice. For use with hardware you own.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import median
from typing import Iterable, Sequence

import numpy as np

# ---------------------------------------------------------------------------
# 1. BAEVSKY'S STRESS INDEX
# ---------------------------------------------------------------------------

# Physiologically plausible R-R bounds (ms). 200 ms = 300 bpm, 2500 ms = 24 bpm.
RR_MIN_MS = 200.0
RR_MAX_MS = 2500.0

# Baevsky's histogram bin width. This is part of the definition, not a tunable.
BAEVSKY_BIN_MS = 50.0


def baevsky_stress_index(
    rr_ms: Sequence[float],
    *,
    bin_ms: float = BAEVSKY_BIN_MS,
    use_median_as_mode: bool = True,
) -> float | None:
    """Baevsky's Stress Index (SI) from a window of R-R intervals.

        SI = AMo / (2 * Mo * MxDMn)

        Mo     mode of the RR distribution, in SECONDS
               (Kubios uses the median RR; set use_median_as_mode=False for the
               true histogram mode)
        AMo    "mode amplitude" — PERCENT of RR intervals falling in the modal
               50 ms bin
        MxDMn  max(RR) - min(RR), the variation scope, in SECONDS

    Units matter enormously: Mo and MxDMn must be in seconds. Passing
    milliseconds silently scales SI by 1e6.

    Typical range ~50 to >900. 50-150 = low stress; >500 = high sympathetic
    activation. Kubios feeds sqrt(SI) into its SNS index to tame the right tail
    — see `baevsky_sns_component`.

    Returns None when the window is too short or degenerate (all intervals
    identical => MxDMn == 0), rather than emitting a fabricated number.

    Reference: "Determining autonomic sympathetic tone and reactivity using
    Baevsky's stress index", Am J Physiol Regul Integr Comp Physiol (2024).
    """
    clean = [float(x) for x in rr_ms if RR_MIN_MS <= float(x) <= RR_MAX_MS]
    if len(clean) < 8:  # too few beats for a meaningful histogram
        return None

    arr = np.asarray(clean, dtype=float)

    # MxDMn: variation scope, in seconds.
    mxdmn_s = (arr.max() - arr.min()) / 1000.0
    if mxdmn_s <= 0:  # every interval identical — SI undefined
        return None

    # Mo: modal RR, in seconds.
    if use_median_as_mode:
        mo_s = float(np.median(arr)) / 1000.0
    else:
        edges = np.arange(arr.min(), arr.max() + bin_ms, bin_ms)
        if edges.size < 2:
            return None
        counts, edges = np.histogram(arr, bins=edges)
        idx = int(np.argmax(counts))
        mo_s = float((edges[idx] + edges[idx + 1]) / 2.0) / 1000.0
    if mo_s <= 0:
        return None

    # AMo: PERCENT of intervals inside the modal bin (bin centred on Mo).
    mo_ms = mo_s * 1000.0
    half = bin_ms / 2.0
    in_bin = np.count_nonzero((arr >= mo_ms - half) & (arr < mo_ms + half))
    amo_pct = 100.0 * in_bin / arr.size

    return amo_pct / (2.0 * mo_s * mxdmn_s)


def baevsky_sns_component(rr_ms: Sequence[float]) -> float | None:
    """sqrt(SI) — the transform Kubios applies before using SI as an SNS index.

    SI has a heavy right tail; the square root makes it usable as a z-scored
    feature alongside RMSSD and mean HR.
    """
    si = baevsky_stress_index(rr_ms)
    return None if si is None else math.sqrt(si)


def rmssd(rr_ms: Sequence[float]) -> float | None:
    """RMSSD (ms) — the vagal/parasympathetic workhorse.

    Included so the stress score below is self-contained. For production use
    NeuroKit2's hrv_time() and, importantly, run artifact correction first:
    nk.signal_fixpeaks(peaks, method="Kubios")  [Lipponen & Tarvainen 2019].
    """
    clean = [float(x) for x in rr_ms if RR_MIN_MS <= float(x) <= RR_MAX_MS]
    if len(clean) < 2:
        return None
    diffs = np.diff(np.asarray(clean, dtype=float))
    return float(np.sqrt(np.mean(diffs**2)))


# ---------------------------------------------------------------------------
# 2. NIGHTSIGNAL — illness / anomaly detection from nightly resting HR
# ---------------------------------------------------------------------------

# Verified against Stanford's published nightsignal.py.
NIGHTSIGNAL_YELLOW_BPM = 3.0
NIGHTSIGNAL_RED_BPM = 4.0

GREEN, YELLOW, RED = 0, 1, 2
_STATE_NAME = {GREEN: "green", YELLOW: "yellow", RED: "red"}

# RHR is computed only from these local hours, and only where steps == 0.
NIGHTSIGNAL_HOURS = (0, 1, 2, 3, 4, 5, 6)


def nightly_resting_hr(
    samples: Iterable[tuple[int, float, float]],
) -> float | None:
    """Nightly resting HR, per NightSignal's definition.

    `samples` is an iterable of (hour_of_day, heart_rate_bpm, step_count).
    Takes the mean HR over samples where steps == 0 and the hour falls in
    00:00-06:59 local. Returns None if nothing qualifies.
    """
    vals = [
        hr
        for hour, hr, steps in samples
        if hour in NIGHTSIGNAL_HOURS and steps == 0 and hr and hr > 0
    ]
    return float(np.mean(vals)) if vals else None


def impute_single_day_gaps(series: Sequence[float | None]) -> list[float | None]:
    """Fill isolated missing days with the mean of their two neighbours.

    NightSignal fills ONLY single-day gaps; two-day gaps are left alone.
    """
    out = list(series)
    for i in range(1, len(out) - 1):
        if out[i] is None and out[i - 1] is not None and out[i + 1] is not None:
            out[i] = (out[i - 1] + out[i + 1]) / 2.0
    return out


def nightsignal(
    nightly_rhr: Sequence[float | None],
    *,
    yellow_bpm: float = NIGHTSIGNAL_YELLOW_BPM,
    red_bpm: float = NIGHTSIGNAL_RED_BPM,
) -> list[int]:
    """NightSignal alert states for a series of nightly resting-HR values.

    Returns one of GREEN / YELLOW / RED per day.

      RED    RHR >= baseline + 4 bpm on TWO CONSECUTIVE nights
      YELLOW RHR >= baseline + 3 bpm on TWO CONSECUTIVE nights (and not red)
      GREEN  otherwise

    The baseline is the median of ALL prior nightly values INCLUDING today —
    an EXPANDING window, not a rolling one. This matters: a rolling window
    lets a slow drift redefine "normal" and the alert never fires.

    Sensitivity ~78% for pre-symptomatic COVID detection, median 3 days before
    symptom onset (Alavi et al., Nat Med 2022). It also fires on vaccination,
    alcohol, hard training and hot bedrooms — see premium-metrics.md §4.4, and
    prefer the 2-of-4-channel confirmation rule described there.
    """
    filled = impute_single_day_gaps(nightly_rhr)
    states: list[int] = []
    history: list[float] = []
    prev_yellow = prev_red = False

    for value in filled:
        if value is None:
            states.append(GREEN)
            prev_yellow = prev_red = False
            continue

        history.append(float(value))
        baseline = median(history)  # expanding window, includes today

        over_red = value >= baseline + red_bpm
        over_yellow = value >= baseline + yellow_bpm

        if over_red and prev_red:
            state = RED
        elif over_yellow and prev_yellow:
            state = YELLOW
        else:
            state = GREEN

        states.append(state)
        prev_red, prev_yellow = over_red, over_yellow

    return states


def state_name(state: int) -> str:
    return _STATE_NAME.get(state, "unknown")


# ---------------------------------------------------------------------------
# 3. GOMPERTZ: HAZARD RATIO -> EFFECTIVE AGE (the WHOOP Age conversion)
# ---------------------------------------------------------------------------

# WHOOP's disclosed rule: "a 10% increase in mortality risk ~= one year of
# effective age." That fixes alpha = ln(1.10) = 0.0953/yr, implying a
# mortality-rate doubling time of ~7.27 years. The demographic MRDT is ~8 yr
# (alpha = 0.0866). Both are provided; WHOOP's is the default so results match
# their published worked examples.
ALPHA_WHOOP = math.log(1.10)          # 0.0953 /yr
ALPHA_GOMPERTZ_8YR = math.log(2) / 8  # 0.0866 /yr


def hazard_ratio_to_years(hazard_ratio: float, *, alpha: float = ALPHA_WHOOP) -> float:
    """Convert an all-cause-mortality hazard ratio to years of effective age.

        delta_age = ln(HR) / alpha

    Positive = ages you; negative = makes you younger.

    Reproduces WHOOP's published examples:
        HR 1.22 -> +2.09 yr ("two years")
        HR 0.85 -> -1.70 yr (they say "about one and a half" — they round)
    """
    if hazard_ratio <= 0:
        raise ValueError("hazard_ratio must be positive")
    return math.log(hazard_ratio) / alpha


@dataclass
class AgeContributor:
    """One input to a WHOOP-Age-style composite.

    `overlap_correction` shrinks a contributor to avoid double-counting
    correlated habits (WHOOP fits this with a structural equation model; 1.0
    means no correction). Set it deliberately — leaving everything at 1.0
    overstates the total.
    """

    name: str
    hazard_ratio: float
    overlap_correction: float = 1.0

    def years(self, *, alpha: float = ALPHA_WHOOP) -> float:
        return hazard_ratio_to_years(self.hazard_ratio, alpha=alpha) * self.overlap_correction


@dataclass
class EffectiveAgeResult:
    chronological_age: float
    effective_age: float
    breakdown: dict[str, float] = field(default_factory=dict)

    @property
    def delta(self) -> float:
        return self.effective_age - self.chronological_age


def effective_age(
    chronological_age: float,
    contributors: Sequence[AgeContributor],
    *,
    alpha: float = ALPHA_WHOOP,
) -> EffectiveAgeResult:
    """A WHOOP-Age-style composite: chronological age + summed hazard effects.

    LABEL THE OUTPUT HONESTLY. This is a heuristic composite of published
    mortality associations — not a validated biological age. Real biological-age
    clocks (PhenoAge, DunedinPACE) require blood chemistry or DNA methylation
    and cannot be computed from a wearable. See premium-metrics.md §3.4.
    """
    breakdown = {c.name: c.years(alpha=alpha) for c in contributors}
    return EffectiveAgeResult(
        chronological_age=chronological_age,
        effective_age=chronological_age + sum(breakdown.values()),
        breakdown=breakdown,
    )


# ---------------------------------------------------------------------------
# 4. VO2MAX — HUNT / Nes 2011 non-exercise model
# ---------------------------------------------------------------------------

def vo2max_hunt(
    *,
    age: float,
    sex: str,
    waist_cm: float,
    resting_hr: float,
    pa_index: float,
) -> float:
    """Estimated VO2peak (ml/kg/min), HUNT non-exercise model (Nes et al. 2011).

        Men:   100.27 - 0.296*age + 0.226*PA-I - 0.369*waist - 0.155*RHR   SEE ~5.70
        Women:  74.74 - 0.247*age + 0.198*PA-I - 0.259*waist - 0.114*RHR   SEE ~5.14

    pa_index is the HUNT physical-activity index (0-15) = weekly frequency
    (0-5) x duration (0.10-1.00) x intensity (1-3). Derive it from HR-zone
    minutes by mapping low/medium/high intensity to 44%/73%/83% of heart-rate
    reserve.

    !! CALIBRATION TRAP: HUNT's RHR was a SEATED CLINIC measurement, not a
    nocturnal sleeping HR. Your band's nocturnal RHR is meaningfully lower and,
    with a negative coefficient, INFLATES the estimate. Pass a seated resting
    HR, or apply and document a fixed offset.

    Coefficients agree across five independent implementations but were not
    verified against the paper directly — confirm at PMID 21502897.
    """
    s = sex.strip().lower()
    if s in ("m", "male"):
        return 100.27 - 0.296 * age + 0.226 * pa_index - 0.369 * waist_cm - 0.155 * resting_hr
    if s in ("f", "female"):
        return 74.74 - 0.247 * age + 0.198 * pa_index - 0.259 * waist_cm - 0.114 * resting_hr
    raise ValueError("sex must be 'male' or 'female'")


def vo2max_hr_ratio(hr_max: float, hr_rest: float) -> float:
    """Uth-Sorensen Heart Rate Ratio method: VO2max ~= 15 * (HRmax / HRrest).

    Cheapest possible estimate — needs only two heart rates. But: HRmax must be
    a genuine MEASURED maximum (not 220-age), HRrest carries the same
    seated-vs-nocturnal caveat as above, and validity is population-dependent
    (derived in well-trained subjects). Use as a cross-check on vo2max_hunt,
    not as a primary estimate.
    """
    if hr_rest <= 0:
        raise ValueError("hr_rest must be positive")
    return 15.0 * (hr_max / hr_rest)


# ---------------------------------------------------------------------------
# 5. SLEEP REGULARITY INDEX
# ---------------------------------------------------------------------------

def sleep_regularity_index(hypnogram: Sequence[Sequence[int]]) -> float | None:
    """Sleep Regularity Index (Phillips et al., Sci Rep 2017).

        SRI = -100 + (200 / (M*(N-1))) * sum_ij delta(s_ij, s_i+1,j)

    `hypnogram` is N days x M epochs of binary state (1 = sleep, 0 = wake),
    conventionally 30 s epochs (M = 2880). Returns -100..100; 100 = perfectly
    regular, 0 = random.

    Sleep regularity is a STRONGER all-cause-mortality predictor than sleep
    duration (Windred et al., Sleep 2024): HR 1.53 at the 5th percentile vs
    median, 0.90 at the 95th.

    Note: SRI values differ between published implementations (pyActigraphy,
    GGIR, sleepreg). Pick one and stay with it.
    """
    days = [list(d) for d in hypnogram]
    if len(days) < 2:
        return None
    m = len(days[0])
    if m == 0 or any(len(d) != m for d in days):
        return None

    n = len(days)
    matches = sum(
        1
        for i in range(n - 1)
        for j in range(m)
        if days[i][j] == days[i + 1][j]
    )
    return -100.0 + (200.0 / (m * (n - 1))) * matches


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

def _demo() -> None:
    rng = np.random.default_rng(42)

    print("=" * 68)
    print("1. BAEVSKY STRESS INDEX")
    print("=" * 68)
    # Relaxed: ~60 bpm with healthy beat-to-beat variability.
    relaxed = 1000 + rng.normal(0, 45, 300)
    # Stressed: faster, and markedly less variable (vagal withdrawal).
    stressed = 750 + rng.normal(0, 12, 300)
    for label, rr in (("relaxed", relaxed), ("stressed", stressed)):
        si = baevsky_stress_index(rr)
        print(
            f"  {label:9s} SI={si:8.1f}  sqrt(SI)={math.sqrt(si):6.2f}  "
            f"RMSSD={rmssd(rr):6.1f} ms"
        )
    print("  (higher SI = more sympathetic activation; 50-150 low, >500 high)")

    print()
    print("=" * 68)
    print("2. NIGHTSIGNAL")
    print("=" * 68)
    # 14 quiet nights ~55 bpm, then a sustained elevation from night 15.
    nights = [55.0 + rng.normal(0, 0.6) for _ in range(14)]
    nights += [60.0, 61.5, 62.0, 59.5, 56.0, 55.2]
    for day, (rhr, st) in enumerate(zip(nights, nightsignal(nights)), start=1):
        flag = "" if st == GREEN else "   <-- ALERT"
        print(f"  night {day:2d}  RHR {rhr:5.1f} bpm   {state_name(st):6s}{flag}")

    print()
    print("=" * 68)
    print("3. HAZARD RATIO -> EFFECTIVE AGE")
    print("=" * 68)
    print("  WHOOP's published examples, reproduced:")
    for hr in (1.22, 0.85, 1.10):
        print(f"    HR {hr:4.2f}  ->  {hazard_ratio_to_years(hr):+5.2f} years")

    res = effective_age(
        38,
        [
            # Illustrative only — substitute hazard ratios you have verified.
            AgeContributor("resting_hr", 0.95, overlap_correction=0.9),
            AgeContributor("sleep_regularity", 0.90),
            AgeContributor("steps", 0.85, overlap_correction=0.7),
            AgeContributor("vo2max", 0.88, overlap_correction=0.8),
        ],
    )
    print(f"\n  chronological: {res.chronological_age:.1f}")
    print(f"  effective:     {res.effective_age:.1f}  ({res.delta:+.1f} yr)")
    for name, yrs in res.breakdown.items():
        print(f"    {name:20s} {yrs:+5.2f} yr")
    print("  (heuristic composite — NOT a validated biological age)")

    print()
    print("=" * 68)
    print("4. VO2MAX + FITNESS")
    print("=" * 68)
    v = vo2max_hunt(age=38, sex="male", waist_cm=86, resting_hr=62, pa_index=9.0)
    print(f"  HUNT/Nes non-exercise: {v:.1f} ml/kg/min  (SEE ~5.7)")
    print(f"  Uth HR-ratio check:    {vo2max_hr_ratio(188, 62):.1f} ml/kg/min")
    print("  (pass a SEATED resting HR, not the band's nocturnal RHR)")

    print()
    print("=" * 68)
    print("5. SLEEP REGULARITY INDEX")
    print("=" * 68)
    epochs = 48  # coarse demo grid
    regular = [[1 if 0 <= j < 16 else 0 for j in range(epochs)] for _ in range(7)]
    irregular = [
        [1 if (j + 5 * i) % epochs < 16 else 0 for j in range(epochs)]
        for i in range(7)
    ]
    print(f"  consistent schedule: SRI = {sleep_regularity_index(regular):6.1f}")
    print(f"  shifting schedule:   SRI = {sleep_regularity_index(irregular):6.1f}")
    print("  (stronger mortality predictor than sleep duration)")


if __name__ == "__main__":
    _demo()
