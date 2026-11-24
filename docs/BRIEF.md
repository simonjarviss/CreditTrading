# The standing brief

> **Citations written `pre-clean-slate:<path>`** name files deleted in the
> 2026-09-28 clean slate. Read one with `git show pre-clean-slate:<path>`;
> `docs/HISTORY.md` explains. They are provenance, not current state.

**Every prompt in this directory opens by reading this file.** It holds what
they all share — the theory of the edge, the mechanisms, how these instruments
actually trade, and the harness rules — so that no prompt repeats it and every
prompt can cite it by section.

> **Trimmed 2026-09-14.** §4 keeps the scoreboard's goals and drops its "live
> today" figures (`python3 -m ops.orient` and the named commands measure them).
> §6, §7 and §8 are stubs, numbered so citations still land: the house rules are
> `CLAUDE.md`, the standing decisions `docs/SYSTEM.md` §5. (The work-order queue
> was deleted 2026-09-28 and this file moved here from `docs/prompts/00_BRIEF.md`.) The full earlier text is the snapshot at git tag `pre-clean-slate`
> `pre-clean-slate:_archive/docs/prompts/00_BRIEF_2026-09-14.md`. Figures left in §1–§3 and §5
> are dated observations, not inputs (H14).

Written 2026-09-07 from a full read of the repo and the live dashboard;
Section 3 added 2026-09-09 from sourced market research; consolidated from 51
prompts to 14 on 2026-09-09.

---

## 1. What "finding alpha" means for this book

The book earns its return through one relation, Grinold's fundamental law, in
the form Clarke, de Silva & Thorley (2002, FAJ) generalised:

    IR ≈ IC · TC · √BR

- **IC**, the information coefficient: how well the signal ranks tomorrow's
  returns. Ours measured **−0.074 (t −11.6)** at the traded 2-day / T+1 horizon
  over 27 years, in every sub-period (2026-09-05 [S],
  `pre-clean-slate:results/cef/ALPHA_AUDIT_2026-09-05.md`; re-measure with
  `python3 scripts/cef/plan_diagnostics.py`). The repo has
  measured many times that sharpening it is the least productive place to work
  (price reversal adds +0.1%; the Kalman lost to a shorter window; per-name
  kappa lost to pooled). **But see W4: the IC has never been tested against the
  three mechanical effects that produce exactly this signature, and every
  number below is conditional on that battery.**
  > **W4 ran on 2026-10-11** (`results/cef/W4_ARTIFACTS_2026-10-11.md`, fit
  > period only, 0 trials). Bounce, stale NAV, ex-dates and crises each explain
  > little or none of the IC. But −0.074 is the **17-name, no-ADV-filter**
  > figure (it reproduces as −0.078 on 2005–22). The **deployed** 13-name
  > signal, as the sleeve filters it, measures about half that and is not
  > significant in any single era. Quote that note's baseline, not this line,
  > for anything about the book that trades.
- **BR**, breadth: the number of *independent* bets per year. We hold 17 names
  and pretend that is 17 bets. It is not. The book's effective breadth is a
  small fraction of its name count — 1.17 on the live weights and 2.24
  historically when this was written (2026-09-07 [S]) — because most of its
  variance is one factor: municipal CEFs against taxable ones. Measure it on
  today's weights with the dashboard's `/api/factors`. Qian & Hua
  (2004) is the reference for why nominal position count is never breadth when
  forecasts are cross-sectionally correlated. **This is the biggest hole in the
  strategy.**
- **TC**, the transfer coefficient: how much of the ideal book we actually hold
  after costs, borrow, availability, rounding and missed sessions. When this was
  written the band kept about **37%** of its gross Sharpe once borrow was
  charged (2026-09-07 [S]; re-measure with `python3 scripts/cef/band_frontier.py`),
  against the 0.3–0.8 range Clarke et al. report as typical for constrained
  portfolios. **This is the capture problem
  and the highest-value work per hour.**

So "finding alpha" here has three distinct meanings, and every prompt says which
one it is doing:

1. **Raise BR** without lowering IC — make seventeen names into more than one
   bet (W10).
2. **Raise TC** — trade less, trade cheaper, short what can be borrowed, size to
   the right volatility, never send an order the strategy did not ask for, and
   measure execution fast enough to act on it (W5, W7, W8, W11, W12).
3. **Add a genuinely new IC source** only where a *mechanism* says one should
   exist and the current signal is provably blind (W10, W13; W14 closed 2026-09-13).

