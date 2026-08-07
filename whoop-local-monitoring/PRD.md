# Product Requirements Document

**Product:** A local-first analytics client for wearables you already own
**Working codename:** `STRAND` *(placeholder — see [§5.3](#53-naming-requirements); do not ship a name containing "whoop")*
**Status:** Draft for review · **Owner:** TBD · **Last updated:** 2026-08-07

> **Companion documents.** This PRD is the decision document. Implementation detail lives in:
> - [`README.md`](./README.md) — BLE protocol reference (GATT UUIDs, framing, opcodes, R24 record map, sync handshake)
> - [`analytics-stack.md`](./analytics-stack.md) — metric-by-metric open-source library reference
> - [`premium-metrics.md`](./premium-metrics.md) — paid-tier feature analysis and rebuild methods
> - [`product-strategy.md`](./product-strategy.md) — market, legal and competitive analysis
> - [`starter/premium_metrics.py`](./starter/premium_metrics.py) — verified reference implementations

---

## Table of contents

1. [Executive summary](#1-executive-summary)
2. [Problem statement and evidence](#2-problem-statement-and-evidence)
3. [Goals and non-goals](#3-goals-and-non-goals)
4. [Users and personas](#4-users-and-personas)
5. [Constraints](#5-constraints)
6. [Product principles](#6-product-principles)
7. [Feature specification](#7-feature-specification)
8. [User stories](#8-user-stories)
9. [What we compute](#9-what-we-compute)
10. [Technical architecture](#10-technical-architecture)
11. [iOS architecture — TCA](#11-ios-architecture--the-composable-architecture)
12. [Android architecture — MVI](#12-android-architecture--mvi)
13. [Web architecture](#13-web-architecture)
14. [Data model and storage](#14-data-model-and-storage)
15. [Monetization](#15-monetization)
16. [Compliance as product requirements](#16-compliance-as-product-requirements)
17. [Roadmap](#17-roadmap)
18. [Success metrics](#18-success-metrics)
19. [Risks and kill criteria](#19-risks-and-kill-criteria)
20. [Open questions](#20-open-questions)

---

## 1. Executive summary

### 1.1 What we're building

A **free, local-first mobile app** that reads sensor data directly from a WHOOP band over
Bluetooth, computes health analytics **on the device**, and keeps a permanent, portable history
that survives subscription lapses, hardware upgrades, and vendor switches.

Native **iOS** (Swift/SwiftUI/TCA) and **Android** (Kotlin/Compose/MVI) apps do the capture. A
**web dashboard** provides deep analysis over synced or imported data — it cannot do Bluetooth on
iOS and is therefore never the capture surface.

### 1.2 Why it can exist

WHOOP's paywall is enforced in its **app and cloud**, not on the band. The strap has **no
application-layer authentication and no payload encryption** — data integrity is plain CRC. A
device owner can read their own sensor stream over standard BLE.

### 1.3 Why someone would choose it

Four things no vendor can offer, because their business model forbids it — not because the
technology is hard:

1. **Your history survives everything** — lapsed subscriptions, new hardware, switching brands.
2. **Recompute the past** with improved algorithms, and see the diff.
3. **Scores that explain themselves**, with outlier-robust baselines that one bad night can't poison.
4. **Honest self-experimentation** with real statistics rather than naive correlation.

### 1.4 What we deliberately will not build

ECG, AFib/arrhythmia verdicts, blood-pressure estimates, and sleep-apnea inference. These are the
features that convert a wellness app into a regulated medical device. See [§5.4](#54-the-medical-device-line).

### 1.5 Business model

Free core with **nothing essential withheld**. Optional supporter tier at **$29/year**.
**No advertising, ever** — it is prohibited by Apple, unusable under GDPR, earns ~10× less than
subscription in this category, and destroys the privacy positioning that is the entire product.

---

## 2. Problem statement and evidence

### 2.1 The core problem

**You bought the hardware. Stop paying and it stops working.** WHOOP bundles the strap into a
mandatory membership; when it lapses the band stops syncing and the app stops showing new data. The
device you own goes dark.

Beyond lock-in, four documented grievances shape the product:

| Problem | Evidence |
|---|---|
| **Scores are a black box** | Peer-reviewed critique: *"companies such as Garmin and Polar execute and make available scientific white papers for most metrics… WHOOP does not follow this same level of transparency."* Forum thread title: *"Nonsensical recovery score - make it make sense."* |
| **One bad night poisons weeks** | Multiple threads report a single HRV spike shifting the personal baseline, producing red recoveries for weeks or months. |
| **Scores change under you** | 4.0 → 5.0 upgrades produced *"HRV dropped almost 50%"* and *"Strain Significantly Lower Than 4.0"* with no way to reconcile the series. |
| **Your data isn't reachable** | Continuous HR, intraday HRV, raw PPG, Strength Trainer sets/reps, journal entries and weight history are in **neither** the API **nor** the CSV export. Export is throttled to once per 24h. |

### 2.2 Market context

- WHOOP: **2.5M+ members**, $1.1B annualized bookings, $10.1B valuation.
- Estimated **~500,000 lapsed straps per year** (modeled from Oura's disclosed 80% year-1 renewal — an order-of-magnitude estimate, not a WHOOP figure).
- **Garmin's CIRQA ($199, no subscription) sold out immediately** — subscription-free demand is real.
- Existing open-source projects (`ryanbr/noop` 544★, `OpenStrap/edge` 418★) proved demand and press
  interest but **neither reached an app store**.

### 2.3 Why now

Community reverse-engineering has made the protocol tractable. The 4.0 is fully documented; the 5.0
is partially documented and actively progressing. The remaining gap is a **polished, trustworthy,
store-distributed product** — which nobody has built.

---

## 3. Goals and non-goals

### 3.1 Goals

| # | Goal | Success looks like |
|---|---|---|
| G1 | A lapsed or active WHOOP band produces useful daily metrics with no subscription | User completes onboarding → sees recovery/strain/sleep within 24h |
| G2 | Data never leaves the device unless the user explicitly opts in | Zero network calls containing health data in the free tier; verifiable |
| G3 | Every score is explainable | Every score view has a "why this number" breakdown with inputs and weights |
| G4 | History is permanent and portable | Full export in open formats at any time; no data loss on any transition |
| G5 | Algorithms improve without rewriting the past silently | Versioned algorithms; explicit user-initiated recompute; diffs shown |
| G6 | Legally and regulatorily defensible | Clean-room record; FTO opinion; no medical claims; coined name |

### 3.2 Non-goals

| # | Non-goal | Rationale |
|---|---|---|
| N1 | Replicating WHOOP's exact scores | Proprietary, and reproducing them invites copyright/patent exposure. We compute our own, from published science. |
| N2 | ECG, AFib, blood pressure, apnea detection | Medical-device regulation. See [§5.4](#54-the-medical-device-line). |
| N3 | Cloud-first architecture | Contradicts the core value proposition. |
| N4 | Advertising | Prohibited, unprofitable, off-brand. See [§15](#15-monetization). |
| N5 | Marketing as a "subscription replacement" | Manufactures the inducement element of tortious interference. |
| N6 | Multi-vendor fusion at launch | Already contested by funded competitors. Revisit post-PMF at the *raw-signal* level. |
| N7 | Real-time 24/7 background monitoring | Not deliverable on either mobile platform. See [§10.4](#104-background-execution-reality). |

---

## 4. Users and personas

### 4.1 Primary: "The Lapsed Owner"
Owns a WHOOP, cancelled or is about to. Feels the hardware was held hostage. Technically
comfortable but not a developer. **Wants:** their band to keep working, and their history back.
**Success:** working daily metrics inside a week, zero recurring cost.

### 4.2 Primary: "The Skeptical Optimizer"
Active WHOOP subscriber. Doesn't trust the Recovery score. Has felt great on a 30% recovery and
terrible on 90%. **Wants:** to see the inputs, adjust the weights, and know when the algorithm is
wrong *for them*. **Success:** identifies a systematic personal bias and corrects it.

### 4.3 Secondary: "The Data Archaeologist"
Years of wearable history across brands. Frustrated that switching devices resets everything.
**Wants:** one continuous timeline, recomputable under consistent algorithms. **Success:** a
multi-year unified series.

### 4.4 Secondary: "The Self-Experimenter"
Runs personal experiments — supplements, sleep timing, alcohol, training. Knows WHOOP's Journal
insights are naive correlation. **Wants:** randomization, washout, confidence intervals, and to be
told when there isn't enough data. **Success:** a defensible personal answer to one real question.

### 4.5 Explicitly not a target
Anyone seeking medical diagnosis, arrhythmia screening, or blood-pressure monitoring. The app
states this plainly and routes them to clinical devices.

---

## 5. Constraints

### 5.1 Hard technical constraints

| Constraint | Consequence |
|---|---|
| **Web Bluetooth is unavailable in every browser on iOS** (WebKit mandate; Safari has never supported it) | Web can never be the capture surface. Native apps are mandatory. |
| **The 5.0 bonds to exactly one device at a time** | Pairing to our app **unpairs the official WHOOP app**. This is a deliberate, irreversible-feeling onboarding moment requiring explicit informed consent. |
| **Background BLE is unreliable on both platforms** | Design for periodic foreground sync; never promise continuous monitoring. |
| **5.0 protocol coverage is incomplete** | Both existing projects call 5.0 support experimental. **Must be validated in Phase 1 before further investment.** |
| **SpO₂ / skin temp arrive as uncalibrated ADC counts** | Report as relative trend only. Never emit absolute % or °C. |
| **Firmware updates can break BLE access** | Version-detect, fail gracefully, communicate honestly. |

### 5.2 Licensing constraints

| Source | License | Usable? |
|---|---|---|
| `OpenStrap/protocol`, `OpenStrap/edge`, `Sophonbot0/whoop-vault` | **MIT** | ✅ **Yes** — our base |
| `ryanbr/noop`, `tanarchytan/noop`, `whoop-rs` | **PolyForm Noncommercial** | ❌ No (commercial use outside the grant = infringement) |
| `goose`, `my-whoop` | **No license** = all rights reserved | ❌ No |
| `hrv-analysis` | GPL-3.0 | ❌ No (copyleft + App Store friction) |
| NeuroKit2 | MIT | ✅ Yes (reference for porting) |

**Requirement:** CI enforces a license allowlist (MIT / Apache-2.0 / BSD / ISC / Zlib). GPL, AGPL,
LGPL and non-commercial licenses fail the build.

### 5.3 Naming requirements

- Coined or arbitrary; **zero WHOOP morphemes**. Cleared in Classes 9/42/44 across US/EU/UK.
- WHOOP referenced **only** in plain-text compatibility copy, never stylized, never with the logo:
  > Works with WHOOP® 4.0 and 5.0. Independent and unofficial — not affiliated with, endorsed by, or
  > connected to WHOOP, Inc. WHOOP is a trademark of WHOOP, Inc.
- Domain: `<brand>.app`. Never `whoopalternative.com`.
- **UI must be visually distinct** — different information architecture, palette, typography, and
  metric names. WHOOP is currently litigating app look-and-feel and has won a trade dress injunction.

### 5.4 The medical-device line

**Never surface:** arrhythmia/AFib verdicts, ECG waveforms or interpretation, blood-pressure
estimates, sleep-apnea inference — *regardless of technical feasibility*. The strap emits
`heartKeyArrhythmiaCheckResult` including an `afibDetected` value; **we do not decode or display it.**

**Claim vocabulary — enforced in code review, copy review, and store metadata review:**

| ✅ Permitted | 🛑 Banned |
|---|---|
| strain, effort, recovery, readiness, sleep quality | detect, diagnose, screen, monitor for |
| "trending higher than your baseline" | "abnormal", "elevated", "high blood pressure" |
| "consider resting today" | arrhythmia, AFib, apnea, hypoxia |
| relative, personal, unitless | any numeric clinical threshold |

**Requirement:** a lint rule scans user-facing strings against the banned list and fails CI.

### 5.5 Legal gating items (block monetized development)

- [ ] **FTO opinion on WHOOP's patent portfolio.** WHOOP is currently asserting four patents on
      physiological-data analysis producing exercise and sleep recommendations. **Patents have no
      reverse-engineering, interoperability, fair-use, or independent-creation defence.** This is the
      single highest-severity item.
- [ ] **Read WHOOP's Terms of Use and device EULA** (*Davidson v. Jung*: a EULA can waive §1201(f)).
- [ ] **Clear the coined name.**
- [ ] **Apple App Review pre-submission inquiry** on Guideline 5.2.1 (external hardware).
- [ ] **Documented clean room** — facts team (touches WHOOP artifacts, produces wire spec) strictly
      separated from implementation team (never touches WHOOP artifacts). Dated captures, retail
      receipts, no ToU acceptance by the facts team.

---

## 6. Product principles

1. **Local by default.** Health data leaves the device only on explicit, revocable, per-feature opt-in.
2. **Explain everything.** Any number a user sees can be decomposed into its inputs and weights.
3. **Never fabricate precision.** Uncalibrated is reported as relative. Insufficient data says so.
4. **The past is immutable; interpretations are versioned.** Raw data is append-only. Algorithms are
   versioned. Recomputation is user-initiated and shows a diff.
5. **Free tier is genuinely complete.** Paid unlocks convenience and depth, never core function.
6. **No dark patterns.** No ads, no upsell interstitials, no engagement mechanics, no streaks-as-guilt.
7. **Honest about being wrong.** Where our score disagrees with how the user feels, we surface it and
   learn, rather than insisting.

---

## 7. Feature specification

### 7.1 P0 — Launch (free tier)

| ID | Feature | Description |
|---|---|---|
| **F-01** | Band pairing & onboarding | Discover, bond, and connect a WHOOP 4.0/5.0. Explicit consent screen for the one-device-bond trade-off. |
| **F-02** | Live view | Real-time HR, R-R intervals, battery, signal quality while foregrounded. |
| **F-03** | History drain | `SET_CLOCK` → batch sync → ACK loop, resumable from cursor. Weeks of per-second records. |
| **F-04** | Raw store | Append-only local storage of decoded records + original bytes. |
| **F-05** | Nightly aggregates | RHR, lnRMSSD (deepest-sleep window), respiratory rate, skin-temp deviation, sleep duration, SRI. |
| **F-06** | Recovery score | 0–100 from personal baselines. **With full input breakdown.** |
| **F-07** | Strain / load | Banister TRIMP + Edwards zone TRIMP, mapped to a bounded scale fit to the user's own distribution. |
| **F-08** | Sleep analysis | Actigraphy sleep/wake (Cole-Kripke / Sadeh) + HR-assisted staging, with honest accuracy caveats. |
| **F-09** | **"Why this number"** | ⭐ Every score decomposes into contributions, baselines, z-scores, and confidence. |
| **F-10** | **Outlier-robust baselines** | ⭐ Median/MAD with winsorization. One bad night cannot poison weeks. |
| **F-11** | Export | JSON + CSV + SQLite of everything, including raw bytes. One tap, no throttle. |
| **F-12** | Health platform sync | Optional write to Apple Health / Health Connect. |
| **F-13** | Signal quality gate | PPG quality + motion gating; refuse to score windows that fail. |
| **F-14** | Data survivorship | Everything works offline forever. No account required. No feature expires. |

### 7.2 P1 — Differentiation (first major update)

| ID | Feature | Description |
|---|---|---|
| **F-20** | **Felt-state logging** | ⭐ Quick daily "how do you actually feel" (1–5 + tags). |
| **F-21** | **Score reconciliation** | ⭐ Detect systematic disagreement between our score and felt state; surface it; offer recalibration. |
| **F-22** | **Algorithm versioning** | ⭐ Every score stamped with an algorithm version. Never silently rewritten. |
| **F-23** | **Retroactive recompute** | ⭐ Re-run the full history under a new version, with a visual diff of what changed and why. |
| **F-24** | Journal / behaviors | Log behaviors (alcohol, caffeine, late meals, travel, supplements). |
| **F-25** | ACWR training load | Acute:chronic workload ratio — a standard sports-science metric WHOOP lacks. |
| **F-26** | Illness early-warning | NightSignal FSM (3/4 bpm, two consecutive nights, expanding-median baseline) with **2-of-4 channel confirmation**. Framed as "your baseline has shifted", never as diagnosis. |
| **F-27** | Strength load | Volume/tonnage load from manual entry or import — addresses the cardio-only gap. |

### 7.3 P2 — Supporter tier

| ID | Feature | Description |
|---|---|---|
| **F-30** | **Rigorous n-of-1** | ⭐ Randomized, washout-controlled experiments with power analysis, effect-size CIs, and multiple-comparison correction. Says "not enough data yet" when true. |
| **F-31** | Multi-device sync | E2E-encrypted sync across the user's own devices. |
| **F-32** | Encrypted backup | Opt-in, zero-knowledge. |
| **F-33** | Web deep-dive | Full-history exploration, correlation matrices, custom charts. |
| **F-34** | **Cross-vendor continuity** | ⭐ Import Garmin/Oura/Apple Health history; unify onto one timeline and one baseline. |
| **F-35** | Custom weights | User-adjustable recovery model inputs. |
| **F-36** | Priority device support | Faster support for new firmware/hardware. |

⭐ = differentiator no competitor currently offers.

### 7.4 Explicitly excluded

ECG · AFib/arrhythmia verdicts · blood pressure · sleep-apnea detection · any clinical threshold ·
advertising · social feed · leaderboards · engagement streaks.

---

## 8. User stories

Format: **As a** [persona], **I want** [capability], **so that** [outcome]. AC = acceptance criteria.

### 8.1 Onboarding

**US-01 — Pair my band**
*As a Lapsed Owner, I want to connect my WHOOP to the app, so that it starts working again.*
- AC1: App detects model (4.0 vs 5.0/MG) and shows model-specific pairing instructions.
- AC2: For 5.0, a **blocking consent screen** explains that bonding here will unpair the official
  WHOOP app, and requires explicit confirmation.
- AC3: Pairing instructions include the physical action ("tap the strap 5–8 times until the LED is
  solid blue").
- AC4: On success, the band's clock is set (`SET_CLOCK`) and confirmed via the `SET_RTC` event.
- AC5: On failure, a specific diagnostic is shown — not "something went wrong".

**US-02 — Understand the trade-off before I commit**
*As a Skeptical Optimizer, I want to know exactly what I give up, so that I can decide.*
- AC1: Pre-pairing screen states plainly: one bond at a time; official app will disconnect; how to revert.
- AC2: Explains what we can and cannot read (no ECG, no calibrated SpO₂/temp).
- AC3: Links to full docs. No dark patterns, no pre-checked boxes.

**US-03 — Get my history off the band**
*As a Data Archaeologist, I want weeks of stored data pulled off, so that I start with real history.*
- AC1: Progress shown as records-per-second and estimated time remaining.
- AC2: Resumable after interruption from the saved cursor.
- AC3: Never re-requests an already-ACKed batch.
- AC4: Completion reports records imported and date range covered.

### 8.2 Daily use

**US-04 — See today's recovery**
*As any user, I want a daily readiness number, so that I can plan training.*
- AC1: Available within 5 minutes of a morning sync.
- AC2: Shows the score, the trend, and the confidence.
- AC3: If inputs are insufficient (< 14 nights of baseline), says so instead of showing a number.

**US-05 — Understand why the number is what it is** ⭐
*As a Skeptical Optimizer, I want the score decomposed, so that I can trust or challenge it.*
- AC1: Tapping any score opens a breakdown: each input, its raw value, its personal baseline, its
  z-score, its weight, and its contribution in points.
- AC2: Shows which input moved the score most versus yesterday.
- AC3: Links to the published method for each component.
- AC4: Shows the data-quality flag for each input.

**US-06 — Not have one bad night wreck my baseline** ⭐
*As any user, I want anomalies handled robustly, so that one outlier doesn't distort weeks.*
- AC1: Baselines use median + MAD, with winsorization at configurable percentiles.
- AC2: Values flagged as outliers are visibly marked and excluded from baseline updates.
- AC3: The user can inspect and manually include/exclude any flagged night.

**US-07 — Log how I actually feel** ⭐
*As a Skeptical Optimizer, I want to record my subjective state, so that the app can learn where it's wrong.*
- AC1: One-tap 1–5 rating plus optional tags, ≤10 seconds.
- AC2: Never blocks other functionality; never nags.
- AC3: After ≥30 paired observations, the app reports correlation between our score and felt state.

**US-08 — Be told when the app is systematically wrong about me** ⭐
*As a Skeptical Optimizer, I want to know about persistent bias, so that I can recalibrate.*
- AC1: After sufficient paired data, detects systematic over/under-estimation.
- AC2: Reports it plainly: "Your felt state averages 1.2 points better than our score on high-strain days."
- AC3: Offers a recalibration that adjusts weights, with a preview of the effect on history.
- AC4: Recalibration is reversible.

### 8.3 History and trust

**US-09 — Keep my scores stable when algorithms change** ⭐
*As a Data Archaeologist, I want versioned scores, so that my history means something.*
- AC1: Every stored score carries an algorithm version.
- AC2: App updates **never** silently rewrite historical scores.
- AC3: When a new version is available, the user is offered a recompute — never forced.

**US-10 — Recompute my whole history and see what changed** ⭐
*As a Data Archaeologist, I want to re-run history under a new algorithm, so that my series is consistent.*
- AC1: Recompute runs over all retained raw data.
- AC2: A diff view shows before/after distributions and the largest individual changes.
- AC3: The prior version's results are retained and restorable.
- AC4: Progress is shown; the operation is cancellable.

**US-11 — Get all my data out**
*As any user, I want a complete export, so that I'm never locked in.*
- AC1: One action exports everything — decoded records, raw bytes, scores (all versions), journal, settings.
- AC2: Open formats: JSON, CSV, SQLite.
- AC3: No rate limit, no account, no server round-trip.

### 8.4 Experimentation (supporter)

**US-12 — Run an honest experiment** ⭐
*As a Self-Experimenter, I want a properly designed n-of-1 trial, so that I get a real answer.*
- AC1: Guided setup: intervention, outcome metric, block length, washout.
- AC2: App randomizes assignment and tells the user what to do each day.
- AC3: Results report effect size with confidence intervals — not just "correlated".
- AC4: **Reports insufficient power honestly** and estimates how much longer is needed.
- AC5: Corrects for multiple comparisons across concurrent experiments.

### 8.5 Privacy and trust

**US-13 — Verify nothing leaves my device**
*As a privacy-motivated user, I want to confirm the local-first claim, so that I can trust it.*
- AC1: A privacy screen lists every network destination the app can contact and why.
- AC2: Free tier makes **zero** network calls containing health data.
- AC3: Any sync/backup is explicit opt-in, per-feature, revocable, and shows what is sent.
- AC4: Source of the analytics core is public and the build is reproducible.

**US-14 — Not be sold anything harmful**
*As any user, I want the app to stay in its lane, so that I'm not misled.*
- AC1: No medical claims anywhere in the product or metadata.
- AC2: If a metric is unreliable, the app says so at the point of display.
- AC3: No advertising, ever. No health data to any third party, ever.

---

## 9. What we compute

Full method and library detail is in [`analytics-stack.md`](./analytics-stack.md) and
[`premium-metrics.md`](./premium-metrics.md). Summary of scope:

| Metric | Inputs | Method | Confidence |
|---|---|---|---|
| Heart rate | PPG / device R-R | Device HR preferred; peak detection as fallback | High |
| **PRV** (not "HRV") | R-R intervals | RMSSD, SDNN, pNN50 after Kubios-style artifact correction. **Labeled PRV** — pulse rate variability ≠ HRV outside rest | High at rest |
| Resting HR | Nightly HR, steps==0, 00:00–07:00 | Mean of qualifying samples | High |
| Respiratory rate | R-R / PPG | RSA + amplitude modulation | Medium (sleep only) |
| Sleep/wake | Accelerometer | Cole-Kripke / Sadeh actigraphy | Medium |
| Sleep stages | Accel + HR + clock | ML staging | **Low** (κ ≈ 0.4–0.6; deep/REM least reliable) — labeled as estimates |
| Sleep Regularity Index | Sleep/wake series | Phillips 2017 formula | High |
| Recovery (0–100) | lnRMSSD, RHR, resp rate, sleep, temp Δ | Personal rolling baselines → signed z-scores → weighted sum → logistic squash | Medium |
| Strain / load | Continuous HR | Banister TRIMP + Edwards zone TRIMP → concave map | Medium |
| ACWR | 7-day vs 28-day load | Standard acute:chronic ratio | Medium |
| Skin temp deviation | Raw ADC | **Deviation from personal baseline only.** Never absolute °C | Medium (relative) |
| SpO₂ | Raw red/IR ADC | **Not shipped at launch.** Requires user-fitted calibration; wrist reflectance is unreliable | — |
| Fitness age | VO₂max estimate | HUNT/Nes non-exercise model, inverted against FRIEND norms | Medium |
| Stress | R-R + accel | Motion-gated RMSSD + √(Baevsky SI), z-scored vs time-of-day-stratified baseline | Medium |

**Implementation notes carried from research:**
- Baevsky's Stress Index is **not** in NeuroKit2 or pyhrv (NeuroKit2's `HRV_SI` is the *Slope Index*).
  Port our verified implementation from [`starter/premium_metrics.py`](./starter/premium_metrics.py).
- HUNT VO₂max expects a **seated** resting HR; nocturnal RHR inflates the estimate. Require a seated
  calibration reading or apply a documented offset.
- Signal-quality gating is **mandatory** before any HRV-derived metric.

---

## 10. Technical architecture

### 10.1 System overview

```
┌───────────────────────────────────────────────────────────────┐
│                      WHOOP BAND (BLE peripheral)              │
│   4.0: service 61080001-…    5.0/MG: service fd4b0001-…       │
└───────────────────────────────────────────────────────────────┘
                    │ BLE GATT (bonded on 5.0)
      ┌─────────────┴──────────────┐
      ▼                            ▼
┌───────────────┐          ┌───────────────┐
│  iOS app      │          │  Android app  │
│  Swift/TCA    │          │  Kotlin/MVI   │
│  CoreBluetooth│          │  Nordic BLE   │
└───────┬───────┘          └───────┬───────┘
        │                          │
        ├── Protocol decoder (ported from MIT OpenStrap/protocol)
        ├── Analytics core (versioned, pure, heavily tested)
        └── Local store (GRDB / Room, append-only raw + derived)
                    │
                    │ optional, opt-in, E2E-encrypted (supporter)
                    ▼
              ┌───────────┐        ┌────────────────────┐
              │ Sync relay│───────▶│  Web dashboard     │
              │ (zero-    │        │  read-only over    │
              │  knowledge)│        │  synced/imported   │
              └───────────┘        └────────────────────┘
```

### 10.2 Layer responsibilities

| Layer | Responsibility | Testability |
|---|---|---|
| **Transport** | BLE scan, bond, connect, MTU, notify subscription, reconnect | Mocked via protocol/interface |
| **Framing** | SOF detection, length + CRC-8, payload reassembly, CRC-32 | Pure — golden-vector tests |
| **Protocol** | Packet-type dispatch, command building, sequence/ACK, R24 decode | Pure — parity fixtures |
| **Sync orchestration** | SET_CLOCK → history drain → ACK loop → cursor persistence | State machine tests |
| **Storage** | Append-only raw, derived tables, migrations | Integration tests |
| **Analytics** | Baselines, scores, experiments — **versioned, pure functions** | Property + regression tests |
| **Presentation** | TCA reducers (iOS) / MVI store (Android) | Exhaustive state tests |

**Key principle: the analytics core is a pure, platform-free, versioned library.** All
differentiation lives there. It is published openly — it's the artifact people cite, fork, and
sponsor — and it is shared in *specification and test vectors* across platforms even where
implementations differ.

### 10.3 Protocol layer sourcing

`OpenStrap/protocol` is **MIT** and pure Dart. We **port** it (with attribution) to Swift and
Kotlin rather than depending on Flutter. Its `decode_parity_cases.json` oracle becomes our
**shared cross-platform test fixture** — both native decoders must produce byte-identical results
against it. This is the highest-leverage testing decision in the project.

### 10.4 Background execution reality

| Platform | What actually works |
|---|---|
| **iOS** | `UIBackgroundModes: bluetooth-central` + State Preservation & Restoration. Wakes on connection/notification events — **but not** after force-quit or a Bluetooth toggle. Roughly **10 seconds** of work per wake. |
| **Android** | Foreground service with a persistent notification + `BLUETOOTH_SCAN`/`CONNECT`. Fails if OS location services are off. Doze defers work. **OEM killers (Samsung "Sleeping apps") override everything.** |

**Design requirement:** the product must be fully usable with **periodic foreground syncs only**.
Background capture is an enhancement, never a dependency. Onboarding includes an Android
battery-optimization exemption flow. **No marketing copy promises continuous monitoring.**

---

## 11. iOS architecture — The Composable Architecture

**Stack:** Swift 6 · SwiftUI · [TCA 1.x](https://github.com/pointfreeco/swift-composable-architecture) ·
swift-dependencies · GRDB · CoreBluetooth · Swift Testing

### 11.1 Why TCA

BLE is a long-lived, event-driven, failure-prone side effect feeding a state machine — exactly what
TCA is designed for. Specifically:
- **Effect cancellation** maps cleanly to connection lifecycles.
- **`@Dependency`** makes the BLE stack swappable for deterministic tests without a physical band.
- **`TestStore`** exhaustively asserts state transitions — critical for a sync protocol with ACK
  loops and resumable cursors.
- **Composition** keeps the feature tree navigable as scope grows.

### 11.2 Feature tree

```
AppFeature
├── OnboardingFeature
│   ├── ModelSelectionFeature
│   ├── PairingConsentFeature      // the one-bond trade-off
│   └── PairingFeature
├── TodayFeature
│   ├── RecoveryCardFeature
│   ├── StrainCardFeature
│   ├── SleepCardFeature
│   └── ScoreBreakdownFeature      // ⭐ "why this number"
├── HistoryFeature
│   ├── TimelineFeature
│   └── RecomputeFeature           // ⭐ retroactive recompute + diff
├── ExperimentsFeature             // ⭐ n-of-1 (supporter)
├── JournalFeature                 // felt-state + behaviors
├── DeviceFeature
│   ├── LiveViewFeature
│   └── SyncFeature                // history drain state machine
└── SettingsFeature
    ├── PrivacyFeature             // network destinations disclosure
    └── ExportFeature
```

### 11.3 BLE as a dependency

```swift
import ComposableArchitecture

@DependencyClient
struct WhoopBLEClient {
    var scan: @Sendable () -> AsyncStream<DiscoveredStrap> = { .finished }
    var connect: @Sendable (_ id: UUID) async throws -> Void
    var disconnect: @Sendable () async -> Void
    var events: @Sendable () -> AsyncStream<StrapEvent> = { .finished }
    var send: @Sendable (_ command: StrapCommand) async throws -> Void
    var connectionState: @Sendable () -> AsyncStream<ConnectionState> = { .finished }
}

extension WhoopBLEClient: DependencyKey {
    static let liveValue = Self.live      // CoreBluetooth implementation
    static let testValue = Self()         // unimplemented — tests must override
    static let previewValue = Self.replaying(fixture: .twoWeeksOfRecords)
}

extension DependencyValues {
    var whoopBLE: WhoopBLEClient {
        get { self[WhoopBLEClient.self] }
        set { self[WhoopBLEClient.self] = newValue }
    }
}
```

**Rules:**
- `testValue` is **unimplemented**. Any test that touches BLE without overriding it fails loudly.
- `previewValue` replays a recorded fixture, so SwiftUI previews and demos work with no hardware.
- The live client owns the `CBCentralManager` and translates delegate callbacks into `AsyncStream`.

### 11.4 The sync reducer

The history drain is the most intricate state machine in the app. Sketch:

```swift
@Reducer
struct SyncFeature {
    @ObservableState
    struct State: Equatable {
        var phase: Phase = .idle
        var recordsImported: Int = 0
        var cursor: SyncCursor?
        var clockConfirmed = false
        @Presents var alert: AlertState<Action.Alert>?

        enum Phase: Equatable {
            case idle
            case settingClock
            case draining(progress: Double)
            case complete(records: Int)
            case failed(SyncError)
        }
    }

    enum Action {
        case startTapped
        case cancelTapped
        case strapEvent(StrapEvent)
        case batchDecoded(Result<Batch, SyncError>)
        case ackSent(batchID: UInt64)
        case alert(PresentationAction<Alert>)
        enum Alert: Equatable { case retry }
    }

    @Dependency(\.whoopBLE) var ble
    @Dependency(\.database) var database
    @Dependency(\.date.now) var now

    private enum CancelID { case eventStream, drain }

    var body: some ReducerOf<Self> {
        Reduce { state, action in
            switch action {
            case .startTapped:
                state.phase = .settingClock
                return .merge(
                    // Long-lived event subscription, cancelled on teardown.
                    .run { send in
                        for await event in ble.events() {
                            await send(.strapEvent(event))
                        }
                    }
                    .cancellable(id: CancelID.eventStream),

                    // Clock first — otherwise every timestamp is 1970.
                    .run { _ in
                        try await ble.send(.setClock(epoch: now))
                    }
                )

            case let .strapEvent(.rtcSet(confirmed)) where confirmed:
                state.clockConfirmed = true
                state.phase = .draining(progress: 0)
                return .run { [cursor = state.cursor] _ in
                    try await ble.send(.enterHighFreqSync)
                    try await ble.send(.sendHistoricalData(from: cursor))
                }
                .cancellable(id: CancelID.drain)

            case let .batchDecoded(.success(batch)):
                state.recordsImported += batch.records.count
                state.cursor = batch.cursor
                return .run { [token = batch.ackToken] send in
                    try await database.append(batch.records)
                    // Acknowledged write — without it the strap resends forever.
                    try await ble.send(.historicalDataResult(token: token))
                    await send(.ackSent(batchID: batch.id))
                }

            case .strapEvent(.historyComplete):
                state.phase = .complete(records: state.recordsImported)
                // Do NOT ack the completion marker.
                return .cancel(id: CancelID.drain)

            case .cancelTapped:
                state.phase = .idle
                return .merge(
                    .cancel(id: CancelID.drain),
                    .cancel(id: CancelID.eventStream)
                )

            case let .batchDecoded(.failure(error)):
                state.phase = .failed(error)
                state.alert = .syncFailed(error)   // cursor is retained → resumable
                return .cancel(id: CancelID.drain)

            default:
                return .none
            }
        }
        .ifLet(\.$alert, action: \.alert)
    }
}
```

**Invariants enforced by tests:**
- Clock is set and confirmed **before** any drain begins.
- Every batch is ACKed exactly once, with an acknowledged write.
- The completion marker is **never** ACKed.
- Cancellation at any point leaves a resumable cursor.
- A dropped connection mid-drain resumes without duplicate or missing records.

### 11.5 Testing

```swift
@Test
func syncSetsClockBeforeDraining() async throws {
    let events = AsyncStream.makeStream(of: StrapEvent.self)
    let sentCommands = LockIsolated<[StrapCommand]>([])

    let store = await TestStore(initialState: SyncFeature.State()) {
        SyncFeature()
    } withDependencies: {
        $0.whoopBLE.events = { events.stream }
        $0.whoopBLE.send = { cmd in sentCommands.withValue { $0.append(cmd) } }
        $0.date.now = Date(timeIntervalSince1970: 1_800_000_000)
    }

    await store.send(.startTapped) { $0.phase = .settingClock }
    #expect(sentCommands.value == [.setClock(epoch: 1_800_000_000)])

    events.continuation.yield(.rtcSet(confirmed: true))
    await store.receive(\.strapEvent) {
        $0.clockConfirmed = true
        $0.phase = .draining(progress: 0)
    }
}
```

**Test strategy:**
- **Golden vectors** — the decoder runs against OpenStrap's `decode_parity_cases.json`; results must
  match byte-for-byte.
- **Recorded sessions** — real BLE captures replayed through the full stack for regression testing.
- **Property tests** — analytics invariants (a score is always 0–100; adding an outlier moves a
  robust baseline by less than a bounded amount).
- **Exhaustive `TestStore`** — every reducer transition asserted.

### 11.6 Persistence

**GRDB** (MIT), with a `@Dependency`-wrapped repository. Raw records are append-only; derived scores
carry an `algorithm_version` and are recomputable. Uses SQLCipher for at-rest encryption, keyed via
Keychain with `kSecAttrAccessibleAfterFirstUnlock` (background writes must work).

---

## 12. Android architecture — MVI

**Stack:** Kotlin 2.x · Jetpack Compose · Coroutines/Flow · Hilt · Room · Nordic Android-BLE-Library ·
Turbine (Flow testing)

### 12.1 Why MVI (and how it mirrors TCA)

We deliberately mirror TCA's shape so the two apps stay conceptually aligned and specs/tests port
cleanly.

| TCA (iOS) | MVI (Android) |
|---|---|
| `State` | `data class UiState` |
| `Action` | `sealed interface Intent` |
| `Reducer` | `reduce(state, intent): State` |
| `Effect` | `suspend` work returning `Intent`s |
| `Store` | `ViewModel` + `StateFlow` |
| `@Dependency` | Hilt-injected interfaces |
| `TestStore` | Turbine assertions over `StateFlow` |

**Recommendation:** hand-rolled `MviViewModel` base class (small, dependency-free, exactly
TCA-shaped). [Orbit MVI](https://github.com/orbit-mvi/orbit-mvi) (Apache-2.0) is a reasonable
alternative if the team prefers a maintained framework.

### 12.2 Base pattern

```kotlin
abstract class MviViewModel<S : Any, I : Any, E : Any>(
    initialState: S,
) : ViewModel() {

    private val _state = MutableStateFlow(initialState)
    val state: StateFlow<S> = _state.asStateFlow()

    // One-shot effects (navigation, toasts) — never part of state.
    private val _effects = Channel<E>(Channel.BUFFERED)
    val effects: Flow<E> = _effects.receiveAsFlow()

    protected abstract suspend fun handle(intent: I, state: S): S

    fun send(intent: I) {
        viewModelScope.launch {
            _state.update { current -> handle(intent, current) }
        }
    }

    protected suspend fun emitEffect(effect: E) = _effects.send(effect)
}
```

### 12.3 Sync feature

```kotlin
sealed interface SyncIntent {
    data object Start : SyncIntent
    data object Cancel : SyncIntent
    data class StrapEvent(val event: com.brand.protocol.StrapEvent) : SyncIntent
    data class BatchDecoded(val result: Result<Batch>) : SyncIntent
}

data class SyncUiState(
    val phase: Phase = Phase.Idle,
    val recordsImported: Int = 0,
    val cursor: SyncCursor? = null,
    val clockConfirmed: Boolean = false,
) {
    sealed interface Phase {
        data object Idle : Phase
        data object SettingClock : Phase
        data class Draining(val progress: Float) : Phase
        data class Complete(val records: Int) : Phase
        data class Failed(val error: SyncError) : Phase
    }
}

@HiltViewModel
class SyncViewModel @Inject constructor(
    private val ble: WhoopBleClient,
    private val repository: RecordRepository,
    private val clock: Clock,
) : MviViewModel<SyncUiState, SyncIntent, SyncEffect>(SyncUiState()) {

    private var eventJob: Job? = null
    private var drainJob: Job? = null

    override suspend fun handle(intent: SyncIntent, state: SyncUiState): SyncUiState =
        when (intent) {
            is SyncIntent.Start -> {
                eventJob = viewModelScope.launch {
                    ble.events().collect { send(SyncIntent.StrapEvent(it)) }
                }
                viewModelScope.launch {
                    ble.send(StrapCommand.SetClock(clock.now()))
                }
                state.copy(phase = SyncUiState.Phase.SettingClock)
            }

            is SyncIntent.StrapEvent -> when (val e = intent.event) {
                is StrapEvent.RtcSet -> if (e.confirmed) {
                    drainJob = viewModelScope.launch {
                        ble.send(StrapCommand.EnterHighFreqSync)
                        ble.send(StrapCommand.SendHistoricalData(state.cursor))
                    }
                    state.copy(clockConfirmed = true,
                               phase = SyncUiState.Phase.Draining(0f))
                } else state

                is StrapEvent.HistoryComplete -> {
                    drainJob?.cancel()   // never ACK the completion marker
                    state.copy(phase = SyncUiState.Phase.Complete(state.recordsImported))
                }

                else -> state
            }

            is SyncIntent.BatchDecoded -> intent.result.fold(
                onSuccess = { batch ->
                    viewModelScope.launch {
                        repository.append(batch.records)
                        ble.send(StrapCommand.HistoricalDataResult(batch.ackToken))
                    }
                    state.copy(
                        recordsImported = state.recordsImported + batch.records.size,
                        cursor = batch.cursor,
                    )
                },
                onFailure = { state.copy(phase = SyncUiState.Phase.Failed(it.toSyncError())) },
            )

            is SyncIntent.Cancel -> {
                drainJob?.cancel(); eventJob?.cancel()
                state.copy(phase = SyncUiState.Phase.Idle)
            }
        }
}
```

### 12.4 BLE layer

**Nordic Android-BLE-Library** (`no.nordicsemi.android:ble`, BSD-3) — it handles the request queue,
bonding, MTU negotiation and reconnection logic that hand-rolled `BluetoothGatt` code gets wrong.
Wrapped behind a `WhoopBleClient` interface exposing `Flow`s, so it is fully fakeable.

```kotlin
interface WhoopBleClient {
    fun scan(): Flow<DiscoveredStrap>
    suspend fun connect(address: String)
    suspend fun disconnect()
    fun events(): Flow<StrapEvent>
    suspend fun send(command: StrapCommand)
    fun connectionState(): Flow<ConnectionState>
}
```

**Foreground service** for sync with a persistent notification (`foregroundServiceType="connectedDevice"`).
Onboarding includes an OEM-aware battery-optimization exemption flow (Samsung's "Sleeping apps" is
the common failure).

### 12.5 Persistence

**Room** with SQLCipher, keyed via Android Keystore. Same schema as iOS ([§14](#14-data-model-and-storage))
so exports are byte-compatible across platforms.

### 12.6 Testing

- **Turbine** over `StateFlow` for reducer assertions (the `TestStore` analogue).
- **Same golden vectors** as iOS — `decode_parity_cases.json` is the shared oracle. A cross-platform
  CI job asserts both decoders agree.
- **Fake `WhoopBleClient`** replaying recorded sessions.

---

## 13. Web architecture

**Explicitly not a capture surface.** Web Bluetooth does not exist on iOS in any browser.

**Stack:** TypeScript · SvelteKit or React · SQLite-WASM · Vite · deployed as a static site.

**Capabilities:**
- **Import** an export bundle from mobile (drag-and-drop). Works with zero backend.
- **Deep analysis** — full-history charts, correlation matrices, experiment results.
- **Supporter sync** — read from the E2E-encrypted relay, decrypted client-side.
- **Web Bluetooth on desktop Chrome only**, as a clearly-labeled bonus path for Linux/Windows users.

**Constraint:** the free web tier processes everything **client-side**. No health data touches a
server without explicit supporter opt-in, and even then it is encrypted before it leaves the device.

---

## 14. Data model and storage

### 14.1 Core tables

```sql
-- Append-only. Never updated, never deleted by the app.
CREATE TABLE raw_record (
    id              INTEGER PRIMARY KEY,
    device_id       TEXT    NOT NULL,
    ts_epoch        INTEGER NOT NULL,
    ts_subsec       INTEGER,
    record_version  INTEGER NOT NULL,
    raw_bytes       BLOB    NOT NULL,   -- original frame, always retained
    decoded_json    TEXT,               -- NULL if undecodable at capture time
    ingested_at     INTEGER NOT NULL
);
CREATE INDEX idx_raw_ts ON raw_record(device_id, ts_epoch);

-- Derived, versioned, recomputable. Safe to delete and rebuild.
CREATE TABLE derived_score (
    id                INTEGER PRIMARY KEY,
    date              TEXT    NOT NULL,
    score_type        TEXT    NOT NULL,  -- recovery | strain | sleep | stress
    value             REAL    NOT NULL,
    algorithm_version TEXT    NOT NULL,
    inputs_json       TEXT    NOT NULL,  -- full breakdown for "why this number"
    confidence        REAL,
    computed_at       INTEGER NOT NULL,
    UNIQUE(date, score_type, algorithm_version)
);

CREATE TABLE baseline (
    metric            TEXT    NOT NULL,
    window_days       INTEGER NOT NULL,
    as_of_date        TEXT    NOT NULL,
    median            REAL    NOT NULL,
    mad               REAL    NOT NULL,
    n_included        INTEGER NOT NULL,
    n_excluded        INTEGER NOT NULL,  -- outliers, surfaced in the UI
    PRIMARY KEY (metric, window_days, as_of_date)
);

CREATE TABLE felt_state (
    date        TEXT PRIMARY KEY,
    rating      INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    tags_json   TEXT,
    note        TEXT,
    logged_at   INTEGER NOT NULL
);

CREATE TABLE experiment (
    id             INTEGER PRIMARY KEY,
    name           TEXT    NOT NULL,
    intervention   TEXT    NOT NULL,
    outcome_metric TEXT    NOT NULL,
    block_days     INTEGER NOT NULL,
    washout_days   INTEGER NOT NULL,
    randomization_seed INTEGER NOT NULL,   -- reproducible assignment
    started_at     INTEGER NOT NULL,
    ended_at       INTEGER
);
```

### 14.2 Design rules

1. **`raw_record` is sacred.** Append-only, always retains original bytes. This is what makes
   retroactive recompute possible and is the core differentiator.
2. **`derived_score` is disposable.** Uniqueness on `(date, type, version)` means multiple versions
   coexist — enabling the diff view.
3. **`inputs_json` is mandatory**, not optional. It is what powers "why this number", and it must be
   captured at compute time.
4. **Baselines record exclusions**, so the UI can show which nights were treated as outliers and let
   the user override.
5. **Encryption at rest on both platforms** (SQLCipher), keyed from platform keystores.

---

## 15. Monetization

### 15.1 Model

| Tier | Price | Contents |
|---|---|---|
| **Free** | $0 | BLE capture, history drain, all core scores, "why this number", robust baselines, full local history, complete export, health-platform sync. **No ads. No SDKs. No account.** |
| **Supporter** | **$29/year** | Multi-device sync, encrypted backup, rigorous n-of-1 experiments, web deep-dive, cross-vendor import, custom score weights, priority device support. |
| **Donations** | — | Liberapay / GitHub Sponsors. A floor, not a plan. |

### 15.2 Pricing rationale

**$29/year, annual only.** This sits precisely on the market anchor and is deliberate on three counts:

1. **It matches the direct comparable.** Users will not price this against WHOOP's ~$30/month —
   they will price it against **Athlytic at $29.99/yr**, the closest "turn hardware you already own
   into WHOOP-style scores" product. Matching that anchor removes price from the decision and puts
   the comparison where we win: local-first, explainable, and permanent history.
2. **Annual-only is the stronger structure, not a compromise.** Annual plans take **60.6%** of Health
   & Fitness subscriptions, and annual subscribers churn **48% after year one versus 79% for
   monthly** — roughly 3× more valuable over 24 months. Offering monthly would mostly cannibalise
   annual with a worse-retaining subscriber.
3. **It reinforces the positioning.** A single low annual price is legible and unaggressive. The
   product's pitch is that you shouldn't pay rent on hardware you own; a monthly meter works against
   that message.

**Framing for marketing:** *"About the cost of one month of the thing you're replacing — once a
year."* Note this frames the **price**, not an instruction to cancel anything — see
[§3.2 N5](#32-non-goals) on tortious interference.

**Anchors:** HRV4Training $9.99 once · **Athlytic $29.99/yr** · Kygo $39.99/yr · Vora Pro $89.99/yr ·
Bevel Pro $99.99/yr · Stryd $129/yr · TrainingPeaks $134.99/yr · WHOOP $199–359/yr.

**Revisit criteria.** Add a monthly tier only if post-launch data shows meaningful demand for trial
flexibility that the free tier does not already satisfy. Since the free tier is genuinely complete,
a monthly plan has little job to do here. Price increases, if ever, apply to new subscribers only —
existing supporters keep their rate.

### 15.3 Why not ads — settled

Prohibited by **Apple Guideline 5.1.3** (which covers "data gathered in the health, fitness, and
medical research context" — broader than HealthKit), banned by Google Play, and unusable under
**GDPR Article 9**. Earns ~10× less than subscription per install in this category. And this
audience treats ads as *the* privacy risk — the enforcement record (GoodRx $1.5M + permanent ban;
BetterHelp $7.8M; *Frasco v. Flo* jury verdict against Meta under CIPA at $5,000/violation) makes
it an existential risk, not a revenue line.

**Requirement:** no advertising, analytics, attribution, or crash SDK ever receives health data, a
health-derived value, or a health-linked identifier. Preferably: no third-party SDKs at all in the
free tier.

### 15.4 Store economics

15% under Apple's Small Business Program and Google Play's equivalent (both apply below $1M/yr), so
**net ≈ $24.65 per supporter per year**.

| Engaged MAU | 5% conversion | 10% conversion |
|---|---|---|
| 5,000 | $6,200 net | $12,300 net |
| 20,000 | $24,700 net | $49,300 net |
| 50,000 | $61,600 net | $123,300 net |

At 5,000 engaged users and 10% conversion this is comparable to the *optimistic* advertising case at
the same scale — with none of the legal exposure, no ad SDK, and no contradiction of the privacy
positioning.

---

## 16. Compliance as product requirements

These are engineering requirements, not legal footnotes.

| ID | Requirement | Verification |
|---|---|---|
| **C-01** | No health data to any third party, ever | Network allowlist test in CI; charles/mitm audit before each release |
| **C-02** | No advertising SDK in any build | Dependency scan in CI |
| **C-03** | License allowlist (MIT/Apache-2.0/BSD/ISC/Zlib) enforced | CI fails on GPL/AGPL/LGPL/non-commercial |
| **C-04** | No banned medical vocabulary in user-facing strings **or store metadata** | String lint in CI; manual metadata review per release |
| **C-05** | Arrhythmia/ECG/BP/apnea fields never decoded or displayed | Code review checklist; explicit test asserting these opcodes are unhandled |
| **C-06** | Every network destination disclosed in-app | Privacy screen generated from the allowlist, not hand-maintained |
| **C-07** | Sync/backup is explicit, per-feature, revocable opt-in | Consent state machine tests |
| **C-08** | GDPR Art. 20 export + Art. 17 deletion | One-tap export; one-tap full local wipe |
| **C-09** | WA MHMDA-grade consent (separate collect / share / sell; we never sell) | Consent records with timestamps |
| **C-10** | Clean-room record maintained | Facts-team spec documents; dated captures; retail receipts |
| **C-11** | Attribution for MIT-derived code (OpenStrap) | In-app acknowledgements screen |
| **C-12** | Visually distinct from WHOOP's app | Design review sign-off before each release |

---

## 17. Roadmap

### Phase 0 — De-risk *(blocks everything)*
FTO opinion · read WHOOP ToU/EULA · clear the name · Apple pre-submission inquiry · establish the
clean room.
**Exit:** legal green light, or a decision to build the non-commercial version instead.

### Phase 1 — Prove the hardware *(4–6 weeks)*
Port `OpenStrap/protocol` to Swift + Kotlin against the shared parity fixture. Reliable 5.0 capture.
Validate the two open protocol questions ([§20](#20-open-questions)). Buy a **Polar H10** for
ECG-derived ground truth.
**Exit:** 14 consecutive days of clean capture from a 5.0, validated against chest-strap R-R.
**Kill criterion:** if 5.0 coverage proves inadequate, stop.

### Phase 2 — Analytics core *(6–8 weeks)*
Versioned, pure, property-tested library. Robust baselines, all P0 scores, `inputs_json` breakdown.
Published openly.
**Exit:** scores computed for the Phase 1 dataset; regression suite green.

### Phase 3 — Free apps *(10–14 weeks)*
iOS (TCA) + Android (MVI). All P0 features. **Submit to App Store early with a minimal build to test
5.2.1 review** — do not defer this discovery.
**Exit:** both apps in stores, or a documented decision to ship via TestFlight/sideload at hobby scale.

### Phase 4 — Differentiate *(8–12 weeks)*
F-20 through F-27: felt-state reconciliation, algorithm versioning, retroactive recompute, ACWR,
illness early-warning.
**Exit:** a user can recompute a full history and see the diff.

### Phase 5 — Supporter tier *(6–8 weeks)*
n-of-1 engine, sync, encrypted backup, web dashboard, cross-vendor import.
**Exit:** paid tier live; first cohort retained 90 days.

---

## 18. Success metrics

### 18.1 Product health

| Metric | Target (12 months) |
|---|---|
| Successful pairing rate (attempts → first sync) | > 80% |
| Day-7 retention (paired users) | > 50% |
| Day-30 retention | > 35% |
| Sync reliability (attempts → complete, no data loss) | > 95% |
| Median time from install to first recovery score | < 24h |

### 18.2 Differentiation

| Metric | Target |
|---|---|
| % of active users who open "why this number" ≥ once/week | > 40% |
| % logging felt state ≥ 3×/week | > 25% |
| % who have run a retroactive recompute | > 15% |
| Supporter conversion (engaged MAU → paid) | 5–10% |

### 18.3 Trust

| Metric | Target |
|---|---|
| Health-data network calls in the free tier | **0** — non-negotiable |
| Medical-claim violations found in review | **0** |
| Store removals / IP complaints | **0** |

### 18.4 Business

Break-even ≈ **1,400 annual supporters** ($40,600 gross, ~$34,500 net at $29/yr less the 15% store
cut). At a 10% conversion rate that implies **~14,000 engaged monthly actives**.

Reference point: Intervals.icu supports a full-time developer at 160,000 users on a $4/mo optional
tier — so the bar is reachable, but it is a multi-year build, not a launch outcome.

---

## 19. Risks and kill criteria

| Risk | Severity | Mitigation | Kill criterion |
|---|---|---|---|
| **WHOOP patent assertion** | 🛑 Fatal | FTO opinion first; design around claims; consider omitting automated *recommendations* | FTO finds unavoidable infringement |
| **App Store 5.2.1 rejection** | 🛑 Fatal to commercial model | Pre-submission inquiry; strip mark from metadata; coined name | Rejected with no remedy → non-commercial only |
| **5.0 protocol coverage inadequate** | 🛑 Fatal | Validate in Phase 1 before further investment | Cannot achieve reliable 14-day capture |
| **Firmware update breaks BLE** | High | Version detection; graceful degradation; honest comms | Repeated unrecoverable breakage |
| **Trademark complaint** | High | Coined name, cleared before launch; referential use only | — |
| **License contamination** | High | CI allowlist; MIT-only base | — |
| **Litigation cost attrition** | High | Entity structure; insurance; *bleem! won every ruling and still went bankrupt* | Cost exceeds appetite |
| **Bond exclusivity friction** | Medium | Explicit informed consent; clear revert instructions | Pairing success < 50% |
| **Background BLE unreliability** | Medium | Design for foreground sync; never promise continuous | — |
| **Sleep staging accuracy** | Medium | Label as estimates; publish κ figures | — |

---

## 20. Open questions

**Must resolve in Phase 1:**
1. **What is the R-R timestamp resolution on the 5.0?** ~26 Hz PPG implies ~38 ms granularity, which
   is marginal for entropy-based metrics unless intervals are computed at higher internal resolution.
2. **Is the R-R stream raw or already artifact-corrected?** If firmware silently interpolates
   outliers, HRV looks fine while genuinely losing information. Test against a Polar H10.
3. **How complete is 5.0 coverage really?** Both existing projects say experimental with incomplete
   overnight inputs.
4. **Does the 5.0 expose raw dual-wavelength PPG**, or only a sleep-computed SpO₂? Determines whether
   SpO₂ is ever feasible.

**Must resolve in Phase 0:**
5. Which patents are asserted in *WHOOP v. Finerpoint* (D. Del. 1:26-cv-00289), and do they read on
   our design?
6. What exactly do WHOOP's ToU and device EULA say about reverse engineering, and who in the org has
   accepted them?
7. Will Apple accept a BLE-only client under 5.2.1 with WHOOP absent from all metadata?

**Product decisions:**
8. ~~Final pricing.~~ **Decided: $29/year, annual only.** See [§15.2](#152-pricing-rationale).
9. Do we pursue a **commercial dual-license** from the NOOP copyright holder, which would retire a
   critical risk and unlock a substantially more mature codebase?
10. Do we target a clinically-adjacent niche later (the Visible/ME-CFS model shows far higher
    willingness-to-pay) — and does that collide with [§5.4](#54-the-medical-device-line)?

---

*Reproduces published science, not WHOOP's proprietary algorithms. Not a medical device, not medical
advice. Not affiliated with WHOOP, Inc. Legal statements require counsel verification against
primary sources.*
