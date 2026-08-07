# Product Requirements Document — Multi-Device Edition

**Product:** A local-first analytics client for whatever wearable you already own
**Working codename:** `STRAND` *(placeholder — do not ship a name containing any vendor mark)*
**Status:** Draft for review · **Owner:** TBD · **Last updated:** 2026-08-07

> **This is an alternative framing to [`PRD.md`](./PRD.md), not a replacement.** That document
> specifies a WHOOP-only client. This one specifies the same engine supporting **many device types,
> one device per user**. Both are live options; keep both narratives.
>
> **Companion documents:** [`README.md`](./README.md) (WHOOP BLE protocol) ·
> [`analytics-stack.md`](./analytics-stack.md) (metric libraries) ·
> [`premium-metrics.md`](./premium-metrics.md) (paid-tier feature analysis) ·
> [`product-strategy.md`](./product-strategy.md) (market and legal analysis) ·
> [`starter/premium_metrics.py`](./starter/premium_metrics.py) (reference implementations)

---

## Table of contents

1. [What changed and why](#1-what-changed-and-why)
2. [Executive summary](#2-executive-summary)
3. [The fidelity tier model](#3-the-fidelity-tier-model)
4. [Device support matrix](#4-device-support-matrix)
5. [Goals and non-goals](#5-goals-and-non-goals)
6. [Users and personas](#6-users-and-personas)
7. [Competitive positioning](#7-competitive-positioning)
8. [Constraints](#8-constraints)
9. [Product principles](#9-product-principles)
10. [Feature specification](#10-feature-specification)
11. [User stories](#11-user-stories)
12. [What we compute, by tier](#12-what-we-compute-by-tier)
13. [Technical architecture](#13-technical-architecture)
14. [iOS architecture — TCA](#14-ios-architecture--tca)
15. [Android architecture — MVI](#15-android-architecture--mvi)
16. [Data model](#16-data-model)
17. [Monetization](#17-monetization)
18. [The AI position](#18-the-ai-position)
19. [Compliance](#19-compliance)
20. [Roadmap](#20-roadmap)
21. [Success metrics](#21-success-metrics)
22. [Risks](#22-risks)
23. [Open questions](#23-open-questions)

---

## 1. What changed and why

### 1.1 The distinction that matters

| | Aggregation *(rejected)* | Multi-device support *(this document)* |
|---|---|---|
| Model | One user, many devices, one merged score | Many users, **one device each** |
| TAM | 22% of device owners have 2+ devices, mostly complementary pairs (watch + scale) | **Everyone who owns any wearable** — ~46% of US adults |
| Competitor | Google Health (shipped May 2026, $9.99/mo, free with AI Pro) | Athlytic ($29.99/yr, **Apple Watch only**) |
| Core problem | Cross-device metrics are **not comparable** — Apple reports SDNN, others RMSSD, no valid conversion | **Does not arise** — see below |

### 1.2 The insight that makes this work

The research found cross-device metric disagreement to be **definitional, not merely noisy**. Apple
reports **SDNN**; Oura, WHOOP, Garmin and Fitbit report **RMSSD** — different physiological
quantities with no fixed conversion. Measurement windows differ too (deep sleep vs whole night vs
longest sleep vs opportunistic sampling). One vendor has published two contradictory definitions of
its own HRV metric.

That is fatal **if you merge two devices for one person**. It is **irrelevant if each user has one
device**, because the entire method rests on **personal baseline z-scores**: *how does today compare
to your own last 30 days, on this device?*

**That comparison is device-agnostic.** It works identically whether the underlying number is SDNN
or RMSSD, because the units cancel. You never compare across devices — only against the user's own
history on the same hardware.

**Consequence:** the single unsolvable problem in the aggregation model does not exist in this one.
What remains is per-device *calibration* (different baseline windows, outlier thresholds, sanity
ranges) — engineering, not science.

### 1.3 What else improves

- **Legal posture.** Launch on sanctioned APIs (HealthKit, Health Connect, Google Health, Oura).
  WHOOP-over-BLE becomes *one supported device among many* rather than the product's identity.
- **Distribution.** No longer "an app marketed to control WHOOP hardware" — which is precisely the
  Apple Guideline 5.2.1 trigger.
- **Naming.** No vendor mark needed anywhere near the brand.
- **Growth.** Each integration multiplies reach instead of deepening a single niche.

---

## 2. Executive summary

**What:** A free, local-first mobile app that connects to **one wearable you already own**, computes
health analytics **on the device**, and keeps a permanent, portable history that survives
subscription lapses, hardware upgrades, and vendor switches.

**Which devices:** Apple Watch and Polar first (both ungated), then WHOOP over BLE, then Fitbit,
Oura and Samsung. Garmin is blocked — its developer program closed to new applicants in 2026.

**Why choose it over the built-in app:**
1. **Your history survives everything** — cancelled subscriptions, new hardware, switching brands.
2. **Scores explain themselves** — every number decomposes into its inputs and weights.
3. **Outlier-robust baselines** — one bad night cannot poison weeks of scores.
4. **Recompute the past** when algorithms improve, and see exactly what changed.
5. **Nothing leaves your device** unless you explicitly opt in.

**Price:** Free core with nothing essential withheld. Optional supporter tier at **$29/year**.
No advertising, ever.

**Not building:** ECG, AFib/arrhythmia verdicts, blood-pressure estimates, sleep-apnea inference.
See [§8.4](#84-the-medical-device-line).

---

## 3. The fidelity tier model

**This is the central design concept.** Data sources differ enormously in what they expose. Rather
than flattening to a lowest common denominator or pretending they're equivalent, the app is
**capability-aware**: it computes the best metrics each source supports and tells the user which
tier they're in.

| Tier | What the source provides | What we can compute | Sources |
|---|---|---|---|
| **A — Raw** | Per-beat RR intervals, raw PPG, accelerometer | Everything. Full HRV from our own artifact correction, custom algorithms, **retroactive recomputation**, signal-quality gating | **Polar (BLE SDK)**, **WHOOP (BLE)** |
| **B — Intraday** | Frequent samples, 5-min arrays, some RR | Good HRV trends, sleep/wake, strain, robust baselines. Partial recompute | Oura API, Google Health (Fitbit), Health Connect Series records, Samsung |
| **C — Summary** | Daily aggregates only | Baselines, trends, z-scores, "why this number". **No recomputation** — the underlying data is gone | Apple HealthKit HRV/sleep, Garmin via Health Connect, WHOOP via official API |

### 3.1 Why this is a feature, not an apology

- **Honesty as product.** The app states plainly what it can and cannot do with your device. No
  competitor does this.
- **A natural, non-predatory upgrade path.** *"Add a Polar H10 (~$90) to unlock Tier A metrics"* —
  hardware we don't sell, don't profit from, and recommend on the evidence.
- **It sets correct expectations.** A Tier C user gets trends and explanations, not a promise of
  research-grade HRV.

### 3.2 Product rules

1. Every score displays its tier and the source it came from.
2. Never compute a metric the tier cannot support. Show *"needs Tier B or higher"* instead.
3. Retroactive recompute is offered **only** where raw data was retained (Tier A, partially B).
4. If a user adds a higher-tier device later, prior history stays at its original tier — clearly
   marked, never silently "upgraded."

---

## 4. Device support matrix

| Device | Access path | Gate | Tier | Phase |
|---|---|---|---|---|
| **Apple Watch** | HealthKit | **None** (App Review only) | C | **1** |
| **Polar** (H10, Verity, watches) | **Official BLE SDK** — open source | **None. Free.** | **A** | **1** |
| **WHOOP 4.0 / 5.0** | BLE direct ([`README.md`](./README.md)) | Reverse-engineering risk; 5.0 bond exclusivity | **A** | **2** |
| **Fitbit** | **Google Health API** | Google Cloud Console registration | B | 3 |
| **Oura** | Oura API v2 | OAuth; **10-user cap until app approved** | B | 3 |
| **Samsung** | Health Connect | Play Console health declaration | B/C | 3 |
| **Withings** | Withings API | Public dev portal, low friction | C | 3 |
| **Garmin** | 🛑 **Developer program CLOSED to new applicants (2026)** | Form removed, no ETA | C (secondhand) | **Blocked** |
| Suunto, Coros, Wahoo, Ultrahuman | Partner-gated | Commercial application required | varies | Later |
| Zepp/Amazfit, Eight Sleep, RingConn | **No official path** | — | — | Not supported |

**Notes that drive the roadmap:**

- **Apple Watch + Polar are both completely ungated.** Phase 1 costs nothing but engineering and
  proves the entire engine end to end.
- **Polar is disproportionately valuable**: free official open-source SDK, raw **ECG at 130 Hz**,
  RR intervals accurate to **<0.2 ms** vs true ECG. It is simultaneously a Tier A source, the
  gold-standard **validation instrument** for everything else, and a cheap accessory recommendation.
- **Garmin is the largest single population (~45M Connect users) and is currently unreachable.**
  Only routes: read secondhand from Health Connect / HealthKit (Tier C), or pay an aggregator who
  already holds a partnership (~$4,800/yr floor — uneconomic at our ARPU). **Treat as blocked, not
  as roadmap.**
- **Fitbit: build against the Google Health API directly.** The legacy Fitbit Web API is decommissioned
  September 2026, and **OAuth tokens do not transfer** — any user acquired on the old API would have
  to re-consent.
- ⚠️ **WHOOP writes only one HR value per day into HealthKit.** So reading WHOOP secondhand from the
  platform store is Tier C at best. The BLE path is what makes WHOOP a Tier A source.

---

## 5. Goals and non-goals

### 5.1 Goals

| # | Goal | Success looks like |
|---|---|---|
| G1 | Any supported device produces useful daily metrics with no vendor subscription | User connects a device → sees scores within 24h |
| G2 | Data never leaves the device unless explicitly opted in | Zero health-bearing network calls in the free tier, verifiable |
| G3 | Every score is explainable | Every score view decomposes into inputs, baselines, weights, confidence |
| G4 | History is permanent and portable | Full export in open formats at any time |
| G5 | Adding a device is incremental, not a rewrite | New source adapter ships without touching the analytics core |
| G6 | The app is honest about what each device can support | Tier is visible on every score |

### 5.2 Non-goals

| # | Non-goal | Rationale |
|---|---|---|
| N1 | **Merging multiple devices into one score for a single user** | Cross-device metrics are definitionally incomparable. This is the rejected aggregation model. |
| N2 | Replicating any vendor's exact scores | Proprietary; invites copyright and patent exposure. We compute our own from published science. |
| N3 | ECG, AFib, blood pressure, apnea detection | Medical-device regulation |
| N4 | Cloud-first architecture | Contradicts the value proposition |
| N5 | Advertising | Prohibited by Apple for health data; ~10× worse economics than subscription |
| N6 | Out-competing Google on AI scale | Impossible. See [§18](#18-the-ai-position) |
| N7 | Continuous 24/7 background monitoring | Not deliverable on either mobile platform |

**On N1 — the one exception we may allow later:** if a user wears **two devices simultaneously for
14+ nights**, we can fit a **per-user Deming regression** between them and offer a *clearly labeled,
estimated* stitched series for continuity across a device switch. No one has published or shipped
this. It would be validated before shipping, never asserted. Backlog, not launch.

---

## 6. Users and personas

### 6.1 "The Stranded Owner"
Owns a wearable whose subscription lapsed or whose vendor app degraded. Feels the hardware was held
hostage. **Wants:** the device to keep working and the history back. *(WHOOP, Fitbit, Oura.)*

### 6.2 "The Skeptical Optimizer"
Active subscriber who doesn't trust the vendor's recovery score. Has felt great on a 30% recovery.
**Wants:** to see the inputs, adjust the weights, and learn where the algorithm is wrong *for them*.
*(Any device.)*

### 6.3 "The Privacy-Motivated User"
Will not put biometric data in a vendor cloud. Currently uses nothing, or Apple Health alone.
**Wants:** real analytics that never leave the phone. *(Apple Watch, Polar.)*

### 6.4 "The Serious Trainee"
Owns a chest strap for accuracy and a watch for convenience. Understands PPG limitations.
**Wants:** research-grade HRV from RR intervals, and honest error bars. *(Polar — Tier A.)*

### 6.5 Explicitly not a target
Anyone seeking medical diagnosis, arrhythmia screening, or blood-pressure monitoring.

---

## 7. Competitive positioning

| Competitor | Price | Devices | Their weakness |
|---|---|---|---|
| **Athlytic** | $29.99/yr | **Apple Watch only** | Single device; no local-first story; no explainability |
| **Google Health + Gemini Coach** | $9.99/mo (~$120/yr), free w/ AI Pro | Many | **4× our annual price**; cloud-mandatory; black-box scoring |
| **Bevel** | $14.99/mo | Many (aggregation) | Priced above WHOOP's One tier *without hardware*; currently being sued by WHOOP over 4 patents |
| **Vendor apps** (WHOOP, Oura, Fitbit) | $70–360/yr | Own hardware only | Subscription lock-in; data dies on cancellation; opaque scores |
| **Apple Health / Samsung Health** | Free | Own ecosystem | No unified readiness score (Apple); no explainability; no export depth |

### 7.1 The position

> **"Athlytic, but for whatever device you own — at the same price, local-first, and it explains
> itself."**

Strictly broader than Athlytic at identical pricing. Radically cheaper than Google Health, and on a
different axis entirely (local vs cloud). Not competing with vendor apps — complementing them for
users who want their data to outlive the subscription.

### 7.2 What we will not claim

We will not claim better AI than Google (impossible — see [§18](#18-the-ai-position)), better sensor
accuracy than the device itself (we use the same sensors), or medical utility of any kind.

---

## 8. Constraints

### 8.1 Hard technical constraints

| Constraint | Consequence |
|---|---|
| **Web Bluetooth unavailable in every browser on iOS** | Web can never be a capture surface. Native mandatory. |
| **HealthKit has no server-side API** | Ingestion must happen on-device. Backend can only receive what our app sends. |
| **HealthKit read permission is opaque** | `authorizationStatus(for:)` reports write status but **not read**. A denied read is indistinguishable from "no data." Onboarding and empty states must degrade gracefully on ambiguity. |
| **Health Connect history limits** | `READ_HEALTH_DATA_HISTORY` needed beyond 30 days; **revoked on uninstall and the window resets on reinstall**. |
| **WHOOP 5.0 bonds to one device at a time** | Pairing unpairs the official app. Explicit informed consent required. |
| **Background BLE unreliable on both platforms** | Design for periodic foreground sync. Never promise continuous monitoring. |
| **Garmin program closed** | Largest population unreachable directly. |
| **Vendors write summaries, not fidelity, to platform stores** | Tier C for most platform-store sources. Verify empirically (see [§23](#23-open-questions)). |

### 8.2 Per-device calibration is required

Even though personal baselines are device-agnostic, each source needs its own configuration:

| Parameter | Why it varies |
|---|---|
| HRV metric identity (SDNN vs RMSSD) | Apple is SDNN; most others RMSSD. **Label it correctly in the UI; never mix.** |
| Baseline window length | Noisier sources need longer windows to stabilize |
| Outlier thresholds | Physiological range differs by metric and measurement method |
| Minimum history before scoring | Tier C needs more nights than Tier A |
| Sampling cadence assumptions | Apple 1–15 min vs Polar per-beat |

**Requirement:** device profiles are declarative configuration with test fixtures, not scattered
conditionals.

### 8.3 Licensing

MIT/Apache-2.0/BSD/ISC only, enforced in CI. Notably: `hrv-analysis` is GPL (avoid — use NeuroKit2,
MIT); `ryanbr/noop` and `whoop-rs` are PolyForm Noncommercial (**cannot be used commercially**);
`OpenStrap/protocol` is MIT (usable, and the basis of the WHOOP adapter); Polar BLE SDK is
officially licensed and open.

### 8.4 The medical-device line

Unchanged from [`PRD.md` §5.4](./PRD.md). **Never surface** arrhythmia verdicts, ECG interpretation,
blood-pressure estimates, or apnea inference — regardless of technical feasibility, and regardless
of which device provides the data.

**This matters more here**, because Polar exposes genuine ECG at 130 Hz. **We record and use it for
RR-interval extraction only. We never display an ECG waveform or interpret rhythm.**

Banned vocabulary (enforced by CI string lint, in code *and* store metadata): detect, diagnose,
screen, monitor for, abnormal, elevated, arrhythmia, AFib, apnea, hypoxia, any clinical threshold.

### 8.5 Legal gating items

- [ ] **FTO opinion on WHOOP's patent portfolio** — ~87 patents; WHOOP is currently asserting four
      against a competitor over *"analysis of physiological data to provide automated exercise and
      sleep recommendations."* **Patents have no reverse-engineering or interoperability defence,
      and this risk applies to the multi-device version too** — it attaches to computing recovery
      and sleep scores at all, not to how the data was obtained.
- [ ] **Incorporate.** Apple 5.1.1(ix) requires healthcare apps be submitted by a legal entity.
- [ ] **Clear a coined name** in Classes 9/42/44 (US/EU/UK).
- [ ] **Review each vendor's API terms.** Notably **Oura prohibits training or fine-tuning any AI/ML
      model on user data** — check against the roadmap before building anything ML-based.
- [ ] **Clean-room record** for the WHOOP BLE adapter specifically (Phase 2, not Phase 1).

---

## 9. Product principles

1. **Local by default.** Health data leaves the device only on explicit, revocable, per-feature opt-in.
2. **Explain everything.** Any number can be decomposed into inputs and weights.
3. **Never fabricate precision.** Uncalibrated is reported as relative. Insufficient data says so.
   Tier limits are stated, not hidden.
4. **The past is immutable; interpretations are versioned.** Raw data append-only; algorithms
   versioned; recomputation user-initiated and diffed.
5. **One device, one truth.** We never merge devices into a single score. Where a user has two, we
   show two — clearly labeled.
6. **Free tier is genuinely complete.** Paid unlocks convenience and depth, never core function.
7. **No dark patterns.** No ads, no upsell interstitials, no guilt mechanics.
8. **Honest about being wrong.** Where our score disagrees with how the user feels, we surface it.

---

## 10. Feature specification

### 10.1 P0 — Launch (free)

| ID | Feature | Notes |
|---|---|---|
| **F-01** | Device connection flow | Source picker → per-device auth/pairing → capability detection → tier assignment |
| **F-02** | **Source adapter framework** | Pluggable; adding a device is config + adapter, not a core change |
| **F-03** | Apple Watch source (HealthKit) | Tier C. Background delivery via `HKObserverQuery` |
| **F-04** | Polar source (BLE SDK) | **Tier A.** Live RR, raw ECG→RR extraction |
| **F-05** | Live view | Real-time HR/RR where the tier supports it |
| **F-06** | Historical import | Backfill available history from the source |
| **F-07** | Raw/append-only store | Original samples retained; never mutated |
| **F-08** | Nightly aggregates | RHR, HRV (labeled by metric type), respiratory rate where available, sleep duration, SRI |
| **F-09** | Recovery score | 0–100 from personal baselines, **with full input breakdown** |
| **F-10** | Strain / load | TRIMP-based, mapped to the user's own distribution |
| **F-11** | Sleep analysis | Tier-dependent: actigraphy where accel is available, vendor stages where not |
| **F-12** | **"Why this number"** ⭐ | Inputs, baselines, z-scores, weights, contributions, confidence, **and tier** |
| **F-13** | **Outlier-robust baselines** ⭐ | Median/MAD with winsorization; excluded nights visible and overridable |
| **F-14** | **Tier disclosure** ⭐ | Every score shows its source and fidelity tier |
| **F-15** | Export | JSON + CSV + SQLite, including raw where retained. One tap, no throttle |
| **F-16** | Health platform sync | Optional write-back to Apple Health / Health Connect |
| **F-17** | Signal-quality gating | Tier A/B: refuse to score windows that fail quality checks |

### 10.2 P1 — Differentiation

| ID | Feature | Notes |
|---|---|---|
| **F-20** | WHOOP source (BLE) | **Tier A.** Phase 2. See [`README.md`](./README.md) |
| **F-21** | **Felt-state logging** ⭐ | Daily 1–5 + tags, ≤10 seconds |
| **F-22** | **Score reconciliation** ⭐ | Detect systematic disagreement between our score and felt state; offer recalibration |
| **F-23** | **Algorithm versioning** ⭐ | Every score stamped; never silently rewritten |
| **F-24** | **Retroactive recompute** ⭐ | Tier A/B only. Full-history re-run with a visual diff |
| **F-25** | Journal / behaviors | Alcohol, caffeine, travel, supplements, illness |
| **F-26** | ACWR training load | Acute:chronic workload ratio — vendors don't ship this |
| **F-27** | Illness early-warning | NightSignal FSM + **2-of-4 channel confirmation**. Framed as "your baseline shifted," never as diagnosis |
| **F-28** | Fitbit / Oura / Samsung sources | Tier B. Phase 3 |

### 10.3 P2 — Supporter tier

| ID | Feature |
|---|---|
| **F-30** | **Rigorous n-of-1 experiments** ⭐ — randomized, washout-controlled, power analysis, effect-size CIs, multiple-comparison correction |
| **F-31** | Multi-device sync (user's own devices), E2E encrypted |
| **F-32** | Encrypted backup, zero-knowledge |
| **F-33** | Web deep-dive dashboard |
| **F-34** | **Device-switch continuity** ⭐ — opt-in overlap calibration with Deming regression, honest residual SD, clearly labeled as estimated |
| **F-35** | Custom score weights |
| **F-36** | BYOK AI assistant (see [§18](#18-the-ai-position)) |

⭐ = differentiator no competitor currently offers.

---

## 11. User stories

**US-01 — Connect whatever I own**
*As any user, I want to connect my existing wearable, so that I get better analytics without new hardware.*
- AC1: Source picker lists supported devices with their tier and what each unlocks.
- AC2: Unsupported devices are named explicitly with the reason (e.g. "Garmin: the developer program
  is closed to new applications").
- AC3: Each source has a tailored auth flow (HealthKit permission, BLE pairing, OAuth).
- AC4: After connecting, the app states the tier and what is and isn't available.

**US-02 — Understand what my device can and can't do**
*As a Skeptical Optimizer, I want to know my data's limits, so that I don't over-trust the numbers.*
- AC1: A capability screen lists each metric, whether it's supported, at what fidelity, and why.
- AC2: Unsupported metrics show what would unlock them (e.g. "needs per-beat RR — add a Polar H10").
- AC3: No upsell framing; hardware suggestions are evidence-based and we profit from none of them.

**US-03 — See today's recovery**
- AC1: Available within 5 minutes of a sync.
- AC2: Shows score, trend, confidence, **source, and tier**.
- AC3: If baseline history is insufficient, says so instead of showing a number.

**US-04 — Understand why the number is what it is** ⭐
- AC1: Tapping a score shows each input's raw value, personal baseline, z-score, weight, contribution.
- AC2: Shows which input moved most vs yesterday.
- AC3: Links to the published method for each component.
- AC4: **Names the HRV metric explicitly** ("SDNN, as reported by Apple Watch") — never generic "HRV".

**US-05 — Not have one bad night wreck my baseline** ⭐
- AC1: Baselines use median + MAD with winsorization.
- AC2: Excluded outliers are visible and individually overridable.

**US-06 — Log how I actually feel** ⭐
- AC1: One-tap 1–5 + optional tags, ≤10 seconds. Never blocks, never nags.
- AC2: After ≥30 paired observations, reports correlation between our score and felt state.

**US-07 — Be told when the app is systematically wrong about me** ⭐
- AC1: Detects persistent over/under-estimation vs felt state.
- AC2: States it plainly and offers reversible recalibration with a preview.

**US-08 — Keep my scores stable when algorithms change** ⭐
- AC1: Every score carries an algorithm version; updates never silently rewrite history.
- AC2: Recompute is offered, never forced, and only where raw data was retained.

**US-09 — Switch devices without losing my history** ⭐
- AC1: History from the old device is retained and clearly attributed.
- AC2: A visible "re-baselining, N days remaining" state after a switch.
- AC3: Trend deltas that straddle a device change are **refused**, not silently computed.
- AC4: *(Supporter)* If ≥14 nights of overlap exist, offer an estimated stitched view — labeled as
  estimated, with residual uncertainty shown, and the unstitched series retained as source of truth.

**US-10 — Get all my data out**
- AC1: One action exports everything in open formats. No rate limit, no account, no server.

**US-11 — Verify nothing leaves my device**
- AC1: A privacy screen lists every network destination and why.
- AC2: Free tier makes zero health-bearing network calls.
- AC3: Analytics core source is public; builds reproducible.

**US-12 — Run an honest experiment** ⭐ *(supporter)*
- AC1: Guided design: intervention, outcome, block length, washout.
- AC2: App randomizes assignment.
- AC3: Reports effect size with confidence intervals.
- AC4: **Reports insufficient power honestly** and estimates time remaining.

---

## 12. What we compute, by tier

| Metric | Tier A (raw) | Tier B (intraday) | Tier C (summary) |
|---|---|---|---|
| Resting HR | ✅ computed by us | ✅ computed by us | ✅ vendor value |
| HRV | ✅ **our own** RMSSD from artifact-corrected RR | ⚠️ from vendor RR if exposed, else vendor value | ⚠️ vendor value, **metric type labeled** |
| Respiratory rate | ✅ from RSA | ⚠️ if vendor provides | ❌ |
| Sleep/wake | ✅ our actigraphy | ⚠️ vendor or ours | ⚠️ vendor only |
| Sleep stages | ⚠️ ours, labeled as estimates | ⚠️ vendor | ⚠️ vendor |
| Recovery score | ✅ full model | ✅ reduced inputs | ✅ reduced inputs |
| Strain / load | ✅ from continuous HR | ✅ | ⚠️ from summaries |
| ACWR | ✅ | ✅ | ✅ |
| Signal-quality gating | ✅ | ⚠️ partial | ❌ |
| **Retroactive recompute** | ✅ **full** | ⚠️ partial | ❌ **raw data never existed** |

**Rules:**
- HRV is **always labeled with its metric identity and source**. Never a bare "HRV: 45".
- Sleep stage durations are always presented as estimates with accuracy caveats (consumer staging
  runs κ ≈ 0.2–0.65 versus polysomnography, and varies by population).
- We never present a Tier C number with Tier A confidence.

Method and library detail: [`analytics-stack.md`](./analytics-stack.md) and
[`starter/premium_metrics.py`](./starter/premium_metrics.py).

---

## 13. Technical architecture

### 13.1 System overview

```
┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐
│ Apple Watch│  │   Polar    │  │   WHOOP    │  │ Fitbit/Oura│
│ (HealthKit)│  │  (BLE SDK) │  │   (BLE)    │  │   (APIs)   │
└─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘
      │ Tier C        │ Tier A        │ Tier A        │ Tier B
      └───────────────┴───────┬───────┴───────────────┘
                              ▼
              ┌───────────────────────────────┐
              │   SOURCE ADAPTER INTERFACE    │  ← the extension point
              │  capabilities · auth · sync   │
              └───────────────┬───────────────┘
                              ▼
              ┌───────────────────────────────┐
              │  NORMALIZED SAMPLE STORE      │
              │  append-only, source-tagged   │
              └───────────────┬───────────────┘
                              ▼
              ┌───────────────────────────────┐
              │   ANALYTICS CORE (versioned)  │
              │  capability-aware · pure      │
              └───────────────────────────────┘
```

### 13.2 The source adapter contract

Every device implements one interface. This is what makes adding a device incremental.

```
SourceAdapter:
    id: SourceID                      # apple_health | polar_ble | whoop_ble | oura_api | ...
    capabilities: Capabilities        # tier, metrics, cadence, HRV metric identity, raw retention
    authorize() -> AuthResult         # HealthKit permission | BLE pair | OAuth
    sync(since: Date) -> [Sample]     # incremental, resumable
    liveStream() -> AsyncStream<Sample>?   # nil where unsupported
    disconnect()
```

```
Capabilities:
    tier: .A | .B | .C
    hrvMetric: .rmssd | .sdnn | .none      # ← drives UI labeling
    hasRawRR: Bool
    hasAccelerometer: Bool
    hrCadence: Duration                     # 1s (Polar) … 15min (Apple) … 1day (WHOOP-via-HealthKit)
    retainsRawBytes: Bool                   # gates retroactive recompute
    supportsBackfill: Bool
```

**Design rules:**
1. The analytics core **reads capabilities and adapts** — it never branches on source identity.
2. A new device is a new adapter plus a device profile. **No core changes.**
3. Every adapter ships with recorded fixtures for offline testing.
4. Capabilities are asserted in tests, not documented in prose.

### 13.3 Layer responsibilities

| Layer | Responsibility | Testability |
|---|---|---|
| Source adapters | Auth, transport, vendor decode → normalized samples | Recorded fixtures per source |
| Normalization | Units, timestamps, source tagging, dedup | Golden vectors |
| Store | Append-only raw; derived versioned | Integration tests |
| Analytics core | Capability-aware, versioned, **pure** | Property + regression tests |
| Presentation | TCA reducers (iOS) / MVI store (Android) | Exhaustive state tests |

### 13.4 Background execution

Unchanged from [`PRD.md` §10.4](./PRD.md): iOS gets ~10 seconds per wake via State Preservation &
Restoration (and nothing after a force-quit); Android needs a foreground service and is still
subject to Doze and OEM battery killers.

**Design rule: the product must be fully usable with periodic foreground syncs only.** API-based
sources (Tier B/C) are easier here — they backfill on open and don't need a live connection.

---

## 14. iOS architecture — TCA

Stack unchanged from [`PRD.md` §11](./PRD.md): Swift 6 · SwiftUI · TCA 1.x · swift-dependencies ·
GRDB · Swift Testing. What changes is that **BLE is one source among several**.

### 14.1 Sources as dependencies

```swift
@DependencyClient
struct SourceRegistry {
    var available: @Sendable () -> [SourceDescriptor] = { [] }
    var adapter: @Sendable (SourceID) -> any SourceAdapter
}

// Each adapter is its own dependency client, so each is independently fakeable.
@DependencyClient
struct HealthKitSource {
    var requestAuthorization: @Sendable () async throws -> Void
    var capabilities: @Sendable () -> Capabilities = { .appleWatch }
    var sync: @Sendable (_ since: Date) async throws -> [Sample]
    var observe: @Sendable () -> AsyncStream<Sample> = { .finished }
}

@DependencyClient
struct PolarSource {
    var scan: @Sendable () -> AsyncStream<DiscoveredDevice> = { .finished }
    var connect: @Sendable (String) async throws -> Void
    var capabilities: @Sendable () -> Capabilities = { .polarH10 }
    var rrStream: @Sendable () -> AsyncStream<RRInterval> = { .finished }
    var ecgStream: @Sendable () -> AsyncStream<ECGSample> = { .finished }  // RR extraction only
}
```

**Rules:** every `testValue` is unimplemented (tests must override or fail loudly); every
`previewValue` replays a recorded fixture so previews and demos work with no hardware.

### 14.2 Feature tree

```
AppFeature
├── OnboardingFeature
│   ├── SourcePickerFeature          // choose your device
│   ├── SourceAuthFeature            // per-source auth (HealthKit / BLE / OAuth)
│   └── CapabilityDisclosureFeature  // "here's what your device supports"
├── TodayFeature
│   ├── RecoveryCardFeature
│   ├── StrainCardFeature
│   ├── SleepCardFeature
│   └── ScoreBreakdownFeature        // ⭐ "why this number" + tier
├── HistoryFeature
│   ├── TimelineFeature
│   ├── RecomputeFeature             // ⭐ Tier A/B only
│   └── DeviceSwitchFeature          // ⭐ re-baselining state
├── ExperimentsFeature               // ⭐ n-of-1 (supporter)
├── JournalFeature
├── SourcesFeature                   // manage connected device, view capabilities
└── SettingsFeature
    ├── PrivacyFeature
    └── ExportFeature
```

### 14.3 Capability-aware reducers

```swift
@Reducer
struct RecoveryCardFeature {
    @ObservableState
    struct State: Equatable {
        var score: RecoveryScore?
        var capabilities: Capabilities
        var insufficientHistory: Bool = false

        // Drives the UI without branching on source identity.
        var canShowRespiratoryRate: Bool { capabilities.tier != .C }
        var hrvLabel: String {
            switch capabilities.hrvMetric {
            case .rmssd: "HRV (RMSSD)"
            case .sdnn:  "HRV (SDNN)"
            case .none:  "HRV unavailable"
            }
        }
    }
    // ...
}
```

The pattern generalizes: **UI and analytics branch on `capabilities`, never on `sourceID`.** Adding
a device cannot regress existing behavior.

### 14.4 Testing

- **Per-source recorded fixtures** — every adapter ships a captured session.
- **Capability matrix tests** — the analytics core is exercised against every tier combination.
- **Golden vectors** — the WHOOP decoder is validated against OpenStrap's `decode_parity_cases.json`
  (shared with Android).
- **Exhaustive `TestStore`** — every reducer transition asserted.
- **Property tests** — scores always 0–100; a single outlier moves a robust baseline by less than a
  bounded amount.

---

## 15. Android architecture — MVI

Stack and pattern unchanged from [`PRD.md` §12](./PRD.md): Kotlin 2.x · Compose · Coroutines/Flow ·
Hilt · Room · Turbine, with the small TCA-shaped `MviViewModel` base class.

**Multi-source specifics:**

```kotlin
interface SourceAdapter {
    val id: SourceId
    val capabilities: Capabilities
    suspend fun authorize(): AuthResult
    suspend fun sync(since: Instant): List<Sample>
    fun liveStream(): Flow<Sample>?
    suspend fun disconnect()
}

@Singleton
class SourceRegistry @Inject constructor(
    private val healthConnect: HealthConnectSource,
    private val polar: PolarSource,
    private val whoop: WhoopBleSource,
    private val oura: OuraApiSource,
) {
    fun available(): List<SourceDescriptor> = /* device + permission aware */
    fun adapter(id: SourceId): SourceAdapter = when (id) { /* ... */ }
}
```

- **Health Connect** is the primary Android source and covers Samsung, Fitbit, Oura and (secondhand)
  Garmin — a single adapter yielding broad coverage.
- **Polar** uses the official Android BLE SDK.
- **WHOOP** uses the Nordic BLE library with the ported protocol decoder.
- Foreground service (`connectedDevice`) only for live BLE sessions; API sources sync on open.

---

## 16. Data model

Extends [`PRD.md` §14](./PRD.md). **The critical change: source is a first-class dimension on
everything.**

```sql
CREATE TABLE source (
    id              TEXT PRIMARY KEY,       -- 'apple_health' | 'polar_ble' | 'whoop_ble' | ...
    display_name    TEXT NOT NULL,
    tier            TEXT NOT NULL CHECK (tier IN ('A','B','C')),
    hrv_metric      TEXT,                   -- 'rmssd' | 'sdnn' | NULL
    capabilities_json TEXT NOT NULL,
    connected_at    INTEGER NOT NULL,
    disconnected_at INTEGER
);

CREATE TABLE sample (
    id            INTEGER PRIMARY KEY,
    source_id     TEXT    NOT NULL REFERENCES source(id),
    device_model  TEXT,                     -- 'Apple Watch S9' | 'Polar H10' | 'WHOOP 5.0'
    firmware      TEXT,                     -- silent vendor algorithm changes are detectable
    metric        TEXT    NOT NULL,
    ts_start      INTEGER NOT NULL,
    ts_end        INTEGER,                  -- interval samples keep BOTH ends (dedup/overlap)
    value         REAL,
    raw_bytes     BLOB,                     -- Tier A only; enables retroactive recompute
    ingested_at   INTEGER NOT NULL
);
CREATE INDEX idx_sample_lookup ON sample(source_id, metric, ts_start);

CREATE TABLE derived_score (
    id                INTEGER PRIMARY KEY,
    date              TEXT NOT NULL,
    source_id         TEXT NOT NULL REFERENCES source(id),
    score_type        TEXT NOT NULL,
    value             REAL NOT NULL,
    algorithm_version TEXT NOT NULL,
    tier              TEXT NOT NULL,
    inputs_json       TEXT NOT NULL,        -- powers "why this number" — mandatory
    confidence        REAL,
    computed_at       INTEGER NOT NULL,
    UNIQUE(date, source_id, score_type, algorithm_version)
);

CREATE TABLE baseline (
    source_id   TEXT NOT NULL REFERENCES source(id),
    metric      TEXT NOT NULL,
    window_days INTEGER NOT NULL,
    as_of_date  TEXT NOT NULL,
    median      REAL NOT NULL,
    mad         REAL NOT NULL,
    n_included  INTEGER NOT NULL,
    n_excluded  INTEGER NOT NULL,           -- outliers, surfaced and overridable
    PRIMARY KEY (source_id, metric, window_days, as_of_date)
);
```

**Rules:**
1. **Baselines are per-source.** A device change starts a new baseline. Never merged implicitly.
2. **Scores are keyed by source.** Two sources on the same date produce two scores, never an average.
3. `ts_end` is retained so overlapping interval samples from different writers can be deduplicated —
   a documented double-count hazard when both a phone and a watch write to the same platform store.
4. `firmware` is stored so a **silent vendor algorithm change** can be detected as a changepoint.
5. `raw_bytes` populated only where the tier supports it; its presence gates recompute.

---

## 17. Monetization

| Tier | Price | Contents |
|---|---|---|
| **Free** | $0 | All supported sources, all core scores, "why this number", robust baselines, full local history, complete export, platform sync. **No ads. No SDKs. No account.** |
| **Supporter** | **$29/year** | Multi-device sync (own devices), encrypted backup, rigorous n-of-1, web dashboard, device-switch continuity, custom weights, BYOK AI, priority device support |

**Rationale unchanged from [`PRD.md` §15.2](./PRD.md):** $29 sits on the Athlytic anchor, annual-only
is the stronger structure (annual takes ~61% of category subscriptions and churns 48% vs 79%
monthly), and a single low annual price reinforces the "don't pay rent on hardware you own" message.

**Multi-device support improves the economics** — the same $29 now addresses everyone with any
wearable rather than WHOOP owners willing to sideload. Break-even remains **~1,400 annual
supporters** (~$34.5k net), but the funnel above it is far wider.

**No advertising, ever.** Prohibited by Apple Guideline 5.1.3 for health data, unusable under GDPR
Article 9, ~10× worse per install than subscription, and destructive to the privacy positioning.

---

## 18. The AI position

**We will not compete on AI scale, and should never imply we do.** Google's SensorFM foundation
model was trained on **over a trillion minutes of sensor data from ~5 million people** and reportedly
beats baselines on 34 of 35 health tasks. Any "better AI insights" claim loses to that.

**Four AI positions a platform giant structurally cannot take:**

| Position | Why they can't |
|---|---|
| **On-device / private** | Their models require the cloud by architecture |
| **Fully explainable** | Their scores are black boxes; ours decompose into inputs and weights |
| **Bring-your-own-key** | User supplies their own LLM key, so health data never touches *our* servers either |
| **Statistically honest** | Randomized n-of-1 that says *"not enough data yet"* rather than asserting a correlation |

**Constraints:**
- ⚠️ **Oura's API terms prohibit training or fine-tuning any AI/ML model on user data** — verify
  scope with counsel before any ML feature touches Oura-sourced data.
- Apple 5.1.2(i) requires disclosing sharing with third parties **"including with third-party AI"**
  and obtaining explicit permission. BYOK makes this clean: the user brings the destination and
  consents to it directly.
- No AI output may make a medical claim. The banned-vocabulary lint applies to generated text —
  which means **AI output must be constrained and reviewed**, not free-form.

---

## 19. Compliance

Requirements carry over from [`PRD.md` §16](./PRD.md), all CI-enforced: no health data to third
parties; no ad SDKs; license allowlist; banned medical vocabulary in strings *and* store metadata;
arrhythmia/ECG/BP fields never surfaced; network destinations disclosed in-app; explicit per-feature
consent; GDPR export/deletion; clean-room record for the WHOOP adapter.

**Additions for multi-source:**

| ID | Requirement |
|---|---|
| **C-13** | Each source's API terms reviewed and recorded before its adapter ships (Oura's AI clause in particular) |
| **C-14** | Vendor attribution honored per source (e.g. Garmin's "Powered by Garmin" if ever reachable) |
| **C-15** | Health Connect permissions requested **minimally**, with per-permission justification for the Play declaration |
| **C-16** | HealthKit read-opacity handled — never claim a permission was denied when data may simply be absent |
| **C-17** | Tier and source displayed on every score (truth-in-labeling) |

---

## 20. Roadmap

**Phase 0 — De-risk.** FTO opinion on WHOOP's patents (applies to *any* recovery/strain/sleep
scoring, not just the BLE path) · incorporate · clear a name · review each vendor's API terms.
**Exit:** legal green light.

**Phase 1 — Ungated sources (6–10 weeks).** Source adapter framework · **Apple Watch (HealthKit,
Tier C)** · **Polar (BLE SDK, Tier A)** · analytics core · "why this number" · robust baselines.
Both sources are completely ungated, so this ships without waiting on anyone.
**Exit:** 14 days of clean capture on both; scores computed; App Store submission tested early.

**Phase 2 — WHOOP (6–8 weeks).** Port `OpenStrap/protocol` to Swift + Kotlin against the shared
parity fixture. Tier A. Clean-room record maintained.
**Exit:** 14 consecutive days of clean 5.0 capture, validated against a Polar H10.
**Kill criterion:** if 5.0 coverage proves inadequate, ship without it — **the product no longer
depends on WHOOP**.

**Phase 3 — API sources (8–10 weeks).** Google Health (Fitbit) · Oura (apply early for the 10-user
cap) · Samsung and secondhand Garmin via Health Connect · Withings.

**Phase 4 — Differentiate (8–12 weeks).** Felt-state reconciliation · algorithm versioning ·
retroactive recompute · ACWR · illness early-warning.

**Phase 5 — Supporter tier (6–8 weeks).** n-of-1 engine · sync · encrypted backup · web dashboard ·
device-switch continuity · BYOK AI.

---

## 21. Success metrics

| Metric | Target (12 months) |
|---|---|
| Successful connection rate (attempt → first sync) | > 85% *(higher than WHOOP-only; API sources are easier)* |
| Day-7 retention | > 50% |
| Day-30 retention | > 35% |
| Median time from install to first score | < 24h |
| Users on Tier A sources | > 25% |
| % opening "why this number" ≥ 1×/week | > 40% |
| % logging felt state ≥ 3×/week | > 25% |
| Supporter conversion (engaged MAU → paid) | 5–10% |
| **Health-data network calls in free tier** | **0 — non-negotiable** |
| Medical-claim violations in review | **0** |

**Break-even ≈ 1,400 annual supporters** (~$34.5k net at $29/yr less the 15% store cut), implying
~14,000 engaged monthly actives at 10% conversion.

---

## 22. Risks

| Risk | Severity | Mitigation | Kill criterion |
|---|---|---|---|
| **WHOOP patent assertion** | 🛑 Fatal | FTO first. **Applies to this version too** — patents attach to computing recovery/sleep scores, not to data source | Unavoidable infringement found |
| **App Store rejection** | High → **much lower here** | Sanctioned APIs; no vendor mark in metadata; test submission in Phase 1 | Rejected with no remedy |
| **Google Health commoditizes the category** | High | Compete on price (4× cheaper), local-first, and explainability — not on AI scale | Free bundling erodes conversion below 3% |
| **Vendor API changes / deprecation** | High | Adapter isolation; build on Google Health API not legacy Fitbit; monitor deprecations | Multiple sources lost simultaneously |
| **Garmin stays closed** | Medium | Ship without it; secondhand Tier C via Health Connect | — |
| **Per-device calibration burden** | Medium | Declarative device profiles + capability tests | Cost per new source exceeds its reach |
| **Tier C is too thin to be useful** | Medium | Validate in Phase 1 with real Apple Watch data | Apple-only users don't retain |
| **WHOOP 5.0 protocol inadequate** | Low *(was fatal)* | **Product no longer depends on it** | — |
| **Litigation cost attrition** | High | Entity structure, insurance. *bleem! won every ruling and still went bankrupt* | Cost exceeds appetite |

**Note how the risk profile improves:** the two fatal risks in [`PRD.md`](./PRD.md) — App Store 5.2.1
rejection and inadequate 5.0 protocol coverage — both drop to survivable here, because the product
launches on sanctioned APIs and no longer depends on any single vendor.

---

## 23. Open questions

**Phase 1 blockers:**
1. **What does each vendor actually write into HealthKit / Health Connect?** *(The single
   highest-value experiment available.)* Install WHOOP, Oura, Garmin and Withings on a test iPhone
   and Android device and **measure**. This determines whether Tier C is rich enough to be a product
   for anyone but Apple Watch owners. Known: WHOOP writes only **one HR value per day** to HealthKit.
2. **Is Apple Watch (Tier C) sufficient on its own?** Athlytic's existence suggests yes. Validate
   with real users before committing to Phase 3.
3. **Polar RR fidelity in practice** — confirm the SDK delivers per-beat RR reliably in real wear.

**Phase 0 blockers:**
4. Which four patents are asserted in *WHOOP v. Finerpoint* (D. Del. 1:26-cv-00289), and do they
   read on our design?
5. Does Oura's AI-training prohibition extend to on-device personalization, or only model training?
6. Will Apple accept the app under 5.2.1 when it supports many devices and names no vendor in its
   metadata? *(Materially more likely than the WHOOP-only version.)*

**Product decisions:**
7. Ship Phase 1 with Apple Watch only, or wait for Polar to have a Tier A story at launch?
   *(Recommendation: both — Polar is what proves the engine and validates everything else.)*
8. Is device-switch continuity ([§10.3](#103-p2--supporter-tier) F-34) worth the validation burden,
   given no one has published the method?

---

*Reproduces published science, not any vendor's proprietary algorithms. Not a medical device, not
medical advice. Not affiliated with any device manufacturer. Legal statements require counsel
verification against primary sources.*