---

## 2. Where alpha comes from in closed-end funds

Before any test, name who is on the other side and why they stay there. The
status column is as of 2026-09-09 [S]; the work orders it names were deleted
2026-09-28 (`pre-clean-slate:_archive/docs/prompts/`, archived) and `docs/RESEARCH_STATE.md` says
what is killed, watched or closed.

| # | mechanism | who loses, and why they keep doing it | horizon | status |
|---|---|---|---|---|
| M1 | **Discount mean reversion.** Retail sentiment moves price; NAV is the anchor; nothing arbitrages the gap because the share count is fixed and there are no APs (Lee, Shleifer & Thaler 1991; Pontiff 1996) | Retail holders who buy yield and sell losses, at whatever price | days to weeks | **Live.** IC −0.074, pending W4 |
| M2 | **Stale NAV.** Munis and loans are matrix-priced; the published NAV lags true value (Getmansky, Lo & Makarov 2004; Choi, Kronlund & Oh 2022) | Nobody — it is measurement error we can remove, or an artefact we are mistaking for alpha | days | NAV autocorrelation 0.388, unmodelled → W4 §C, W13 |
| M3 | **Seasonal retail flow.** Tax-loss selling into year-end, reversal after (Starks, Yong & Zheng 2006, in *municipal* CEFs specifically) | Tax-motivated retail — not stupid; the tax value exceeds the price concession | dated, weeks | Pooled January measured (+7.7bp/day). Group split untested → W10 §E |
| M4 | **Group-level fair value.** A muni fund's fair discount moves with the muni/Treasury ratio and its SIFMA-linked leverage cost; a HY fund's with spreads; a PIMCO fund's with its repo cost and its own premium regime | The z-score reads a fair-value shift as a dislocation and trades the wrong way for months | weeks to months | Untested as a *conditional* level → W10 §D |
| M5 | **The group spread itself.** The muni-vs-taxable discount spread reverts; the book is short it at whatever level the demeaning produced | The same retail base, at sector level | weeks | Taken by accident at 92.5% of risk. Never sized → W10 §B, §C |
| M6 | **Corporate events.** Tenders, rights offerings, mergers, open-endings, activist 13Ds move a discount to a known level on a known date | Boards that resist activists; holders who sell before the tender | dated | Not staged. Calendar only → W9 Stage 3. **Regime change: see §3** |
| M7 | **Distribution policy.** Cuts re-rate a fund permanently; the rolling mean takes a year to notice | Yield-screening retail | months | Tested twice, failed at a 2-day hold. **Do not rebuild** |
| M8 | **Fund health / price level.** Low-priced CEFs have eroded capital through return-of-capital; higher-priced funds revert better AND cost fewer ticks | Yield chasers in eroded funds | — | Measured +0.16 net in July, "Adopt", **never deployed** → W11 §D |
| M9 | **Volatility state.** Discounts widen together in credit sell-offs and revert fastest afterwards; the options market prices tomorrow's volatility today. Two uses: a *hedge* (long gamma pays exactly then, but costs the variance risk premium every other day) and *information* (a band width and vol target that know a shock is on) | Nobody, for the hedge — it is insurance, priced rich. For the information use: the book's own lagging estimates | days to weeks | **Closed 2026-09-13**: the book is not short vol in a way a hedge could use, and no declared conditioner times credit gamma (`docs/RESEARCH_STATE.md` CLOSED: W14-A, G6) |

---

## 3. How these instruments actually trade

Sourced facts about the products themselves. Every claim here is either a
primary source or is flagged. Prompts cite this section rather than restating
it.

### The wrapper

A traditional CEF issues a fixed share count at IPO and **never creates or
redeems**. There is no authorized-participant mechanism, which is why the
discount persists and why nothing closes it mechanically. It is also why the
**lendable pool cannot grow with short demand** (§ below).

At end-2023 there were **402 traditional CEFs, down from 427 a year earlier —
a twelfth consecutive annual decline, about 36% below 2011** — with negative net
share issuance for a second year and no new launches. The universe we are
shopping in is shrinking, which matters for breadth (W10 §F) and for
survivorship (W1 §C).

**62% of traditional CEFs use leverage**, at an average structural leverage
ratio around 28% (bond funds 29%). The 1940 Act §18(a) requires **≥300% asset
coverage for debt and ≥200% for preferred**, tested when leverage is issued.
Below it, a fund may not declare common distributions or buy back common shares.

