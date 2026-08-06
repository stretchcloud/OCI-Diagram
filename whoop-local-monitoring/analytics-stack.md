# Local Analytics Stack — rebuilding WHOOP-style metrics from raw signals

Once you're pulling raw data off the band ([../README.md §7](./README.md#7-the-whoop-ble-protocol-reference)),
this is the open-source toolkit for turning it into the metrics WHOOP sells. Everything here
reproduces **published science**, not WHOOP's proprietary formulas — expect offsets from the
app's numbers, and validate against how you actually feel and perform.

**Your raw inputs** (from the `R24` record and live streams): heart rate (bpm), R-R /
inter-beat intervals (ms), raw green + red/IR PPG ADC, 3-axis accelerometer (g), and
*uncalibrated* skin-temp / SpO₂ ADC counts.

---

## 1. Heart rate from PPG

- **Concept:** band-pass filter the PPG (~0.5–4 Hz) → detect systolic peaks → peak-to-peak
  interval → BPM.
- **Libraries:** [HeartPy](https://python-heart-rate-analysis-toolkit.readthedocs.io/)
  (`heartpy.process(data, sample_rate)`; adaptive threshold, built for noisy wrist/camera
  PPG) · [NeuroKit2](https://github.com/neuropsychology/NeuroKit) (`nk.ppg_process`) ·
  [SciPy](https://docs.scipy.org/doc/scipy/reference/signal.html) (`butter`+`filtfilt`,
  `find_peaks`).
- **Tip:** prefer the band's own **R-R intervals** when present — cleaner than re-detecting
  beats from raw PPG. Reserve PPG peak detection for quality-checking or gap-filling.

## 2. Heart rate variability (HRV) — the backbone of "recovery"

- **Concept:** on the NN (artifact-corrected R-R) series compute **RMSSD**, **SDNN**,
  **pNN50** (time domain) and LF/HF (frequency). RMSSD reflects vagal/parasympathetic tone;
  **RMSSD in deep sleep, `ln`-transformed (lnRMSSD)**, is the standard recovery signal.
- **Artifact-correct FIRST** — one missed/extra beat wrecks HRV.
- **Libraries:** [`hrv-analysis`](https://github.com/Aura-healthcare/hrv-analysis) (Aura —
  explicit `remove_outliers`, `remove_ectopic_beats`, then `get_time_domain_features`) ·
  [NeuroKit2](https://neuropsychology.github.io/NeuroKit/functions/hrv.html) (`nk.hrv`,
  `signal_fixpeaks`) · [pyHRV](https://github.com/PGomes92/pyhrv) (Task-Force-compliant).
- **Caveat:** frequency-domain metrics need clean, evenly-resampled segments; RMSSD/pNN50
  tolerate short windows and occasional artifacts far better than LF/HF.

## 3. Recovery / Readiness — your own 0–100 score

No open library outputs a branded score; the recipe is well-established:

1. Nightly, compute: lnRMSSD (deep sleep), resting HR, respiratory rate, total sleep time +
   efficiency, skin-temp deviation.
2. Maintain a **personal rolling baseline** per metric — 7-day (reactivity) + ~28–60-day
   ("normal range") mean and SD.
3. Convert each to a **z-score vs baseline**, signed so "good" is positive (HRV↑ = +,
   RHR↑ = −, resp-rate↑ = −, sleep-debt = −, |temp Δ| large = −).
4. Weighted sum → squash to 0–100 (e.g. logistic). HRV and RHR dominate; sleep, respiratory
   rate, and temperature are modifiers/illness flags.

- **Reference method:** Marco Altini's lnRMSSD 7-day baseline + coefficient-of-variation
  ("normal range") approach (HRV4Training writings).
- **Feature tooling if you go ML:** [FLIRT](https://github.com/im-ethz/flirt) (sliding-window
  feature generation over HRV/ACC).
- **Caveat:** baselines need ~2–4 weeks to stabilize; consistency (same sleep window/posture)
  matters more than any single formula. Alcohol, illness, late meals, and travel legitimately
  move the score.

## 4. Sleep staging

- **Sleep/wake** from the accelerometer via **Cole-Kripke** or **Sadeh** actigraphy.
  Lib: [pyActigraphy](https://github.com/ghammad/pyActigraphy) (both algorithms + more).
- **4-stage (light/deep/REM)** needs HR + HRV + motion + a circadian-clock feature.
  Lib/model: [`ojwalch/sleep_classifiers`](https://github.com/ojwalch/sleep_classifiers)
  (Apple-Watch-derived models; companion PhysioNet dataset to retrain/validate).
- **Caveat (be realistic):** actigraphy over-estimates sleep (high sleep sensitivity, poor
  wake specificity). Multi-stage HR+motion staging lands around Cohen's **κ ≈ 0.4–0.6**;
  deep/REM boundaries are least reliable. Treat stage durations as estimates, not truth.

## 5. Respiratory rate

- **Concept:** respiration modulates the cardiac signal (respiratory sinus arrhythmia / HF
  band) and PPG amplitude. Estimate from the dominant frequency of the R-R series or PPG AM.
- **Libraries:** [NeuroKit2](https://neuropsychology.github.io/NeuroKit/) (`rsp_rate`,
  `ecg_rsp`, `hrv_rsa`) · HeartPy (`breathingrate` from P-P intervals).
- **Caveat:** best at rest/sleep with clean PPG; degrades with motion, age, high rates.

## 6. Strain / training load

- **Banister TRIMP:** `duration × mean_HR × weight(HRR)`, where `HRR = (HR−HRrest)/(HRmax−HRrest)`
  and the weight is an exponential of HRR (up-weights hard efforts).
- **Edwards zone TRIMP:** `Σ (minutes_in_zone_i × i)` over 5 HR-max zones.
- These are ~10-line NumPy/pandas formulas (need your **HRrest** and **HRmax**). WHOOP Strain
  is a **log/Borg-scaled 0–21** mapping of cardiovascular (+ muscular) load — reproduce the
  *shape* with a monotonic concave map fit to your own load distribution.
- **Caveat:** HR-based load lags short anaerobic efforts and can't see true muscular load —
  the gap WHOOP fills with an accelerometer-derived term.

## 7. SpO₂ and skin temperature — handle with care

- **You only have raw ADC counts** off the band — there is **no on-band calibration**.
- **SpO₂:** requires the red/IR **ratio-of-ratios** `R = (AC_red/DC_red)/(AC_IR/DC_IR)` then
  an empirical `SpO₂ ≈ A − B·R` calibration **you must fit yourself** against a reference
  oximeter. Wrist reflectance is hard (motion, perfusion, skin tone) — approximate at best,
  and WHOOP only samples it briefly during sleep.
- **Skin temperature:** report **nightly deviation from a personal rolling baseline**
  (illness / menstrual-cycle signal), never an absolute °C.

---

## Recommended end-to-end pipeline

```
BLE collector (bleak)                     # ../README.md §7, whoop-vault
   → E2E-PPG or NeuroKit2                  # PPG → IBI, with signal-quality assessment
   → hrv-analysis                          # artifact correction + HRV / resting HR (nightly)
   → NeuroKit2                             # respiration / RSA
   → pyActigraphy + sleep_classifiers      # sleep/wake + staging
   → pandas rolling baselines & z-scores   # personal baselines
   → your Recovery (0–100) + log-mapped Strain (0–21)
   + skin-temp Δ and (optional, fitted) SpO₂ as extra flags
```

**Do not skip signal-quality assessment.** Motion artifacts dominate wrist-PPG error;
quality-gating (E2E-PPG's SVM or NeuroKit2's `ppg_quality`) is what makes the HRV — and
therefore the whole recovery pipeline — trustworthy.

**All-in-one references worth reusing:**
[E2E-PPG](https://github.com/HealthSciTech/E2E-PPG) (full wrist-PPG → HRV pipeline) ·
[NeuroKit2](https://github.com/neuropsychology/NeuroKit) (the backbone) ·
[Wearipedia](https://github.com/Stanford-Health/wearipedia) (unified wearable-data API;
includes a WHOOP device — check whether it exposes raw vs summary data for your model).

---

*Reproduces published methods, not WHOOP's proprietary algorithms. Not medical advice; not a
medical device. Validate against ground truth before trusting any derived number.*
