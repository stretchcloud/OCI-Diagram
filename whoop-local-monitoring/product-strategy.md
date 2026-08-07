# Product Strategy: A Third-Party WHOOP Client

> **Scope.** You asked for a strategy for a free, ad-supported web + iOS + Android app —
> working name "un-whoop." This document is that strategy, but it does not endorse the plan as
> stated. Research turned up **five independent problems, any one of which is fatal to that
> specific plan**, and one of them (patents) has no legal defence available to you at all.
>
> There is a viable product here. It is **paid, ad-free, differently named, and differently
> differentiated**. That version is laid out from [§4](#4-the-version-that-works) onward.
>
> Not legal advice. Every legal claim here needs counsel to re-verify before you rely on it.

---

## 1. Executive summary

| | Your plan | What research says |
|---|---|---|
| **Name** | "un-whoop" | ❌ Not protected by nominative fair use. One web form kills it. |
| **Monetization** | Free + ads | ❌ Banned by Apple, ~10× worse than subscription, and rejected by this audience. |
| **Platforms** | Web + iOS + Android | ⚠️ Web **cannot** do BLE on iOS, ever. Web must be a dashboard, not a capture surface. |
| **Distribution** | App stores | ⚠️ Apple has a purpose-built rejection for this. **No competitor has ever gotten in.** |
| **Differentiation** | "Something hacky WHOOP can't do" | ⚠️ Your likely first three ideas are already taken by funded competitors. |
| **Legal posture** | Interoperability | 🛑 **WHOOP is currently suing a competitor over four patents on exactly this feature set.** |

**The single most important finding:** on **17 March 2026**, WHOOP sued Finerpoint (Bevel) in
D. Del. (1:26-cv-00289) over **four patents** covering *"analysis of physiological data to provide
automated exercise and sleep recommendations,"* plus copyright, plus **trade dress on the app UI**.
In February 2026 WHOOP also won a **preliminary injunction** against Shenzhen Lexqi on trade dress.

**Patents have no reverse-engineering defence, no interoperability exemption, no fair use, and no
independent-creation defence.** Everything in the earlier research — DMCA §1201(f), *Sega*,
*Connectix*, clean-room practice — is irrelevant to a patent claim. You can build entirely from
published Task Force 1996 formulas and still infringe a claim covering *"computing a recovery
indicator from HRV measured near wake."*

**Verdict: do not write monetized code before getting a freedom-to-operate opinion on WHOOP's
patent portfolio.** That is the gating item. Everything else in this document is downstream of it.

---

## 2. The five problems with the plan as stated

### 2.1 🛑 Patents — no defence exists

WHOOP raised **$575M** (Series G, $10.1B valuation) and is behaving like a company preparing for an
IPO: demonstrating a defensible moat through litigation. It has, in the last 18 months:

- sent a cease-and-desist to Bevel (Nov 2024),
- won a **preliminary injunction** against Lexqi on trade dress (Feb 2026),
- filed a **four-patent + copyright + trade dress** suit against Bevel (Mar 2026).

The Bevel complaint alleges copying of the *"look and feel … including the structure, organization
and presentation of core metrics such as recovery, strain and sleep."* Identified patents include
**US 12,318,226** ("Determining Sleep Need from Physiological Measurements," issued 2025-06-03) and
**US 9,750,415 B2** (sleep-stage detection with HRV near waking to generate an individualized
recovery indicator).

That second patent describes, almost exactly, the thing this app would compute.

**Mitigation:** an FTO opinion before coding; design around the claims; consider omitting automated
*recommendations* (the patents emphasize recommendation generation, not measurement); budget for
defence or don't monetize. **This is a real cost, not a formality.**

### 2.2 🛑 "un-whoop" is not defensible

Nominative fair use protects using a mark **to refer to someone else's product** ("works with
WHOOP"). It does **not** protect using the mark as **your own brand name** — that fails the
*New Kids / Toyota v. Tabari* test at prongs 2 and 3 simultaneously. The federal dilution
fair-use carve-out (15 U.S.C. §1125(c)(3)(A)) expressly excludes use *"as a designation of source
for the person's own goods or services."*

WHOOP holds **~52 USPTO filings**, including WHOOP Reg. **4805176** (Classes 10 + 42, covering
SaaS analytics of physiological metrics) and Reg. **7757625** (Class 44, expressly reciting a
*downloadable mobile application*), plus a **3-D trade dress registration** on the clasp geometry.

And enforcement doesn't require a lawsuit. Apple's IP dispute form and Google Play's trademark form
both accept a registration number and act on complaint — **2–3 weeks on Play, faster on Apple**.
Consequences run to **developer account termination**.

**Effort for WHOOP to kill "un-whoop": one web form, about fifteen minutes.**

Compare how the incumbents handle it. NOOP's own `DISCLAIMER.md` states its mark usage is
nominative *"and never as the name of this project's own product or brand."* Gadgetbridge contains
no vendor mark at all. That clause is precisely the one "un-whoop" violates.

### 2.3 🛑 Ads are prohibited, unprofitable, and off-brand — all three

**Prohibited.** Apple bans this three separate ways, and **more broadly than HealthKit**:

> **5.1.3(i)** — "Apps may not use or disclose to third parties **data gathered in the health,
> fitness, and medical research context** — including from the Clinical Health Records API,
> HealthKit API, Motion and Fitness … — **for advertising, marketing, or other use-based data
> mining purposes**."

Note *"including from"* — the named APIs are **examples**, not the scope. Biometric data read off a
WHOOP strap over BLE is data gathered in the health and fitness context. Guidelines 5.1.2(vi) and
2.5.18 add independent prohibitions. Google Play bans health data for ads including
interest-based advertising. Under GDPR, health data is Article 9 special category — and consent
bundled into a free ad-supported app is not "freely given" (an Italian DPA fined a health app
**€1.5M** for exactly that bundling).

**Unprofitable.** Modeled ARPDAU for a glance-type app is **$1.50–$9 per user per year**. One
salary needs **6,600–41,000 DAU**. The entire visible niche is two GitHub projects at 544★ and
418★. Meanwhile Health & Fitness has the **highest install LTV of any category at $1.20** for
subscriptions versus ~$0.11 modeled for ads — roughly **10× better**. That's why ~80% of the
category's revenue is subscriptions.

**Off-brand, and legally radioactive.** The audience research is unambiguous: *"the most frequently
stated risk was not misuse of personal health data but the fear of receiving more personalized
advertisements."* **Ads are the privacy fear.** Samsung flooded Samsung Health with ads, users
revolted, and Samsung removed them in 2021. F-Droid — this genre's natural home and Gadgetbridge's
entire distribution channel — classifies ads as an **anti-feature**.

And the enforcement record is brutal: FTC fined GoodRx **$1.5M** with a *permanent ban* on sharing
health data for advertising; BetterHelp **$7.8M**. In *Frasco v. Flo Health* (Aug 2025) a jury found
**Meta liable under CIPA** for receiving health data via an embedded SDK — **$5,000 per violation**;
Flo settled for $8M, Google paid $48M. Washington's My Health My Data Act covers heart rate,
treats ad-SDK transfer as a likely **"sale,"** and carries a **private right of action**.

Monetizing also flips a criminal switch: **17 U.S.C. §1204** penalizes willful §1201 violation
*"for purposes of commercial advantage or private financial gain."* Ad revenue is private financial
gain.

### 2.4 🛑 The app stores are a closed door — and that's what makes ads impossible

This is the structural contradiction that ends the ad model on its own.

Apple's actual, verified rejection text under Guideline **5.2.1**:

> "Your app includes content or features from 'XXX', **or is marketed to control external hardware
> from 'XXX', without the necessary authorization** … attach documentary evidence … demonstrating
> authorization … **or** remove the third-party content from your app **and its metadata**."

Your options are (a) get written authorization from WHOOP — which will not be granted to a
competitor, or (b) strip "WHOOP" from your name, subtitle, description, keywords and screenshots —
which destroys the discoverability that an ad-supported free app depends on entirely.

**Neither existing project is in a store.** `ryanbr/noop` ships as sideloaded APK / AltStore IPA /
non-notarized macOS app. `OpenStrap/edge` is TestFlight-only (10k tester cap, 90-day expiry). That
is a tacit admission the store route is closed for this product class.

**Ad revenue requires scale → scale requires the stores → the stores are the chokepoint.**

Precedent for how fast this goes: **The OG App** (a third-party Instagram client) hit ~10,000
downloads and was removed by Apple within days, then by Google a week later, with the founders'
personal accounts disabled. **Beeper Mini** was blocked by Apple at the protocol level repeatedly,
and a bipartisan DOJ referral didn't save it.

### 2.5 ⚠️ Your license base can't be used commercially

Verified by reading the actual license files:

| Project | License | Commercial use? |
|---|---|---|
| `ryanbr/noop`, `tanarchytan/noop`, `tanarchytan/whoop-rs` | **PolyForm Noncommercial 1.0.0** | ❌ **No** |
| `b-nnett/goose`, `johnmiddleton12/my-whoop` | **No license file** = all rights reserved | ❌ **No — worse** |
| `Aura-healthcare/hrv-analysis` | **GPL-3.0** | ❌ No (also App Store incompatible) |
| **`OpenStrap/edge`, `OpenStrap/protocol`, `Sophonbot0/whoop-vault`** | **MIT** | ✅ **Yes** |

PolyForm NC grants rights only *"for any permitted purpose"* and then enumerates them exhaustively
— personal use *"without any anticipated commercial application."* An ad-supported app falls
**outside the grant entirely**, which is not a license breach but **bare copyright infringement**.
It's stricter than CC-BY-NC, which at least hedges with "primarily."

**Two clean paths:** build on the MIT projects, or **negotiate a commercial dual-license** from the
NOOP copyright holder. PolyForm exists precisely to enable that second option, and it's the
cheapest way to retire a critical risk.

---

## 3. What *not* to differentiate on

Three of the most obvious "hacky things WHOOP can't do" are already taken:

| Idea | Status |
|---|---|
| **Multi-device fusion** (WHOOP + Oura + Garmin in one app) | ❌ **Taken.** Vora (500+ integrations, free tier), **Bevel ($10M Series A)**, Kygo, ONVY, plus infra from Terra/Spike/Open Wearables. No longer a differentiator. |
| **Algorithm transparency** | ❌ **Taken.** Open Wearables ships MIT-licensed open scoring, marketed as *"open algorithms you can actually read."* Fitbit shipped a "transparent Sleep Score" in March 2026. |
| **N-of-1 experiments** | ⚠️ **WHOOP already does this.** Journal + Behavior Insights, 300+ behaviors, reports associations after ≥5 yes / ≥5 no in 90 days. |
| **Data export** | ❌ Eroding fast under GDPR Art. 20 pressure. WHOOP already shipped export. |

Note also: **Terra's API costs ~$10/user/year** against ~$4/user/year of ad revenue. Aggregation via
a paid API is fatal to a free product. Only self-hosted (Open Wearables, $0/user) works.

---

## 4. The version that works

### 4.1 Positioning

> **A local-first analytics client for wearables you already own — including ones whose
> subscription has lapsed. Your data stays on your device. Your history follows you across
> devices, vendors, and years.**

Note what this positioning does *not* say: it never mentions cancelling a subscription. That phrasing
would manufacture the inducement element of a **tortious interference** claim. NOOP deliberately
says the opposite — *"users are encouraged to maintain an active relationship with the official
product."* Copy that discipline.

### 4.2 The four genuinely unclaimed differentiators

**1. Retroactive recomputation with visible algorithm diffs.** ⭐ *The strongest position.*

Keep the raw stream forever, version every algorithm, and let a user re-run **their entire history**
under a new version — showing the diff. Vendors structurally can't: retaining full-resolution
PPG + accelerometer has no revenue justification at their scale, silently rewriting historical
scores destroys trust, and it invites direct version-vs-version comparison that a black box cannot
survive. Open Wearables versions scores openly but operates on *derived* API data. **Only a
BLE-direct client owns the raw signal.**

This also answers a real, documented grievance: users whose HRV "dropped almost 50%" going 4.0 → 5.0
with no way to reconcile the series.

**2. Cross-vendor longitudinal continuity.**

Switch from WHOOP to Oura today and your history resets to zero. **No vendor can ever fix this** —
the switcher is a customer they lost. A third party owns a continuous physiological timeline across
hardware generations, brands, and subscription lapses. For a quantified-self audience, multi-year
continuity is both the highest-value asset and the strongest retention mechanic available.

**3. Statistically honest n-of-1.**

WHOOP does naive correlation on observational data. Nobody — including WHOOP — does **randomization,
washout periods, blocking, effect-size confidence intervals, multiple-comparison correction, or
power analysis**. "Does magnesium actually change my HRV?" answered with a properly designed
randomized trial, with an honest "we don't have the power to say yet," is a genuinely new product.
**The gap is rigor, not the feature.**

**4. Fixing the two most-complained-about algorithm failures.**

- **Outlier-robust baselines.** One anomalous HRV spike currently poisons WHOOP recovery for weeks.
  Winsorized/median-MAD baselines fix it. Pure math.
- **Score-vs-felt-state reconciliation.** Log how you actually feel; surface where the algorithm is
  systematically wrong *for you*; recalibrate. Turns *"my recovery says 30% but I feel great"* — the
  single most common complaint — into your headline feature. **Nothing on the market does this.**

**Two adjacent options worth considering:**
- **Strength load that isn't cardio-only.** The biggest technical thread on WHOOP's forum (88+
  replies) is HR accuracy during lifting — because strain is cardiovascular-only. Volume/tonnage
  load (user-entered or Hevy-imported) addresses it.
- **Clinically-adjacent niches.** [Visible](https://www.makevisible.com/) proved this with ME/CFS
  and Long Covid pacing — *"activity tracking for illness, not fitness."* Chronically ill users have
  far higher willingness-to-pay and near-zero alternatives. ⚠️ But this collides hardest with
  medical-device regulation — see [§7](#7-the-medical-device-line).

### 4.3 Naming

Requirements: coined or arbitrary, **zero WHOOP morphemes**, clearable in Classes 9/42/44 across
US/EU/UK. Follow the Gadgetbridge pattern — a name about *what it does*, not *what it replaces*.

Then use the mark **only** referentially, in plain text, never stylized, never in WHOOP's colors or
typeface, never with the "W" logo:

> Works with WHOOP® 4.0 and 5.0. Independent and unofficial — not affiliated with, endorsed by, or
> connected to WHOOP, Inc. WHOOP is a trademark of WHOOP, Inc.

Domain: `yourbrand.app`, never `whoopalternative.com`.

---

## 5. Platform strategy

### 5.1 The hard constraint: Web Bluetooth does not work on iOS

| Browser | Web Bluetooth |
|---|---|
| Chrome / Edge / Opera / Samsung Internet (desktop + Android) | ✅ |
| **Safari — macOS, iOS, iPadOS, all versions** | ❌ **Never. No plans.** |
| **Chrome / Edge / Firefox on iOS** | ❌ Apple's WebKit mandate means they inherit the gap |
| Firefox (all platforms) | ❌ Refused since 2015 on privacy grounds |

There is also **no background execution at all** — close the tab and the connection dies. The
workarounds (Bluefy, a Safari extension) require installing separate software and are not a
consumer funnel.

**Conclusion: the web app cannot be the capture surface. Native is mandatory for iOS.**

### 5.2 Recommended architecture

```
┌─────────────────────────────────────────────────────────┐
│  ANALYTICS CORE  — platform-free, versioned, tested     │
│  HRV · sleep · recovery · strain · n-of-1 statistics    │
│  ← ALL differentiation lives here. Publish it openly.   │
└─────────────────────────────────────────────────────────┘
        ↓                    ↓                    ↓
┌──────────────┐   ┌──────────────┐   ┌────────────────────┐
│  iOS (BLE)   │   │ Android(BLE) │   │  WEB (no BLE)      │
│  capture+UI  │   │  capture+UI  │   │  dashboard, deep   │
│              │   │              │   │  analysis, import, │
│              │   │              │   │  export, sharing   │
└──────────────┘   └──────────────┘   └────────────────────┘
```

**Mobile: Flutter + `flutter_blue_plus`, forked from MIT-licensed `OpenStrap/edge`.** The reasoning
isn't framework preference — it's that OpenStrap is *already* Flutter with working iOS + Android
BLE that computes HR, HRV, sleep staging, recovery, strain, breathing coherence and HR zones, with
Apple Health / Health Connect export, under **MIT**. Forking code that already solves your hardest
problem beats greenfield by a wide margin.

*Alternative:* React Native + `react-native-ble-plx` (3.4k★, Apache-2.0) has the best-documented iOS
state-restoration story — but you rebuild the WHOOP protocol layer. **Do not use Capacitor**
(weakest background story, and its "web" leg is dead on iOS anyway).

**Web: companion dashboard, not capture.** Deep analysis, history exploration, n-of-1 experiment
design, import/export, sharing. Web Bluetooth on desktop Chrome as a bonus path only.

### 5.3 Background BLE — design around it, you cannot fix it

**iOS:** requires `UIBackgroundModes: bluetooth-central`. Background scanning is degraded (explicit
service UUIDs only, forced duplicate filtering, slowed intervals). State Preservation & Restoration
relaunches on events **but not** if the user force-quit the app or toggled Bluetooth. Restored apps
get roughly **10 seconds**. Apple: it *"can't run forever."*

**Android:** `BLUETOOTH_SCAN`/`CONNECT` on 12+; **scanning fails outright if OS location services are
off**; Doze defers work even with WorkManager; Android 13 mandates foreground-service types; 15
tightened launch restrictions. **OEM battery killers override everything** — Samsung's "Sleeping
apps" auto-adds apps after inactivity regardless of foreground service status.

> **Design rule: never ship a feature that requires uninterrupted 24/7 background BLE. It is not
> deliverable on either platform.** Degrade gracefully to periodic foreground syncs, and build an
> onboarding flow that walks Android users through disabling battery optimization.

---

## 6. Monetization

**Drop ads. Adopt the Intervals.icu model** — the only model in this space that demonstrably
supports a developer:

> 160,000+ active athletes. Free for everyone, nothing withheld. Optional **$4/mo supporter tier**.
> No ads, no VC. **The creator went full-time on it in 2024.**

### Recommended ladder

| Tier | Price | Contents |
|---|---|---|
| **Free core** | $0 | Everything essential: BLE capture, all scores, full local history, export. No ads, no SDKs, no account. This is the distribution engine *and* the credibility. |
| **Supporter** | **$20–30/yr** | Multi-device sync, opt-in encrypted backup, advanced n-of-1 statistics, priority device support, retroactive recompute across devices. |
| **Donations** | — | Liberapay / GitHub Sponsors / Open Collective. A floor, not a plan. |

**Price ceiling is set by Athlytic at $29.99/yr** — the direct "turn your watch into a WHOOP" comp.
You cannot charge more than that for scores computed from hardware the user already owns.

**Why this beats ads even at identical revenue:** 5,000 engaged users at $25/yr with a 10% take rate
is ~$12,500/yr — comparable to the *optimistic* ad case at the same scale — with **no ad SDK, no
privacy contradiction, no F-Droid anti-feature label, no ATT prompt, no FTC/HBNR exposure, no CIPA
class-action surface, and no Apple 5.1.3 violation.**

**The psychographic point that settles it:** people leaving WHOOP are not people who won't pay. They
own $200–350 hardware and pay for Stryd ($129/yr) and TrainingPeaks ($135/yr). They object to
**rent on a device they already bought.** An optional $25/yr is aligned with that. Ads are not.

*If ads are truly non-negotiable, the only defensible variant is Runalyze's: ads on the free **web**
tier only, where "no ads" is the thing you sell — and never in the mobile apps that touch health data.*

---

## 7. The medical-device line

**Never surface these, regardless of technical feasibility:** AFib or arrhythmia verdicts, ECG
interpretation, blood-pressure estimates, sleep-apnea inference.

The strap *does* emit a rhythm classifier — NOOP's protocol docs show
`heartKeyArrhythmiaCheckResult` with values including `afibDetected`, plus ECG packet layouts. NOOP
deliberately decodes it and **refuses to display it**: *"the on-strap rhythm classifier's verdict is
decoded as a byte and is never presented as a finding — NOOP is not a medical device."* Follow that.

The WHOOP FDA warning letter (14 Jul 2025, closed 17 Jun 2026) is the lesson: FDA held that Blood
Pressure Insights was a device because BP estimates are *"inherently associated with the diagnosis
of hypo- and hypertension"* — and that **even if** intended for wellness it would still fail the
low-risk test, because *"FDA considers products not to be low risk if FDA actively regulates
products of the same type."*

WHOOP survived that because it's a $575M-funded company that could negotiate for eleven months and
ship a labeling change. **A third-party app gets a warning letter — which WHOOP then forwards to
Apple and Google.** Regulatory risk and platform risk are the same risk.

**Claim vocabulary — freeze this before design:**

| ✅ Safe | 🛑 Banned |
|---|---|
| strain, effort, recovery, readiness, sleep quality | detect, diagnose, screen, monitor for |
| "trending higher than your baseline" | "abnormal", "elevated", "high blood pressure" |
| "consider resting today" | arrhythmia, AFib, apnea, hypoxia |
| relative, personal, unitless | any numeric clinical threshold |

Enforce it in code review, copy review, **and store metadata review**. FDA reads all of it, and
intended use is inferred from everything — feature names, UI strings, screenshots, marketing, even
founder posts.

---

## 8. Pre-build checklist

**Gating — do these before writing monetized code:**

- [ ] 🛑 **FTO opinion on WHOOP's patent portfolio.** Pull the Bevel complaint (D. Del.
      1:26-cv-00289) to see the four asserted patents. **This is the one risk with no defence.**
- [ ] 🛑 **Read WHOOP's actual Terms of Use and device EULA.** Under *Davidson v. Jung* a EULA can
      waive §1201(f) interoperability rights. Nobody in this research could read them.
- [ ] 🛑 **Clear a coined name** in Classes 9/42/44 (US/EU/UK).
- [ ] 🛑 **Resolve the license base**: build on MIT projects, or negotiate a commercial dual-license
      from the NOOP copyright holder.
- [ ] ⚠️ **Pre-submission inquiry to Apple App Review** on the 5.2.1 external-hardware question.
      Do this before building — it determines whether *any* monetization is possible.
- [ ] ⚠️ **Verify 5.0 feasibility.** Both OpenStrap and NOOP describe 5.0/MG support as
      **experimental with incomplete overnight inputs**. You own a 5.0. *This may block the product
      before any legal issue does.*

**Engineering hygiene:**

- [ ] **Documented clean room.** Two roles: a facts team that touches WHOOP artifacts and produces a
      wire-format spec; an implementation team that never touches WHOOP artifacts and codes only
      from the spec. Dated captures, receipts for straps purchased retail. Ideally the facts team
      never accepted WHOOP's ToU.
- [ ] **No verbatim ports.** Re-derive CRC-16/MODBUS from the published specification; re-derive any
      handshake constant from your own capture. NOOP's docs say `crc16Modbus` was *"ported verbatim"*
      from an unlicensed repo — those two words are discovery poison for a commercial defendant.
- [ ] **License policy in CI.** Ban GPL/AGPL/LGPL. Prefer MIT/Apache-2.0. NeuroKit2 over
      `hrv-analysis`.
- [ ] **Visually distinct UI** — different information architecture, palette, typography, and metric
      names. WHOOP is *currently litigating app look-and-feel* and just won a trade dress injunction.
- [ ] **Health data never crosses a process boundary** to any third-party SDK — ads, analytics,
      attribution, or crash reporting.
- [ ] **Consider an EU/UK entity** for the reverse-engineering work: Software Directive Art. 6
      permits decompilation for interoperability and **Art. 8 makes contrary contract terms null and
      void** — materially stronger than the US position.

**Counsel needed in four disciplines:** IP litigation with patent FTO · US privacy (FTC/HBNR/state) ·
EU/UK data protection · FDA/MDR regulatory. Plus tech E&O, media/IP, and cyber insurance.

---

## 9. Roadmap

**Phase 0 — De-risk (before code).** The gating checklist above. If the FTO opinion comes back bad,
**stop** — or build the non-commercial version instead.

**Phase 1 — Prove the hardware.** Fork `OpenStrap/edge` (MIT). Get reliable 5.0 capture on your own
band. Verify the two open questions from the earlier guide: R-R timestamp resolution, and whether
the stream is pre-filtered. Buy a **Polar H10 (~$90)** for ECG-derived ground truth.

**Phase 2 — Build the core.** Platform-free analytics library: robust baselines, versioned
algorithms, retroactive recompute. Publish it openly — it's the artifact people cite, fork, and
sponsor.

**Phase 3 — Ship free mobile.** iOS + Android, no ads, no SDKs, no account. Test App Store review
early with a minimal build. Have the sideload/TestFlight path ready as a fallback, and know that it
caps you at hobby scale.

**Phase 4 — Differentiate.** Score-vs-felt-state reconciliation, then rigorous n-of-1, then
cross-vendor continuity. These are the reasons to choose you.

**Phase 5 — Monetize.** Supporter tier at $20–30/yr once the free product is genuinely good. Web
dashboard as a supporter-facing surface.

**Kill criteria — decide these now, honestly:**
- FTO opinion finds unavoidable infringement → stop or redesign.
- Apple rejects under 5.2.1 with no remedy → the commercial version is dead; ship non-commercial.
- 5.0 protocol coverage proves inadequate → no product.
- A firmware update breaks BLE access and can't be recovered → the whole category is at risk.

---

## 10. The honest summary

**There is a legitimate, defensible non-commercial interoperability project here.** NOOP and
OpenStrap demonstrate it, carefully and in public.

**Monetizing changes four things structurally, not incrementally:**

1. It **voids the license** on most existing WHOOP reverse-engineering code (PolyForm NC or
   unlicensed).
2. It converts you from a hobbyist into **a competitor** — at the exact moment WHOOP has raised
   $575M, won a trade dress injunction, and filed a four-patent suit against another app for
   computing recovery, strain and sleep.
3. It **forces you through the app stores**, where Guideline 5.2.1 has a purpose-built rejection for
   your exact case, and where no project in this niche has ever been admitted.
4. It makes **the ad model self-defeating**: the only monetization that scales at low ARPU requires
   health-adjacent advertising, which Apple bans three ways, Google bans, GDPR makes
   consent-impossible, the FTC has twice permanently enjoined, and a jury has found the ad recipient
   liable for.

**My recommendation:** build it **paid, ad-free, on-device, under a coined name, on MIT code, with
an FTO opinion in hand, with no arrhythmia/ECG/BP features** — and pressure-test App Store review
before writing significant code.

And a note on cost that has nothing to do with who's right: **bleem! won every ruling against Sony
and still went bankrupt.** Sony reportedly spent over $10M; bleem! was drained by legal fees and
folded in 2001. Against a company that just raised $575M, *"I would win at trial"* is not a business
plan.

If any of those conditions is unacceptable, the honest answer is that **the non-commercial version
is the version that works** — and it's a genuinely good project.

---

*Compiled from research into WHOOP user communities, the competitive and monetization landscape,
platform policy, and the legal environment. Not legal advice — every legal claim needs counsel to
verify against primary sources. Not affiliated with WHOOP.*