> **CORRECTED 2026-10-12.** This paragraph said a large NAV drawdown "forces
> deleveraging *mechanically*". §18 contains no maintenance test that compels
> redemption (15 U.S.C. 80a-18, fetched 2026-10-12; `docs/REFERENCES.md` §18
> row and §12j). Any forced deleveraging comes from the fund's own preferred or
> credit terms, which must be read fund by fund [U].

Leverage type differs by group and is a required control, never something to
average away:

- **Nuveen munis** lever through **tender option bond trusts** — a fixed-rate
  muni deposited in a trust that issues a floater to money funds and a residual
  to the fund. **The floater resets to the SIFMA Municipal Swap Index**, which
  is tax-exempt, resets **weekly (published Wednesdays by 4pm ET)** and trades
  structurally below taxable short rates. S&P put average fund-sponsored TOB
  leverage at ~2.5× in Dec 2023, rising to ~3.32× by Q2 2024.
- **PIMCO multi-sector** funds lever through **reverse repo** — 18–42% of
  managed assets in recent filings, at roughly 6.3% effective cost.
- For reference, Sept 2026: SOFR 3.65%, EFFR 3.63%.

### NAV: what it is, when it appears, and how stale it is

Rule 22c-1's forward-pricing mandate applies to **redeemable** securities and
therefore **not to CEFs at all**. Daily NAV striking is strong industry
convention reinforced by exchange norms, not a clean statutory daily
requirement. Nuveen's prospectus language is representative: NAV "determined as
of the close of trading (normally 4:00 p.m. Eastern time) on each day the NYSE
is open". **No sponsor documents a public posting time**, which is why the
evening decision was a race we did not control (W3).

