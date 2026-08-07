# Rebuilding WHOOP's Paid-Tier Metrics Locally (Peak & Life features on a WHOOP 5.0)

> Companion to [`README.md`](./README.md). That document covers *getting raw data off the band*.
> This one answers: **which of WHOOP's pricier-tier features are actually hardware-locked, and
> how do you compute the rest yourself from data you already own?**
>
> Short version: **of the six features gated behind the Peak and Life tiers, exactly one is
> genuinely impossible on a WHOOP 5.0.** The other five are algorithms over signals your band
> already produces.

---

## 1. The tiers, and what actually gates each feature

| Tier | ~Price (USD/yr) | Hardware | Adds |
|---|---|---|---|
| **One** | $199 | WHOOP 5.0 | Recovery, Strain, Sleep, VO₂max, steps |
| **Peak** | $239 | WHOOP 5.0 | Healthspan (WHOOP Age + Pace of Aging), Health Monitor + alerts, Real-time Stress Monitor |
| **Life** | $359 | **WHOOP MG** | Heart Screener (ECG), Irregular Heart Rhythm Notifications, Blood Pressure Insights |

*(UK pricing seen in the wild: Peak £229, Life £349.)*

### The verdict table

| Feature | Tier | Gate | Can you build it on a 5.0? |
|---|---|---|---|
| **Healthspan / WHOOP Age / Pace of Aging** | Peak | **Software** | ✅ Yes — §3 |
| **Health Monitor + alerts** | Peak | **Software** | ✅ Yes — §4 (easiest, highest value) |
| **Real-time Stress Monitor** | Peak | **Software** | ✅ Yes — §5 |
| **Irregular Heart Rhythm (AFib)** | Life/MG | **Software** | ✅ Yes — §6 (WHOOP's own is PPG-based!) |
| **Blood Pressure Insights** | Life/MG | **Software** | ⚠️ Don't — §7. Build a proxy, never mmHg |
| **Heart Screener (ECG)** | Life/MG | **HARDWARE** | ❌ **No.** Physically impossible — §8 |

### Why the Peak tier is provably software-only

**WHOOP shipped Healthspan/WHOOP Age to the WHOOP 4.0 via an app update.** Hardware from 2021.
That single fact settles it: Healthspan, Health Monitor and the Stress Monitor involve no sensor
your band lacks. They are cloud math over sleep, HR, HRV and activity.

### What's actually different about the MG

The 5.0 and MG sensor pods are described as "virtually identical in core physical design" — same
Ambiq Cortex-M4 MCU, same TDK-InvenSense **6-axis IMU** (so yes, your 5.0 *does* have a
gyroscope), same PPG stack, same thermistor, same charger, same band geometry. Weight differs by
0.8 g (26.5 vs 27.3).

**The MG's only real hardware addition is a pair of ECG electrodes** — conductive contacts on the
pod casing plus a **conductive U-shaped bracket in ECG-compatible bands**. You touch the clasp
with the opposite hand to close a **Lead-I** circuit for ~30 seconds. Proof that the electrodes
live in the *band*: fitting a standard 5.0 band to an MG pod **disables ECG**.

> **A note on the "5.0 already has an ECG chip" theory.** TechInsights' 5.0 teardown mentions a
> "PPG/ECG flex board" with an Analog Devices "optical PPG/ECG analog front-end." Tempting, but
> "PPG/ECG AFE" is how Analog Devices markets a *combo part family* — shipping that part in the
> PPG role says nothing about whether the ECG channels are populated, wired, or routed. The exact
> part number is paywalled. **And it doesn't matter**: without electrodes there is no signal to
> amplify. Treat the internal-silicon question as unresolved and irrelevant.

### On flipping firmware feature flags — a documented dead end

The protocol does contain a flag mechanism (`SET_FF_VALUE` 0x78, `GET_FF_VALUE` 0x80,
`START_FF_KEY_EXCHANGE` 0x75), an ECG command family internally codenamed **"Labrador"**
(`SELECT_WRIST` 0x7B, `TOGGLE_LABRADOR_DATA_GENERATION` 124, `TOGGLE_LABRADOR_RAW_SAVE` 125,
`TOGGLE_LABRADOR_FILTERED` 0x8B), and a flag literally named `enable_raw_data_w_ecg`.

**Don't chase it.** Four reasons:
1. Those opcodes were decoded from the **phone app's** unified command enum, which covers 4.0,
   5.0 and MG alike. Presence in the app proves nothing about your hardware.
2. The reverse-engineering projects that found them warn, in their own source comments, twice:
   *"do not invent ECG from an ACK."* No wire capture on any device has confirmed the ECG family
   functions.
3. Even a successful strap-side unlock produces nothing, because **the derived scores are computed
   in WHOOP's cloud**, not on the band. Flipping a flag cannot make a Healthspan number appear.
4. Several of these opcodes sit next to genuinely destructive ones (flash erase, firmware load).

The productive path is to compute the metrics yourself. Everything below does that.

---

## 2. Two things to verify before you write any analytics code

Both are cheap to test and either one can silently invalidate everything downstream.

**(a) What is the timestamp resolution of the R-R stream?**
The 5.0's PPG is reported at ~26 Hz, giving ~38 ms peak-timing granularity — marginal for the
entropy-based metrics that AFib detection depends on, *unless* the firmware computes inter-beat
intervals at a higher internal resolution. Log a few thousand R-R values and inspect the
distribution of unique values. Clustering at ~38 ms multiples is the warning sign.

**(b) Is the R-R stream raw, or already artifact-corrected?**
If WHOOP's firmware silently interpolates outlier intervals, it **destroys AFib detectability
while leaving HRV metrics looking perfectly healthy**. Test by wearing the band during deliberate
motion and checking whether implausible intervals ever appear, or by comparing against a chest
strap (see §9).

**And one labeling correction that applies throughout:** wrist PPG gives you **pulse rate
variability (PRV), not HRV**. They agree at rest, supine, still, with a clean signal — i.e.
exactly the nightly sleep window everything below uses. Outside that window, label it PRV and
don't compare it to ECG-HRV reference values. (Yuda et al. 2020: *"a new biomarker, not a
surrogate for HRV"*; a 2025 study found poor agreement in 11 of 13 conditions.)

---

## 3. Healthspan / WHOOP Age / Pace of Aging

### What WHOOP discloses

Developed with Dr. Eric Verdin (Buck Institute). **Nine contributors**, all linked to all-cause
mortality:

| # | Contributor | From your raw data? |
|---|---|---|
| 1 | Sleep consistency | ✅ accel + HR → sleep/wake → SRI |
| 2 | Sleep duration | ✅ |
| 3 | Time in HR zones 1–3 | ✅ (WHOOP uses **heart-rate reserve**, not %HRmax) |
| 4 | Time in HR zones 4–5 | ✅ |
| 5 | Strength activity time | ⚠️ accel classification is hard — log manually |
| 6 | Steps | ✅ |
| 7 | VO₂max | ⚠️ estimate — §3.3 |
| 8 | Resting heart rate | ✅ |
| 9 | Lean body mass | ❌ needs a smart scale / DEXA |

**Seven of nine come straight off your band.** One needs a tape measure, one needs a scale.

### 3.1 The method (and the formula)

WHOOP's disclosed pipeline is three steps:
1. Map each contributor to a published **hazard ratio (HR)** for all-cause mortality.
2. Convert HR → years **log-linearly**: *"a 10% increase in mortality risk ≈ one year of effective
   age; a hazard ratio of 1.22 pushes WHOOP Age up by two years."*
3. Correct for overlap with a **structural equation model** so correlated habits aren't
   double-counted.

Step 2 is just **Gompertz mortality**: human hazard is log-linear in age with a mortality-rate
doubling time (MRDT) of ~8 years.

```
Δage_years = ln(HR) / α        where  α = ln(2) / MRDT

MRDT = 8 yr            → α = 0.0866 /yr
WHOOP's "10% ≈ 1 yr"   → α = ln(1.10) = 0.0953 /yr  (implied MRDT ≈ 7.27 yr)
```

Sanity check against WHOOP's own worked example: `ln(1.22)/ln(1.10) = 2.09` → "two years." ✅

So: `WHOOP_Age ≈ chronological_age + Σ_contributors [ ln(HR_i) / 0.0953 ] × overlap_correction_i`

**Pace of Aging** compares your most recent **30 days** against your **6-month** WHOOP Age
baseline — "what happens if the last 30 days continue." Reported range −1× to 3× (endpoints
single-sourced; treat as approximate).

### 3.2 Hazard ratios to plug in

Published figures you can use for step 1. **Verify each at source before shipping** — several are
commonly miscited.

| Contributor | Effect | Source |
|---|---|---|
| Resting HR | **RR 1.09 (1.07–1.12) per +10 bpm** — 46 studies, n=1,246,203 | Zhang et al., CMAJ 2016;188(3):E53 |
| Sleep regularity (SRI) | **HR 1.53 (1.41–1.66)** at 5th-percentile SRI vs median; **0.90** at 95th. Top 4 quintiles vs lowest: 20–48% lower mortality. n=60,977 UK Biobank | Windred et al., *Sleep* 2024 (PMID 37738616) |
| Steps | **HR 0.85 per +1000 steps/day** (17 cohorts, n=226,889) | ⚠️ **Banach 2023, Eur J Prev Cardiol** — *not* Paluch 2022, which reports quartile HRs and a 6–8k (≥60 yr) / 8–10k (<60 yr) plateau |
| Cardiorespiratory fitness | ~13% lower mortality per +1 MET (widely cited, **unverified**) | Kodama et al., JAMA 2009;301(19):2024 |

**Sleep regularity is a stronger mortality predictor than sleep duration** — weight it accordingly.

### 3.3 VO₂max — the HUNT/Nes non-exercise model

Your band has no GPS, so Firstbeat-style HR↔pace extrapolation isn't available. The best fully
specified published alternative is the **HUNT** model behind NTNU's World Fitness Level
calculator (Nes et al., *Med Sci Sports Exerc* 2011;43(11):2024, **PMID 21502897**):

```
Men:   VO₂peak = 100.27 − 0.296·age + 0.226·PA-I − 0.369·waist_cm − 0.155·RHR    (SEE ≈ 5.70)
Women: VO₂peak =  74.74 − 0.247·age + 0.198·PA-I − 0.259·waist_cm − 0.114·RHR    (SEE ≈ 5.14)
```

`PA-I` = HUNT physical-activity index = weekly frequency (0–5) × duration (0.10–1.00) ×
intensity (1–3), range 0–15. Derive it from your HR-zone minutes by mapping low/medium/high
intensity to **44% / 73% / 83% of heart-rate reserve**.

> ⚠️ **A calibration trap nobody flags.** HUNT's RHR was a **seated clinic measurement**, not a
> nocturnal sleeping HR. Your band's nocturnal RHR runs meaningfully lower, and with a −0.155
> coefficient that **inflates your VO₂max**. Either take a seated resting measurement for this
> input, or apply and document a fixed offset.

> ⚠️ These coefficients agree across five independent implementations and two web calculators, but
> one repo explicitly logs that it could not verify a claimed verbatim reproduction. Confirm
> against PMID 21502897 before trusting them, including which variant (waist vs BMI) is primary.

**Cross-check** with the Heart Rate Ratio method (Uth et al. 2004): `VO₂max ≈ 15 × (HRmax/HRrest)`
— needs a genuine measured HRmax (not `220−age`) and the same seated-RHR correction. Validity is
population-dependent; don't apply it blind to a sedentary user.

**Fitness Age** = the age at which population-mean VO₂max equals your estimate, inverting FRIEND
registry norms (Kaminsky et al., Mayo Clin Proc 2015). This is the honest, publishable "age"
number — far better grounded than a composite.

### 3.4 What you cannot reproduce, and one important caveat

- **PhenoAge** (Levine 2018) — all nine inputs are blood chemistry. Needs a lab panel.
- **DunedinPACE** — requires a **DNA methylation array**. WHOOP's "Pace of Aging" borrows the name
  and framing of DunedinPACE but **shares none of its measurement basis**. Worth knowing before
  you treat either number as biological age.
- **KDM (Klemera–Doubal)** is the one biological-age method that is *biomarker-agnostic* — you can
  retrain it on wearable features. Reference implementation: the R package
  [`BioAge`](https://github.com/dayoonkwon/BioAge) (`kdm_calc`, `hd_calc`, `phenoage_calc`).
- **Homeostatic Dysregulation (HD)** is the most portable: Mahalanobis distance from a healthy
  reference distribution. Run it over your own wearable feature vector using your healthiest
  3-month window as the reference. Defensible as *personal* homeostatic dysregulation — **not** a
  validated aging clock.

There is **no open-source wearable biological-age package**. Retraining KDM on wearable features
is the largest piece of genuinely original work in this project.

### 3.5 Sleep Regularity Index (needed for contributor #1)

```
SRI = −100 + (200 / (M·(N−1))) · Σ_{i,j} δ(s_{i,j}, s_{i+1,j})

M = epochs/day (30 s standard), N = days, s ∈ {sleep, wake}
δ = 1 if state at the same epoch on consecutive days matches, else 0
Range −100…100.  100 = perfectly regular.
```
Implementations: `pyActigraphy.sleep.ScoringMixin.SleepRegularityIndex()`,
[`mengelhard/sri`](https://github.com/mengelhard/sri), [`dpwindred/sleepreg`](https://github.com/dpwindred/sleepreg) (R),
GGIR's `CalcSleepRegularityIndex()`. ⚠️ Values differ across packages — pick one and stay with it.

---

## 4. Health Monitor + alerts — start here

**The easiest and highest-value rebuild**, because the best published detector has fully specified,
verified parameters.

WHOOP's Health Monitor shows six metrics — live HR, HRV, RHR, respiratory rate, SpO₂, skin
temperature — and alerts on **personal baseline deviation** (plus one absolute backstop: SpO₂
below 94%). Thresholds and baseline window are unpublished.

### 4.1 NightSignal — use this as your primary detector

From Stanford's [`wearable-infection`](https://github.com/StanfordBioinformatics/wearable-infection)
(Alavi et al., *Nat Med* 2022). Of their three algorithms, **NightSignal has the best sensitivity
(78%, vs CuSum 54% and RHRAD 44%)**, alerting 53 of 68 COVID-positive participants at or before
symptom onset — **median 3 days early**.

Parameters verified by reading `nightsignal.py`:

```python
yellow_threshold = 3   # bpm above baseline
red_threshold    = 4   # bpm above baseline
```

1. **Nightly RHR** = mean HR over samples where **step count == 0**, restricted to hours
   **00:00–06:59** local.
2. **Gap imputation**: a single missing day flanked by present days is filled with the neighbour
   mean. Two-day gaps are not filled.
3. **Baseline** = median of *all prior nightly averages including today* — an **expanding-window**
   median, not a rolling one.
4. **Red** = RHR ≥ baseline + 4 bpm on **two consecutive nights**.
5. **Yellow** = RHR ≥ baseline + 3 bpm on two consecutive nights, and not already red.

A reference implementation is in [`starter/premium_metrics.py`](./starter/premium_metrics.py).

### 4.2 The sensitivity reality check

Scripps **DETECT** (Radin et al., *Nat Med* 2020, n=30,529): symptoms alone AUC 0.71, sensor data
alone AUC 0.72, **combined AUC 0.80**. But the number that matters:

> **An RHR change >2 SD was detected in only 30.3% of positive cases.**

A single-channel z-score rule misses ~70% of infections. **So combine channels**: require
**≥2 of {RHR↑, RMSSD↓, respiratory rate↑, skin temp↑} for 2 consecutive nights** before alerting.
That's what takes DETECT from 0.72 to 0.80, and it kills most single-channel false positives.

### 4.3 Skin temperature — where uncalibrated is fine

Your band gives raw, uncalibrated ADC counts (see README §4). **That's not a problem here**,
because every published method uses *deviation from personal baseline* anyway. Absolute
calibration is irrelevant; sensor drift and ambient coupling are not.

TemPredict (Oura/UCSF): **76% (38/50)** of participants showed a temperature rise before symptom
onset. Note that a healthy person's within-day range can exceed **0.9 °F (~0.5 °C)** — you need
**5–21 nights** of consistent wear before deviations mean anything.

### 4.4 Detector stack

1. **Robust z-score** — use **median and MAD**, not mean/SD (one illness episode poisons an
   SD baseline). Trailing 28–31 days. Use log scale for RMSSD (lnRMSSD is standard).
2. **NightSignal FSM** — §4.1. Primary.
3. **CUSUM** — `S_n = max(0, S_{n−1} + (x_n − μ₀ − k))`, alarm at `S_n > h`. Catches slow drift
   z-scores miss.
4. **EWMA** — `z_n = λx_n + (1−λ)z_{n−1}`, λ ≈ 0.1–0.3. Better for gradual drift.
5. **Mahalanobis distance** over the nightly feature vector — elegant, because it reuses the same
   `hd_calc` logic from §3.4 and catches "everything slightly off in a correlated way," which is
   exactly the illness signature per-metric z-scores miss.
6. Streaming: [`river`](https://github.com/online-ml/river); change-point:
   [`ruptures`](https://github.com/deepcharles/ruptures); SPC charts: `pyspc`.

**Benign confounders to suppress or annotate:** alcohol (large RHR↑ + RMSSD↓, indistinguishable
from illness), hard training the previous day, late meals, hot bedroom, menstrual phase (a
predictable ~0.3–0.5 °C luteal shift), altitude, vaccination, jet lag.

### 4.5 Respiratory rate (an input you must derive)

Not directly sensed — derive from PPG/R-R via respiratory sinus arrhythmia and amplitude/baseline
modulation. Best PPG algorithm bias ~1.0 bpm; modern methods reach MAE ~1.6–1.9 breaths/min.
Use [`RRest`](https://github.com/peterhcharlton/RRest) (Charlton's 314-algorithm benchmark suite)
or NeuroKit2's `rsp` / `hrv_rsa`. Restrict to sleep.

---

## 5. Real-time Stress Monitor

WHOOP's version: continuous **HRV + HR** → a **0–3 stress score**, compared against a trailing
**14-day HRV baseline**, and **motion-gated by the accelerometer** so exertion isn't misread as
stress. No proprietary sensor — WHOOP has no EDA either. **Fully reproducible.**

### 5.1 ⚠️ The Baevsky trap — read this before writing code

**NeuroKit2 does NOT implement Baevsky's Stress Index.** Its `HRV_SI` is the **Slope Index**, an
HRV *asymmetry* metric (Piskorski & Guzik) — verified at `neurokit2/hrv/hrv_nonlinear.py:407–410`.
**pyhrv doesn't implement it either.** Any code or tutorial claiming `nk.hrv()["HRV_SI"]` is
Baevsky is wrong.

You must implement it yourself (~10 lines):

```
SI = AMo / (2 · Mo · MxDMn)

Mo     = mode of the RR distribution, in SECONDS (Kubios uses median RR)
AMo    = % of RR intervals in the modal bin (bin width 50 ms)
MxDMn  = max(RR) − min(RR), in SECONDS
```
Typical range ~50 to >900; 50–150 low stress, >500 high sympathetic activation. **Kubios takes
√SI** to tame the right tail. Reference: *Am J Physiol Regul Integr Comp Physiol* (2024),
"Determining autonomic sympathetic tone and reactivity using Baevsky's stress index."

> There is a **buggy implementation in the wild** that substitutes the raw mode-bin *count* where
> the modal RR *value* belongs. Getting the seconds-vs-milliseconds conversion wrong silently
> scales your index by 10⁶. A correct implementation is in
> [`starter/premium_metrics.py`](./starter/premium_metrics.py).

### 5.2 Don't use LF/HF

Billman, *Front Physiol* 2013;4:26 (~1,000 citations): *"The LF/HF ratio does not accurately
measure cardiac sympatho-vagal balance."* LF is not a clean sympathetic marker and the ratio
assumes a reciprocal relationship that doesn't exist. **RMSSD / SD1 / HF / pNN50 → vagal tone**
is well supported; sympathetic tone has no clean HRV proxy. Baevsky SI is the best available and
is still indirect.

### 5.3 Pipeline

```
raw PPG (+ accel)
  → nk.ppg_clean() → nk.ppg_findpeaks()     [or the band's own R-R stream]
  → nk.ppg_quality() + accel magnitude       → MOTION GATE (drop noisy/moving windows)
  → nk.signal_fixpeaks(method="Kubios")      [Lipponen & Tarvainen 2019 correction]
  → rolling 60–300 s windows, 50 % overlap
  → per window: RMSSD, SD1, mean HR  +  √(Baevsky SI)
  → z-score vs a trailing 14-day baseline, STRATIFIED BY HOUR-OF-DAY
  → stress ∝ w₁·(−z_RMSSD) + w₂·(+z_√SI) + w₃·(+z_HR)  → clamp to 0–3
```

**Window length:** RMSSD agrees with 300 s gold standard down to ~14 s **at rest** — but validity
collapses under load (correlations below 0.50 for 60 s windows during cognitive tasks).

### 5.4 Caveats — state these plainly

1. **Motion artifact dominates.** Wrist tendon motion produces noise overlapping the cardiac band.
   RMSSD is a derivative, so it amplifies per-beat timing noise far worse than HR error suggests.
2. **WHOOP's own validation** (Bellenger et al., *Sensors* 2021): HR agreement is fine, but
   **lnRMSSD bias and limits of agreement approached or exceeded the smallest worthwhile change**.
   Day-to-day HRV deltas from wrist PPG may be inside measurement noise.
3. **HRV cannot separate arousal valence.** Excitement, caffeine, standing up, digestion and a
   cold room all raise sympathetic tone. ("Are you stressed or just excited?" — *J Affect Disord*.)
4. **No EDA.** Electrodermal activity is the only purely-sympathetic channel and neither you nor
   WHOOP has it. Irreducible ceiling.
5. **Stratify the baseline by hour-of-day** — HRV has a strong circadian rhythm, and a flat 14-day
   baseline will systematically read "stressed" every morning.
6. **Gate on posture** — standing produces vagal withdrawal indistinguishable from stress.

---

## 6. Irregular Heart Rhythm / AFib screening — the best unlock

**WHOOP's own AFib detection is PPG-based, not ECG-based.** From their trial registration
(NCT05809362) and published protocol (*BMJ Open*, June 2024), the **WARN / ANF 1.0** algorithm:

> *"The WHOOP strap measures changes in blood flow via **photoplethysmography (PPG)**, from which
> timing between successive heartbeats ('beat-to-beat intervals') is measured. A machine learning
> algorithm (**XGBoost**) analyses beat-to-beat intervals for irregularity suggestive of AF, with
> aggregated data analysed as overlapping **30-min 'epochs'**."*

Validated against a BioTel ePatch ECG. **Your 5.0 produces every input this needs.** The MG
requirement is a commercial/regulatory decision — most plausibly because WHOOP ties the alert to
on-device ECG confirmation so it's actionable.

This approach is established enough that FDA created a device class for it: **21 CFR §870.2790**,
"Photoplethysmograph analysis software for over-the-counter use," Class II — explicitly *"not
intended to provide a diagnosis,"* with special controls requiring **signal-quality detection**.

| Study | n | Notify rate | PPV vs ECG patch |
|---|---|---|---|
| Apple Heart (NEJM 2019) | 419,297 | 0.52% | **0.84** |
| Fitbit Heart (Circulation 2022) | 455,699 | ~1% | **98.2%** |
| Huawei Heart (JACC 2019) | 187,912 | 0.23% | **91.6%** |

That PPV spread is driven by population and confirmation-rule strictness, not sensor quality —
Apple's cohort was young and low-prevalence; Fitbit required **11 consecutive** irregular windows.

### 6.1 Algorithms (all run on the R-R series alone)

- **CosEn** (Lake & Moorman 2011) — sample entropy normalized by tolerance and mean RR; works on
  **as few as 12 beats**. Best cost/benefit single feature for streaming.
- **Lorenz / Poincaré plot of ΔRR** (Sarkar/Ritscher/Mehra, IEEE TBME 2008 — the implantable
  monitor family). AF = diffuse isotropic cloud; sinus = tight cigar; **ectopy = discrete
  side-lobes** — which is exactly how you separate PACs/PVCs from AF.
- **Lian et al. 2011** (*Am J Cardiol*) — simplest publishable method: plot RR vs dRR on a
  **25 ms grid**, count non-empty cells, threshold.
- **Shannon entropy** of the binned ΔRR distribution; **RMSSD/nRMSSD**; **pNN40/pNN70**.
- **Gradient-boosted trees over the above** = a faithful reproduction of WHOOP's XGBoost design.

### 6.2 Code and validation data

| Resource | What it gives you |
|---|---|
| [`Sarathismg/BayesBeat`](https://github.com/Sarathismg/BayesBeat) | Bayesian DL for AF from **noisy** PPG — **ships pretrained CPU weights** |
| [`AshleyLab/deepbeat`](https://github.com/AshleyLab/deepbeat) | Multi-task CNN: joint signal-quality + AF (data via Synapse, non-commercial DUA) |
| [`chengstark/SiamAF`](https://github.com/chengstark/SiamAF) | MIT; ECG↔PPG shared latent, PPG-only inference |
| [`Aura-healthcare/hrv-analysis`](https://github.com/Aura-healthcare/hrv-analysis) | **Ectopy rejection — mandatory before any AF metric** |
| [`HealthSciTech/E2E-PPG`](https://github.com/HealthSciTech/E2E-PPG) | Signal-quality gate + denoise + peak detection |
| **MIMIC PERform AF** ([Zenodo](https://zenodo.org/records/15906524)) | 35 subjects, **simultaneous ECG + PPG** — your best validation set |
| **MIT-BIH AFDB** | Canonical R-R AF benchmark — tune thresholds here first |
| PhysioNet/CinC 2017 | 8,528 ECGs; **winners tied at F1 = 0.83** — a realistic ceiling even on clean single-lead ECG |

### 6.3 Build order and the honest limits

```
CosEn + Lorenz-plot features
  → hrv-analysis ectopy rejection      (PACs/PVCs are THE dominant false positive)
  → E2E-PPG signal-quality gate
  → restrict to sleep / still periods  (~40% of free-living PPG is unusable)
  → multi-epoch confirmation rule      (Apple 5-of-6; Fitbit 11 consecutive)
  → validate: MIT-BIH AFDB → MIMIC PERform AF → your own Polar H10 ground truth
```

**Limits to respect:**
- **Ectopy is the main false-positive source.** A two-stage detector with PAC/PVC recognition
  moved published AF performance from sens 94.55→98.18 / spec 95.75→97.90 — but the ectopy
  classifier itself was only 63% sensitive. Even the fix leaks.
- **PPG beat detection is worse *in* AF** (F1 92–97% vs 99–100% in sinus) — a circular failure
  mode where the detector partly detects its own noise.
- **PPG cannot distinguish AF from atrial flutter, MAT, or frequent ectopy**, because the
  discriminating feature (atrial electrical activity) isn't in an optical signal.
- USPSTF 2022 gives AF screening in asymptomatic adults an **"I" statement** — insufficient
  evidence — having explicitly considered wearables.

**Report it as:** *"irregular rhythm episodes detected during N analyzable still-minutes —
consider a single-lead ECG."* **Never** "AFib," never a burden percentage, never "no AFib."

---

## 7. Blood Pressure — build a proxy, never a number

**Don't try to output mmHg.** This isn't caution, it's the field's own position.

**Single-site wrist PPG structurally cannot measure transit time.** PTT needs two PPG sites on the
same arterial path; PAT needs an ECG R-wave reference. With one wrist sensor you're left with
pulse-wave *morphology* + ML — the family the literature is harshest on.

- **2025 AHA/ACC guideline: cuffless BP devices are not recommended** for diagnosis or management,
  and reliance on smartwatch BP should be avoided.
- **No cuffless device — commercial or prototype — has been validated** to ISO 81060-3:2022 or the
  ESH 2023 recommendations. (ISO 81060-2 is for cuffs and is inappropriate here.)
- Mukkamala et al., *Hypertension* 2025;82(6):957: *"no compelling evidence that pulse wave
  analysis and pulse arrival time can provide significant added value in BP measurement accuracy
  **beyond the cuff BP or demographic data for calibration**."*

**The calibration paradox:** once calibrated to your own cuff readings, a model that returns "your
calibration value, lightly perturbed" scores well on MAE, because within-subject BP variance is
small next to between-subject variance. WHOOP's **30-day recalibration requirement is effectively
an admission** that the model tracks a decaying anchor.

Empirically: neural nets beat a **mean regressor** by margins the authors called *"not large enough
to be of any practical relevance"* (Schrumpf 2021); cross-dataset transfer showed *"practically
complete loss of predictive power"* (Weber-Boisvert 2023); the best 2025 benchmark reaches SBP MAE
**9.0 mmHg calibrated / 13.9 uncalibrated** against an AAMI standard of **≤5 ± 8**.

**What to build instead:** a unitless **nocturnal vascular-tone / arterial-stiffness index** from
PPG morphology (second-derivative aging index, reflection index, stiffness index, augmentation
index — see [`pyPPG`](https://github.com/godamartonaron/GODA_pyPPG)'s 74 biomarkers), reported as a
**z-score against your personal baseline**. Same category as your recovery scores, and honest.
Or hypertension *classification* rather than regression (realistic AUC 0.70–0.83).

> **Framing matters legally, not just ethically.** FDA issued WHOOP a warning letter over BPI in
> July 2025; it was resolved in June 2026 **through a labeling/marketing change** — dropping
> "medical-grade" language — not an algorithm change. Describe anything you build as a *personal
> trend signal that prompts a real measurement*.

---

## 8. ECG — the one genuine wall, and the cheap way around it

**You cannot derive an ECG from PPG. Not with better algorithms, not with more sampling.**

ECG measures **body-surface electrical potentials** from myocardial depolarization — a direct
electrophysiological observation. PPG measures **optical absorbance from pulsatile blood volume** —
the *end* of a lossy chain (excitation → contraction → pressure wave → wrist volume → absorbance).
The map is many-to-one and non-invertible:

- **Electrical activity with no mechanical output** — pulseless electrical activity, non-conducted
  PACs, blocked atrial beats — is present in ECG, **invisible** in PPG.
- **Atrial activity has essentially no pulse-volume signature.** No P waves, no f-waves, no flutter
  waves. This is *why* PPG can't separate AF from flutter.
- **Repolarization has no mechanical correlate at all** — ST segments and T waves simply do not
  exist in an optical signal.

Exclusively in the ECG: **P wave** (AF vs flutter vs MAT), **PR interval** (AV block, WPW delta
wave), **QRS morphology** (VT vs SVT with aberrancy — a life-or-death distinction), **QT/QTc**
(torsades risk; the most common reason a drug gets a cardiac safety label), **ST segment** (STEMI,
ischemia), **T/U waves** (hyperkalemia), **pacing spikes**.

> ML papers that "reconstruct ECG from PPG" produce plausible-looking waveforms by hallucinating a
> population-average QRS/T shape conditioned on beat timing. They recover no subject-specific ST or
> QT information, because that information was never in the input. Generative, not measurement.

### Buy the capability instead — it's far cheaper than the tier

| Device | ~Price | Notes |
|---|---|---|
| **AliveCor KardiaMobile 1L** | **~$79** | FDA-cleared, 30 s, classifies Normal/AFib/Brady/Tachy. One-time cost, **less than a year of the Life premium**, and gives strictly more than WHOOP's 30-second clasp reading (also single-lead). |
| AliveCor KardiaMobile 6L | ~$129 | Six leads → real axis + limited morphology |
| Wellue DuoEK | ~$69–100 | Continuous 15-min mode — catches paroxysmal events that 30 s spot checks miss |
| **Polar H10** | **~$90** | See §9 — the highest-leverage purchase for this project |

Open hardware (none FDA-cleared, none for diagnosis): AD8232 breakout (~$20), TI ADS1292R eval
board, OpenBCI Cyton. **Safety: battery-powered and floating only — never connect a DIY ECG to a
mains-powered or grounded device while it's on your body.**

---

## 9. Buy a Polar H10 before you build any of this

**~$90, and it's the single highest-leverage purchase in the project.**

It's a genuine single-lead *electrical* sensor and the de facto research standard for R-R
intervals (r = 0.95 at rest, > 0.93 during incremental exercise vs criterion ECG; 95% of intervals
within 2 ms). Critically, **it streams R-R over BLE**, so it drops straight into the pipeline you
already built.

That gives you **ECG-derived ground truth** to:
- answer both questions in §2 (timestamp resolution, whether the stream is pre-filtered),
- validate your AFib detector against real electrical beat timing,
- quantify how much your PRV diverges from true HRV, and when.

Every downstream metric in this document inherits its credibility from beat-timing accuracy. This
is how you find out whether you have any.

---

## 10. Recommended build order

1. **Signal conditioning first.** `nk.ppg_quality()` + accelerometer magnitude → motion gate;
   `nk.signal_fixpeaks(method="Kubios")` → beat correction. *Everything downstream is garbage
   without this, and it's the step hobby projects skip.*
2. **Nightly aggregates** — RHR (steps==0, 00:00–07:00), lnRMSSD (last slow-wave-sleep period, to
   match WHOOP), respiratory rate, skin-temp deviation, sleep duration, SRI.
3. **Health Monitor** (§4) — easiest, highest value, fully specified. NightSignal + robust
   z-scores + 2-of-4-channel confirmation.
4. **Stress Monitor** (§5) — motion-gated RMSSD + √(Baevsky SI), z-scored against a
   time-of-day-stratified 14-day baseline.
5. **VO₂max** (§3.3) — HUNT/Nes, with a seated-RHR calibration; cross-check with Uth HRR.
6. **Fitness Age** — invert FRIEND norms. The honest "age" number.
7. **AFib screening** (§6) — after the Polar H10 arrives, not before.
8. **WHOOP-Age-equivalent** (§3.1) — Gompertz HR→years over the 8 derivable contributors. Ship it
   labelled as a **heuristic composite**, not a biological age.
9. *(Optional)* Personal homeostatic dysregulation — Mahalanobis distance from your healthy-window
   reference. Doubles as the multivariate illness detector in §4.4.

---

## 11. Sources

**WHOOP methodology:** [Healthspan white paper](https://www.whoop.com/us/en/thelocker/Healthspan-Data-Meets-Longevity/) ·
[Healthspan support guide](https://support.whoop.com/s/article/Healthspan-WHOOP-Age-Pace-of-Aging-Guide) ·
[heart rate reserve](https://www.whoop.com/us/en/thelocker/why-whoop-uses-heart-rate-reserve-not-max-heart-rate/) ·
[Stress Monitor](https://www.whoop.com/us/en/press-center/whoop-launches-new-stress-monitor-feature-first-wearable-to-measure-daily-stress-levels-and-implement-stress-reduction-interventions-in-real-time/) ·
[Health Monitor](https://www.whoop.com/us/en/thelocker/health-monitor-feature/) ·
AFib trial [NCT05809362](https://clinicaltrials.gov/study/NCT05809362) + [protocol](https://pubmed.ncbi.nlm.nih.gov/38830741/)

**Biological age:** [BioAge (R)](https://github.com/dayoonkwon/BioAge) · [DunedinPACE](https://github.com/danbelsky/DunedinPACE) ·
[biolearn](https://github.com/bio-learn/biolearn) · [GOLD BioAge](https://advanced.onlinelibrary.wiley.com/doi/10.1002/advs.202501765) ·
[HR→age translation](https://pubmed.ncbi.nlm.nih.gov/34151374/)

**VO₂max / fitness age:** [Nes 2011 HUNT](https://pubmed.ncbi.nlm.nih.gov/21502897/) ·
[NTNU calculator](https://www.ntnu.edu/cerg/vo2max) · [Kaminsky FRIEND 2015](https://www.mayoclinicproceedings.org/article/S0025-6196(15)00642-4/pdf) ·
[Uth HR-ratio](https://link.springer.com/article/10.1007/s00421-003-0988-y) · [Firstbeat VO₂max](https://assets.firstbeat.com/firstbeat/uploads/2017/06/white_paper_VO2max_30.6.2017.pdf)

**Illness detection:** [DETECT (Nat Med 2020)](https://www.nature.com/articles/s41591-020-1123-x) ·
[Stanford wearable-infection](https://github.com/StanfordBioinformatics/wearable-infection) ·
[Alavi 2022](https://pubmed.ncbi.nlm.nih.gov/34845389/) · [AnomalyDetect](https://github.com/gireeshkbogu/AnomalyDetect) ·
[TemPredict](https://ouraring.com/blog/tempredict_covid19_research/)

**HRV / stress:** [NeuroKit2](https://github.com/neuropsychology/NeuroKit) ·
[Baevsky SI methods paper](https://journals.physiology.org/doi/full/10.1152/ajpregu.00243.2024) ·
[Kubios HRV methods](https://www.kubios.com/blog/hrv-analysis-methods/) ·
[Billman 2013 on LF/HF](https://www.frontiersin.org/journals/physiology/articles/10.3389/fphys.2013.00026/full) ·
[WHOOP PPG HRV validation](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8160717/)

**Sleep regularity:** [Phillips 2017 SRI](https://www.nature.com/articles/s41598-017-03171-4) ·
[Windred 2024](https://pubmed.ncbi.nlm.nih.gov/37738616/) · [pyActigraphy](https://github.com/ghammad/pyActigraphy)

**Mortality hazard ratios:** [Zhang 2016 RHR](https://www.cmaj.ca/content/188/3/E53) ·
[Banach 2023 steps](https://academic.oup.com/eurjpc/article/30/18/1975/7226309) ·
[Paluch 2022 steps](https://www.thelancet.com/journals/lanpub/article/PIIS2468-2667(21)00302-9/fulltext)

**Blood pressure:** [Mukkamala 2025](https://www.ahajournals.org/doi/10.1161/HYPERTENSIONAHA.125.24822) ·
[2025 AHA/ACC guideline](https://www.jacc.org/doi/10.1016/j.jacc.2025.05.007) ·
[FDA warning letter](https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/warning-letters/whoop-inc-709755-07142025)

**FDA / regulatory:** [21 CFR §870.2790](https://www.ecfr.gov/current/title-21/chapter-I/subchapter-H/part-870/subpart-C/section-870.2790) ·
[Apple irregular rhythm IFU](https://www.apple.com/legal/ifu/irnf/irn-ifu-2-en_US.pdf)

---

## 12. Confidence and caveats

**High confidence — verified by reading source code or primary registration:**
NightSignal's exact thresholds and FSM; NeuroKit2's `HRV_SI` being Slope Index (not Baevsky);
the absence of Baevsky SI from both NeuroKit2 and pyhrv; BioAge's KDM/PhenoAge/HD formulas;
WHOOP's AFib algorithm being PPG+XGBoost (their own trial registration); FDA's PPG device class;
Apple/Fitbit/Huawei PPV figures; the AHA/ACC cuffless-BP position.

**Medium confidence — multiple consistent sources, primary not read:**
WHOOP's nine Healthspan contributors and the hazard-ratio → log-linear → SEM pipeline (the white
paper itself was never retrieved); the HUNT/Nes coefficients (agree across five implementations,
but one repo flags an unverified reproduction); Baevsky's formula and Kubios's √SI transform;
the 26.5 g / 27.3 g weight delta.

**Explicitly unverified — check before relying on:**
WHOOP's actual per-contributor hazard ratios, SEM structure, and lean-body-mass estimator (all
unknown); the −1× to 3× Pace of Aging endpoints (single source); WHOOP's "<8% VO₂max error" claim
(vendor, unvalidated); Kodama's "13% per MET"; the linearized FRIEND norms circulating in
open-source repos (refit from the published decade tables); whether the 5.0's BLE stream exposes
raw dual-wavelength PPG or only a sleep-computed SpO₂; which FCC ID (WG50/WS50/WM50) is the MG.

**Structural limits that no amount of engineering fixes:**
No open-source wearable biological-age package exists — retraining KDM on wearable features is
original work. PhenoAge needs blood; DunedinPACE needs methylation. Sympathetic tone has no valid
HRV-only measurement (WHOOP shares this ceiling). And wrist-PPG HRV has validated accuracy
problems *at the magnitude that matters* — WHOOP's own validation study found lnRMSSD limits of
agreement approaching or exceeding the smallest worthwhile change, meaning day-to-day HRV deltas
may sit inside measurement noise.

---

*Reproduces published science, not WHOOP's proprietary algorithms. Not affiliated with WHOOP.
Not a medical device, not medical advice. For use with hardware you own.*