Municipal bonds are **matrix-priced**. The MSRB reports fewer than 2,800 muni
trades a day across fewer than 1,500 unique securities against more than a
million CUSIPs outstanding, with two-thirds of the securities that trade at all
trading once or twice. Nuveen's own registration language says the pricing
service values a bond from *"yields or prices of municipal securities of
comparable quality, type of issue, coupon, maturity and rating"* — a curve, not
a trade. Bank-loan funds use dealer-quote surveys. Choi, Kronlund & Oh (2022,
JFE 145(2):296–317) find bond-fund NAVs "extremely stale" with returns
predictable over days to weeks, worse in crises; Cici, Gibson & Merrick ("Missing
the Marks", JFE) find cross-fund dispersion in month-end marks on *identical*
bonds, so part of the smoothing is **discretionary**, not mechanical.

**Rule 2a-5** (compliance 8 Sept 2022) moved fair-valuation to a board-overseen
"valuation designee" at each adviser. A family's smoothing profile can change
without announcement — and our time holdout begins 2023-01-01, immediately
after.

**CEFConnect italicises a NAV whose published date is earlier than the row's
date.** Capture the NAV's own as-of date, never just its value.

**Bond-market holidays on which the NYSE trades** — Columbus/Indigenous Peoples'
Day, Veterans Day — produce a mechanical discount swing every year: price moves,
NAV carries forward stale. W4 §C decides how the panel treats them.

### Ex-distribution arithmetic — and a correction

On the ex-date the distribution leaves the fund's assets, so **NAV drops too**,
not just price. With both falling by *D*, a discount `(P−N)/N` becomes
`(P−N)/(N−D)` — for a 10% discount and a 0.75% monthly distribution, about
**7bp**, not the 75bp earlier notes in this repo claimed. Bali & Hite (1998)
find the realised price drop is slightly *less* than the distribution because of
tick discreteness. **Earlier prompts asserting that an ex-date "moves price and
not NAV" were wrong; W4 §A measures the real coefficient and corrects every
string.**

> **Measured 2026-10-11 (W4, `results/cef/W4_ARTIFACTS_2026-10-11.md` §1):** on
> our 13 names, 2005–22, the arithmetic above is swamped by a price pattern.
> The discount *falls* on the ex-date and keeps falling for two more sessions,
> and the price drops by slightly *more* than the distribution, not less. Do
> not assume either the 7bp arithmetic or Bali & Hite's direction for these
> funds; read the note.

2023 traditional-CEF distributions were 67% income, 13% capital gains and **20%
return of capital** — which is the substance behind M8. Managed distribution
policies need an SEC exemptive order under §19(b)/Rule 19b-1 and covered about
32% of traditional CEFs in 2024, concentrated in multi-strategy and equity
funds rather than credit — so in our universe a distribution cut is more likely
to reflect real income degradation than a smoothing-policy choice.

### The secondary market and the closing auction

Our names run from about $3m a day (JFR) to $43m (PDI) in dollar ADV (undated,
17-name book; on CRSP 2024 the 13 ran from $1.26m (MHD) to $31.5m (PDI),
`results/data/universe_2026-10-08/`; re-measure before relying on either). We do not
move markets at the live screen (0.7% of ADV); **we pay ticks** — a one-cent
spread is 10.7bp on a $4.69 share and 2.9bp on a $17 share, against a 32.6bp
breakeven.

#### The tick convention — defined once here, cited everywhere else

**Added 2026-09-10, resolving W0 Part F.** Three documents quoted three
different numbers for PHK's tick and none stated its convention, so they read as
a dispute. They are three different quantities:

| quantity | PHK | what it is |
|---|---:|---|
| **half-tick** | 10.65bp | half a cent on $4.69 — `pre-clean-slate:_archive/docs/PLAN.md` §4.1 |
| **full tick** | 22.22bp | one cent on $4.51 — `pre-clean-slate:_archive/docs/PER_NAME_ARCHITECTURE.md` §4 |
| **charged half-spread** | 25.77bp | `config/costs.yaml`, **1.25× the full tick**, and that multiplier holds for all 17 CEFs |

**The ledger charges 25.77bp — 2.4× what PLAN's prose implies.** So:

- **State the convention wherever a tick figure appears.** A bare "PHK's tick is
  X" is ambiguous and has already been read three ways.
- **The number that enters a cost calculation is the charged half-spread**, from
  `config/costs.yaml`, because that is what the ledger actually applies.
- **The 1.25× multiplier is itself an assumption**, not a measurement. `W7` Part C
  measures spreads independently; if it disagrees with the yaml, the yaml is
  wrong and every net figure computed from it moves.

Per **H14**, do not key a rule on the numbers in this table — re-read
`config/costs.yaml` and say which convention you used.

**The auction rules differ by venue, and getting them from one fact sheet is how
you end up with a wrong specification.** Verified against rule text 2026-09-09:

**NYSE** (where the CEFs trade). MOC/LOC must be entered by **15:50 ET** — the
"Closing Auction Imbalance Freeze Time" of Rule 7.35(a)(8), defined as ten
minutes before the end of Core Trading Hours, so **it moves with early closes**.
After it, only orders opposite a published Regulatory Closing Imbalance are
accepted, and if none was published all are rejected. **MOC/LOC may not be
cancelled or reduced after 15:50 "even to correct a legitimate error"** — the
only carve-out needs a Trading Official's approval. The Regulatory Closing
Imbalance publishes when it is **500 round lots or more (50,000 shares)** under
Rule 7.35B(d)(1), and — correcting an earlier version of this brief — **it is
published once, at 15:50. It does not refresh.** NYSE also retains **DMM
discretion**: a DMM may close a security without a trade, or run the auction
manually.

**Nasdaq** (where TLT trades, so the gamma hedge lives here). **MOC until 15:55,
LOC until 15:58**, IO until 16:00, with cancel/modify frozen from 15:50. Its
NOII **does** refresh — every 10 seconds from 15:50, then every second from
15:55 — with no share threshold gating it. No DMM.

**NYSE Arca** (HYG, LQD, SPY): Rule 7.35-E is parallel in architecture but
**its cutoff and threshold could not be verified** and vendor sources only
suggest parity with NYSE. **Confirm before routing.** (2026-10-08: a 2018 SEC
release puts Arca's closing imbalance freeze at 15:59. That is not the current
rule text; `docs/REFERENCES.md` §3.) *Correction 2026-11-02: the cutoff is
verified. SEC Rel. 34-103886 (SR-NYSEARCA-2025-67, 90 FR 43676, 10 Sep 2025)
puts the Closing Auction Imbalance Freeze one minute before the close, and
NYSE's Arca timetable reads 15:00 imbalance publication, 15:59 freeze (only
offsetting MOC/LOC accepted, cancels rejected). The publication threshold is
still unverified. `docs/REFERENCES.md` §3.*

Our clips are one to three orders of magnitude below 50,000 shares, so we never
register as a published imbalance. NYSE's **Closing IO Order** (Rule
7.31(c)(2)(D)) is limit-only and auction-only and, unlike MOC/LOC, may be entered
on **both** sides up to 16:00 — note NYSE is amending this order type now
(SR-NYSE-2026-36, implementation by Q1 2027).

Closing auctions matched **$55.5bn a day, 9.44% of US notional, in Q2 2024**.
And the number that matters for a thin CEF: **about 3.3% of NYSE auction volume
goes unfilled, rising to 6.3% for non-Russell-1000 names** — which is what all
seventeen of ours are.

**No CEF-specific bid-ask, quoted-depth or closing-auction-share dataset exists
publicly.** These must be measured from our own fills and quote history (W7).

### The short side

CEF borrow is structurally thin for a reason that will not improve: the share
count is fixed, only fully-paid and excess-margin shares are loan-eligible, and
only where the holder has opted into a lending programme (IBKR's requires a
margin account or a cash account with liquid net worth above $25,000). **The
marginal CEF holder is a retired retail income investor in a cash account —
precisely the holder whose shares are not in the pool.** Hence NAD's 3,000
visible lendable shares against our 8,129 short.

**⚠ That last number is now disputed and must be re-measured before any
availability work (2026-09-10).** The retired public file and TWS **tick 236**
were believed to report the same exact-share figure. On the first day both
could be compared they did not:

| | we short | file (09-08) | tick 236 (09-10) | |
|---|---:|---:|---:|---|
| NAD | 6,550 | **3,000** | **83,942** | 28× |
| NVG | 4,679 | 20,000 | 149,125 | 7× |
| MHD | 8,856 | 250,000 | 102,491 | 0.4× |
| NZF | 271 | 150,000 | 275,577 | 2× |

On the file's numbers 18.7% of today's short book is unbuildable; on the API's,
**0%**. The entire premise of the availability cap turns on which is right, and
one observation two days apart cannot settle it — the two could be measuring
different things (indicative pool vs currently-shortable, and whether shares
already lent to us are netted out). Until W8 Part A resolves it with a week of
paired observations, treat "11.4% of the short book is unbuildable" as
**unverified**, and do not size a cap on either number. Tick 236 only answers
when no other client session is holding market data — it returned NaN under
error 10197 all morning, which is why the comparison had never been made.

IBKR's public file (`shortstock/usa.txt`) was retired on 2026-09-09 (404; the
ftp hosts do not answer). The fee now comes from the API's FEE_RATE bars —
which also carry five years of history (H4); availability comes only from
TWS tick **236** returns the same exact-shares figure while legacy tick 46 is a
coarse bucket. The fee accrues as **market value × fee rate ÷ 360**, with market
value marked up to **102%** of the prior settlement price — not the ÷252 on the
raw close our harness uses (W8 §A).

**Recall is monthly, not occasional.** Every one of the 17 distributes monthly.
A lender whose shares are on loan through a record date receives a payment in
lieu, which is ordinary income — never a qualified dividend and, for a
**municipal** fund, never the exempt-interest dividend the holder bought the
fund for. Tax-sensitive muni lenders therefore have a standing monthly incentive
to recall before the record date. A discretionary recall requires two trading
days' notice; thirteen consecutive days on the Reg SHO threshold list forces a
mandatory buy-in at the start of T+14.

**We are not alone on the short side.** Alexander & Peterson (2017, *Journal of
Financial Markets*) find CEF short-selling rises with the premium and that
heavily-shorted funds see the premium decline over the following **five days** —
our horizon. FINRA publishes short interest twice monthly for all listed
securities, free, about seven business days after settlement.

### Corporate events, and a 2026 regime change

Saba, Karpus and Bulldog drove about 90% of 2023 CEF activist actions and held
stakes in **44% of all traditional CEFs** at end-2024. Across 34 funds with
activist-forced tenders 2015–2022, excess discount versus peers averaged −4.4%
the year before the initial 13D, narrowed to −1.2% pre-tender and −0.2% during
the tender, **then widened back to −3.3% the year after** — the effect largely
round-trips within a year, and 75% of activists fully exit within a year (48%
within three months). Bradley, Brav, Goldstein & Jiang (2010, JFE): a
successful open-ending **eliminates** the discount; the "roughly **half**" figure
describes funds that were attacked and did **not** convert.

> **CORRECTED 2026-10-08.** Until today this paragraph said open-endings "cut
> discounts to roughly half" and that the Supreme Court ruled "unanimously". Both
> had already been corrected in `docs/REFERENCES.md` §5 ([V], read in full) and
> never carried back here: the half figure is the non-converters' path, and the
> vote was **6–3**.

**But on 11 June 2026 the Supreme Court held, 6–3, that §47(b) of the
1940 Act creates no implied private right of action**, narrowing the activist
litigation toolkit against control-share provisions. Historical
activism-driven convergence should not be assumed to repeat at the same rate.

Two mechanics worth knowing precisely: **SEC staff require a CEF tender to be
priced at NAV as of the close of the tender's last day** — a dated, NAV-priced
convergence event, and being short into one is a known, avoidable loss. And
rights-offering subscription prices are commonly set at about 90% of the average
close over the expiration date and four preceding sessions, over a ~30-day
period; **transferable versus non-transferable is the field that matters**,
because non-transferable rights force mechanical dilution on non-participants.

> **CORRECTED 2026-10-12, two points, both already recorded in
> `docs/REFERENCES.md` and never carried back here:**
>
> 1. **The tender "staff requirement" is a sponsor's description, not SEC
>    text.** It comes from a Nuveen N-2. Rule 13e-4 has no NAV-pricing
>    requirement and no staff letter was found (fetched 2026-10-12). Tenders at
>    97% and 99.5% of NAV exist, so read it as fixing the NAV *date*, not the
>    percentage, and take each tender's price basis from its own offer document.
> 2. **The rights-offering formula is not "about 90%".** On HYT's 2022 offering
>    it was **95%** of the average close over the expiration date and the four
>    preceding sessions, **floored at 90% of NAV** and capped just below NAV
>    (`docs/REFERENCES.md`, HYT 424(b)(5) row, [V]).

### Who runs these funds

Verified 2026-09-09 against `cef_facts.csv`. **Do not infer the sponsor from the
group** — the muni group is two sponsors with two different leverage mechanisms,
and an earlier draft of this brief got it wrong.

| sponsor | names |
|---|---|
| Nuveen | NAD, NEA, NVG, NZF (muni, **TOB / SIFMA**), JFR (loan) |
| BlackRock | **MQY, MHD (muni, preferred: VRDP/MFP)**, BIT (multi), HYT (hy) |
| PIMCO | PDI, PTY, PDO, PCN, PHK, PFN (multi, **reverse repo**) |
| DoubleLine | DSL (multi) |
| AllianceBernstein | AWF (hy) |

> **CORRECTED 2026-10-20.** The BlackRock row above is incomplete. Both
> BlackRock munis **also lever through tender option bond trusts**, and MHD's
> preferred is **VMTP**, not VRDP or MFP. So TOB leverage is not a Nuveen-only
> mechanism, as the leverage list in "The wrapper" implies. Their annual report
> for the year to 2026-07-31 (N-CSR 0001193125-26-413740) shows:
>
> - **MHD**: TOB trust certificates $852.4m, VMTP shares $717.8m, no VRDP;
> - **MQY**: TOB $476.9m, VRDP $847.4m.
>
> MQY showed both in 2022 too. Whether their floaters reset to SIFMA is not read
> [U]. Source: `docs/REFERENCES.md` §12aw;
> `results/cef/MUNI_HAZARD_FLAGS_GATE_2026-10-20.md` §6.

### Options

**No CEF we trade has usable listed options** — verified per ticker, not
assumed. Sixteen of seventeen have no listed options market at all, including
PDI and PTY, the two most likely by market cap. **DSL is a single exception**: it
appears in two independent options-analytics platforms' optionable universes,
but its depth is unverified and must be checked on a live broker chain before
anyone relies on it. For scale, business development companies (ARCC, PSEC) *do*
have options while large plain equity CEFs (ADX, UTF) do not — the gate is
order flow, not fund structure.

Whatever we do with options therefore happens in HYG, LQD, TLT, JNK or SPY. **Only HYG is genuinely usable** as a
credit-vol instrument; JNK, LQD, MUB, EMB and BKLN list options with materially
thinner books, TLT is the rates-vol venue, and the institutional alternatives
(CDX payer swaptions; Cboe's IBHY/IBIG options on iBoxx futures) are out of
reach from this account.

Long gamma pays the variance risk premium. Implied runs 1.3–1.5× realised in
the repo's own SPY data; the premium is documented in credit as well as equity;
and in the one study that includes HYG the average synthetic variance-swap
payoff across the ETFs examined was about **−74%**. A systematic long-gamma book
**loses on average and wins in stress.**

**IBKR paper fills options at the displayed price, from top of book, with no
market impact**, and does not support penny-increment option fills in paper.
Paper option P&L cannot establish that any option strategy has positive expected
value (this was W14 §C; W14 is deleted and options are closed).

Basis risk is real: in March 2020 CEF discounts widened by more than 1,600bp
while HYG's own price-to-NAV deviation reached −5% to −8% intraday and its
average absolute stated premium/discount rose from 0.21% to 1.06%.

### One honest gap

**There is essentially no academic literature validating a CEF discount-reversion
signal at a 1–5 day horizon.** Pontiff (1995, JFE) finds a 20%-discount fund
earns about 6pp more over *twelve months*; Ji (2013) estimates reversion at
8.6%/month, a **7.7-month** half-life. Our pooled AR(1) φ = 0.9722 implies 24.6
days — an order of magnitude faster. Being novel is allowed. Being novel and
untested against bid-ask bounce, stale NAV and ex-date arithmetic is not, which
is why **W4 runs before any further trial is spent.**

---

## 4. The scoreboard

The quantities the capture work moves, each measurable faster than P&L. **No
"live today" column, deliberately** — it carried the arm rate as "3 of 26" while
three other documents disagreed. Run the command in the last column.

| goal | target / reference | how measured |
|---|---|---|
| Capture ratio, net ÷ gross Sharpe | the joint optimiser's modelled ratio (W12) | `python3 scripts/cef/band_frontier.py` |
| Turnover | below the retired calendar's turnover within 20 armed sessions (pre-registered in `results/cef/PREREG_BAND_2026-09-06.md`) | broker fills only |
| Cost robustness | never flips sign across the cost grid | harness, 5/15/30bp |
| Turnover stability, era sd/mean | ≤ the band's | harness by era |
| Borrow drag | cut by shorting different names; re-measure on the daily fee panel first | `data/cef/cef_borrow_history.parquet` |
| Availability | 0% of the short book unbuildable | TWS tick 236 + FINRA (method in W8) |
| Effective breadth | ≥ 4 | dashboard `/api/factors` |
| Execution | below the breakeven cost per unit turnover, with a standard error small enough to act on | `/fill-audit` |
| Uptime | every trading day, or an alert | `python3 -m ops.session_uptime` |
| Dust | 0 | dashboard `/api/trades` |
| Return convention | total returns | W4 §A |

---

## 5. The harness, and the rules every research prompt inherits

Do not build another backtester. The canonical one is `scripts/research/harness.py` (restructured with the team lead's ruling of 2026-10-27; `band_frontier.evaluate` delegates to it, byte-identical on the live book). Extend it visibly.

```python
from scripts.cef.band_frontier import build_targets, band, calendar, evaluate
from scripts.cef.spec import BAND_WIDTH     # never write the width as a literal
from scripts.research import harness        # the one lag, report(), the family builders
T, R = build_targets()          # frictionless daily targets as the sleeve builds them
H_live = band(T, BAND_WIDTH)    # the live policy, read from the frozen spec
H_old  = calendar(T, 2)         # the previous configuration
res    = evaluate(H, R)         # applies H.shift(2): decide t, MOC fill t+1, earn t+2
rep    = harness.report(H, R)   # gross headline, 5/15/30bp grid, H5 eras, fit and holdout rows
# other families: harness.cross_sectional_weights / event_weights; ML: scripts/research/ml.py;
# store the trial's series: scripts/research/registry.py; compare variants: resampling.sharpe_diff
```

**H1.** Execution convention is **shift(2)**. Anything scored differently is not
comparable to any number in the repo.

**H2. Turnover-matched comparisons only.** A construction that trades more looks
better gross and worse net; neither is the point. Find the band width or cost
coefficient that matches the reference's turn/yr within 5% and compare there.

**H3. Cost grid 5 / 15 / 30bp** on every table, and where W7 §C exists, the
measured per-name per-era column beside it. The answer must not flip sign across
the grid.

**H4. Borrow is charged separately and labelled.** Since 2026-09-10 the fee is
a **daily series, by name, 2021-09-13 onward**: `data/cef/cef_borrow_history.parquet`
(43 of 44 names, 52,978 rows, FCT none — as built 2026-09-10 [S]), from IBKR
`reqHistoricalData(whatToShow="FEE_RATE")`, built by
`scripts/cef/fetch_borrow_history.py`. Charge the actual daily fee over
2021–26; before 2021-09 there is no fee data — use the 2021–26 mean by name
and label those rows an assumption. "One day of fees applied to history" is
no longer the method. **The history is not benign:** the PIMCO premium funds
averaged PTY 29.7% (max 178%), PFN 19.7%, PHK 16.6%, PCN 13.8%, PDO 13.4% to
borrow over 2021–26 against 0.3–1% today, so every net-of-borrow figure in
this repo computed on today's fees (the 1.22%/yr drag included) is suspect
until re-measured on the panel.

**H5. Eras:** 2005–09, 2010–14, 2015–19, 2020–22, 2023–26. Pre-2013 is thin.
Report era turnover sd/mean.

**H6. IC** is Spearman between the signal at *t* and the forward 2-day return
starting *t+2*, **non-overlapping**, expected negative, with standard errors
clustered by date (W4 §E), never naive.

**H7. No lookahead.** Every estimated quantity uses data strictly before the
date it is used on; state the alignment in a comment; assert it at runtime.

**H8. No sweeping and picking.** Derive parameters, then check they land on a
plateau. Picking the argmax of a swept column is how `z_window=63` was chosen,
and it failed out of sample.

**H9. The 27 untouched names** are the comparison set. Any specification change
is run on them once, on the combined spec, before promotion. **Trading any of
them consumes the set.**

**H10. Count trials.** Two counters, each with its own deflated-Sharpe bar
√(2 ln N): **CEF** and **GAMMA** — read both from the counter table in
`docs/RESEARCH_STATE.md`, never from a prompt. Every prompt says which it
increments. The combined book is judged on the joint record.

**H11. Pre-register before the session that trades it.**
`results/cef/PREREG_BAND_2026-09-06.md` is the shape. Every adoption names the
live statistic and horizon that would reverse it.

**H12. Negative controls.** If a mechanism says an effect lives in munis, test
it in HY too. If it is equally strong where the mechanism cannot operate, it is
not what you think.

**H13. Time holdout.** Every estimated quantity is fitted on data before
**2023-01-01**; every table shows a fit row and a 2023–2026 holdout row.
Derived quantities are computed on the fit period and applied unchanged.
Rolling estimators are fine on the holdout; what is forbidden is *choosing*
anything with sight of 2023–26. The 27 remain the second check, and if the two
disagree, the spec is not adopted and the disagreement is written up.

**H14. No decision rule may key on a number written in these documents.**
Every figure in this brief and in the prompts — measured, fetched or cited — is
a **starting observation with a date and a method**, recorded so you know what
to expect and can tell quickly if something has changed. **None of them is an
input to a decision.** A prompt's rule must re-measure the quantity it keys on,
at run time, from data, and must state what it does under either outcome.

This applies to our own measurements as much as to the literature. A borrow
panel two days old, an option chain snapshotted on one afternoon, a variance
decomposition run on a panel that ends six weeks ago, an era table computed
before the return convention was fixed — all of these go stale, and several
already have. **If a prompt reads "X is 59.6%, therefore do Y", it is wrong and
should read "measure X this way; if it is high, Y follows; if not, Z."**

The test to apply when writing or reviewing a prompt: *could this rule still be
executed correctly by someone who deleted every number from the document?* If
not, the rule is resting on a number instead of on a method.

**H15. Returns are total returns** once W4 §A lands. If the distribution panel
cannot cover a name-date, the harness **raises**; it never falls back to price
returns silently.

---

## 6. House rules for code

**Moved 2026-09-14.** The house rules for code are `CLAUDE.md`, "Hard rules —
code", which every agent loads. The earlier copy here is in the snapshot at git tag `pre-clean-slate`
`pre-clean-slate:_archive/docs/prompts/00_BRIEF_2026-09-14.md` §6.

---

## 7. Standing decisions

**Moved 2026-09-14, verbatim, to `docs/SYSTEM.md` §5**, which owns them. Do not
re-ask a question that table answers; departures from it must be explicit.

---

## 8. The queue

**Moved 2026-09-14; the queue itself deleted 2026-09-28; the plan is `docs/ROADMAP.md`.** Every work order is
under `pre-clean-slate:_archive/docs/prompts/` (git tag `pre-clean-slate`); the open work is
`pre-clean-slate:results/ops/ALPACA_MIGRATION_MANIFEST_2026-09-28.md` §5–§6. The
ordering rationale and trial budget as written on 2026-09-09 are in the (deleted)
snapshot `pre-clean-slate:_archive/docs/prompts/00_BRIEF_2026-09-14.md` §8.
