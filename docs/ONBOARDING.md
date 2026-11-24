# Onboarding: your first days on the credit book

**This file owns** setting up an analyst's Mac and a guided tour of the codebase.
Who does what, and how work reaches `main`: `docs/TEAM.md`. The rules: `CLAUDE.md`.
What is true right now: `python3 -m ops.orient`. This file holds no figures about
the book, on purpose: they go stale, and the commands do not.

---

## 1. The book in one paragraph

A **systematic credit closed-end-fund discount-reversion book**. A closed-end fund
(CEF) publishes a net asset value (NAV) each day, and its shares trade at whatever
the market pays, usually at a discount to NAV. Nothing creates or redeems shares
against the basket, so nothing pulls the price back to NAV. The book buys credit CEFs
that are unusually cheap against **their own** discount history, shorts the unusually
rich ones in equal dollars, sizes the whole to a volatility target, and trades only
when a position drifts outside a no-trade band. It places its own orders at the
close on Alpaca paper, every trading day, from a cloud VM. The full account is
`docs/SYSTEM.md` §1; why the edge exists and who is on the other side is
`docs/BRIEF.md` §2.

**How one trading day runs** (`docs/RUNNER.md`, "The session, in order"):

```
evening of t     NAVs for t land  ->  refresh panels  ->  decide the plan on t's prices and NAVs
morning of t+1   backstop: the same plan, if the evening run did not finish
15:52-15:58 t+1  the saved plan's orders go out (on paper, market orders just before the close:
                 CLAUDE.md order-path rule 3; docs/RUNNER.md "Paper execution")
close of t+1     filled                                   ...and the position earns t+2's return
after the close  verify: reconcile with Alpaca, score the day, one verdict line
night            collect: the day's data, checked
```

That is the `shift(2)` convention every backtest in this repo must reproduce:
decide at *t*, fill at *t+1*'s close, earn *t+2*.

---

## 2. Set up your Mac

You need: a GitHub account, with the team lead's invitation to this repository
accepted (GitHub e-mails it to you; it gives you Write access: push branches,
open pull requests).

**2.1 Tools**

```bash
xcode-select --install                    # Apple's command-line tools, if not already present
# Homebrew, if not already present: https://brew.sh
brew install python@3.13 gh git           # requirements.txt names Python 3.13 as the version the system runs on
gh auth login                             # GitHub, in the browser
```

Then install Claude Code (https://docs.claude.com, "Claude Code") and sign in.

**2.2 The repository**

```bash
gh repo clone quanttqueensu/CreditTrading
cd CreditTrading
python3.13 -m venv .venv                  # a private Python for this repo
source .venv/bin/activate                 # run this in every new terminal
python3 -m pip install -r requirements.txt
```

**2.3 Your credentials.** Create `config/.env` (it is gitignored and never
committed). Every value is **your own**; the book's keys never leave the team lead.

```bash
# Your own Alpaca PAPER account, never the book's. The research scripts read
# these two names, so on your machine they mean your account.
ALPACA_CEF_KEY_ID=
ALPACA_CEF_SECRET_KEY=

# The read-only Cloudflare R2 token the team lead gives you (the WRDS mirror;
# research only, never live). src/data/r2.py raises, naming the variable, if one is missing.
R2_ENDPOINT=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET=

# Your own contact for SEC EDGAR's fair-access policy: your name and your e-mail.
# scripts/data/edgar_client.py has no default and refuses to run without it.
SEC_USER_AGENT=
```

Check what is set without printing a value:
`python3 -m quantt.broker.alpaca_probe --check-keys`. Never paste a key into a
chat, an issue, a commit or a Claude session.

**2.4 Data.** `data/` is gitignored: you build your own copy. The core CEF price
and NAV panels:

```bash
python3 scripts/cef/stage_cef.py          # full history (network: Yahoo)
python3 scripts/cef/fetch_daily.py        # bring it up to date
python3 scripts/fetch_cef_distributions.py
```

Each lane's other panels, and which source feeds what, are in `docs/DATA.md` §2.
Your `data/` is yours: it does not reach the book, which decides on the prod
machine's own panels.

**2.5 Check it works**

```bash
python3 -m ops.orient                     # where you are, and what is true right now
python3 -m pytest                         # the test suite; never quote a count, run it
python3 -m ops.doc_audit --check          # do the documents still say true things?
```

What you should see:

- **orient's PROD section reads `UNMEASURED`**, because your machine has no route
  to the VM. That is correct: prod is the team lead's. The Alpaca snapshots orient
  shows are the team lead's record of the book's account.
- **pytest**: tests that need the real panels skip, with the reason stated, until
  you have run 2.4; nothing should fail. A test that fails only because a panel is
  missing is a bug in the test (it should skip and say why): report it to the
  team lead. CI runs the same suite on every pull request, on a
  clone with no `data/` at all.
- **doc_audit**: no `DRIFT`.

**2.6 Claude Code.** Run `claude` in the repository. `CLAUDE.md` loads by
itself, and a banner shows the book's state. Tell Claude once, durably, who you
are: add this line to `~/.claude/CLAUDE.md` (your personal file, outside the repo):

```
In the quanttqueensu/CreditTrading repository I am an analyst in the <FICC risk | equity risk | cross-asset signals, dashboard and data> lane, not the team lead.
```

`CLAUDE.md`, "Who you are working for", tells Claude what that means.

---

## 3. A map of the repository

| path | what it is | live or research | kept by |
|---|---|---|---|
| `src/deploy/sleeves/cef_discount.py` | **the strategy**: discount, z-score, weights, volatility scalar, band | live | PM |
| `src/deploy/` (the rest) | the sleeve interface every strategy obeys, the registry, the static benchmark | live | PM |
| `quantt/session/` | one trading session: refresh, decide, the nine gates, record, send, verify, score | live | PM |
| `quantt/broker/` | the Alpaca REST client and the read-only account probe | live | PM |
| `quantt/collect/` | the nightly data collector | live | PM |
| `quantt/deploy/` | the prod installers (laptop and VM) and secrets at boot | live | PM |
| `ops/specs/`, `ops/books/` | the frozen spec and the book json: governance, not config | live | PM |
| `ops/orient.py`, `ops/prod_state.py`, `ops/doc_audit.py` | where am I; which machine is prod; are the documents true | tooling | PM |
| `scripts/cef/` | **the research harness**: `band_frontier.py` (its `evaluate()` is the canonical backtest), `validate.py`, diagnostics, the CEF trials. Also `spec.py` and `fetch_daily.py`, which the runner calls | research, plus two live files | PM |
| `scripts/macro/` | fixed-income research: macro events, credit events and fixed-income instruments | research | FICC risk |
| `scripts/xasset/` | equity and ETF research: the XASSET protocol, runner and trials | research | equity risk |
| `scripts/events/` | corporate-event research: the merger pair, NAV tenders, SPACs, merger arbitrage, their gates | research | PM |
| `scripts/gamma/` | the short-TLT-variance test: Cboe volatility indices, gate G2, option snapshots | research | PM |
| `scripts/data/`, `scripts/rv/`, `scripts/holdings/`, `scripts/build_etf_daily.py`, `src/data/` | fetchers and data builds: the EDGAR client, CRSP stagers, CEFConnect, factor files, ETF bars, the R2 reader | research | cross-asset, dashboard and data |
| `dashboard/` | the read-only dashboard, and `snapshots/`, the book's nightly snapshot it reads (`dashboard/README.md`) | monitor | cross-asset, dashboard and data |
| `src/backtest/` | the original engine, lookahead guard, cost model and walk-forward | research | PM |
| `results/<family>/` | dated findings and pre-registrations, each true **as of its date** | record | that family's lane |
| `docs/` | one owner per question; `docs/INDEX.md` lists them | | per the index |
| `.claude/` | Claude Code's skills, agents, hooks and workflows (`.claude/README.md`) | | PM |
| `config/` | the cost model, and your own `.env` | live | PM |
| `data/` | the panels: gitignored, your own copy | | |

---

## 4. What to read, in order

Everyone, in your first days:

| # | read | for |
|---|---|---|
| 1 | `README.md` | the layout and the commands |
| 2 | `docs/SYSTEM.md` §0–§4 | what we trade, what is known and what is not, what binds, how it runs |
| 3 | `CLAUDE.md` | the hard rules. They bind people as much as agents |
| 4 | `docs/TEAM.md` | your lane, and how your work reaches `main` |
| 5 | `docs/BRIEF.md` §1–§3 and §5 | the theory, how the instruments trade, the harness rules H1–H15 |
| 6 | `docs/RESEARCH_STATE.md` | the trial counters, the verdict legend D1–D7, what is dead and why |
| 7 | `src/deploy/sleeves/cef_discount.py` | the strategy, in code. Its docstrings carry most of the incident history |
| 8 | `evaluate()` in `scripts/cef/band_frontier.py` | the one backtest every result must be comparable to (`/harness`) |
| 9 | `docs/RUNNER.md`, "The session, in order" | how a day trades |
| 10 | `results/cef/RESEARCH_PLAN_2026-10-09.md` | the programme the lanes work from |

Then your lane:

| lane | read next |
|---|---|
| FICC risk | `scripts/cef/exposure_readout.py` and `scripts/cef/live_attribution.py` (the book's rate, credit and muni risk); the KILLED and WATCH tables of `docs/RESEARCH_STATE.md` (the credit-ETF, flow, trend and calendar ideas that died here, including XASSET-X3, the month-end Treasury extension that was term premium; the forced IG-to-HY index deletion on WATCH stays with the PM); `docs/BRIEF.md` §1 (what finding alpha means for this book); `results/cef/W10_PARTB_2026-10-12.md` (where the book's edge lives across fund groups, which an overlay has to respect); `results/cef/RESEARCH_PLAN_2026-10-09.md` §3, trial C2 (macro observables per fund group, planned on CEF: whether it moves to MACRO is the team lead's open question, so do not start a test like it); `results/cef/PORTFOLIO_FRAMEWORK_2026-10-15.md` (how a signal joins the book) |
| Equity risk | `scripts/xasset/book_profile.py` and `scripts/xasset/specialist_betas.py` (written for the core; adapt them for C4); `results/xasset/PREREG_XASSET_SLATE_2026-10-12.md` and `results/xasset/XASSET_RESULTS_2026-10-14.md` (the first slate and why each test failed); `scripts/xasset/protocol.py` and `scripts/xasset/runner.py` (how a slate runs once); `results/cef/PORTFOLIO_FRAMEWORK_2026-10-15.md` (how a new sleeve joins the book) |
| Cross-asset signals, dashboard and data | `results/xasset/XASSET_RESULTS_2026-10-14.md` (the first four cross-asset tests and why each failed); `CLAUDE.md`, "Any monitor is read-only"; `dashboard/README.md` (the snapshot it reads, and what a snapshot may never carry); `docs/RUNNER.md` (what a session records); `quantt/session/records.py` (the on-disk record the snapshot is cut from); `ops/orient.py` and `ops/prod_state.py` (read-only readers that already exist); `docs/HISTORY.md` (the IBKR-era dashboard, at tag `pre-clean-slate`); `docs/DATA.md` and `CLAUDE.md`, "Hard rules: data" (the data platform you keep: every series has a fetcher and a source note in `docs/REFERENCES.md`) |

---

## 5. The tools

| tool | use it |
|---|---|
| `python3 -m ops.orient` | first, every session |
| `/graveyard` | **before proposing anything**: what has died, and how |
| `/harness` | before writing any backtest |
| `/repro` | before quoting any figure |
| `/prereg` | to draft a pre-registration for a trial |
| `/research-idea`, `/backtest-request` | saved workflows: an idea taken to a reviewed result; one backtest question, independently re-derived |
| the subagents (`.claude/README.md`) | one research line of specialist seats: `statistician` before spending a trial (is the test powerful enough to find the effect?), `beta-detector` before trusting a result, `quant-reviewer` after writing research code |

A change to a frozen spec or a book json follows `/spec-change` on your branch,
like any proposal; the team lead decides and releases it. The team lead's only:
`/release-check`, `/daily-ops` (it reads prod's state directory), and everything in
`docs/RUNBOOK.md`.

---

## 6. Words you will meet

| term | meaning | owner |
|---|---|---|
| **MOC** | market-on-close: an order filled in the closing auction (`time_in_force=cls` at Alpaca) | `CLAUDE.md`, order-path rule 3 |
| **`shift(2)`** | decide at *t*, fill at *t+1*'s close, earn *t+2* | `docs/BRIEF.md` H1 |
| **discount, z** | `100·(price − NAV)/NAV`; z-scored against the fund's own history, shifted a day | `docs/SYSTEM.md` §1 |
| **band** | the no-trade band: trade a position back to the band's edge only when it drifts outside | `docs/SYSTEM.md` §1 |
| **frozen spec** | the versioned JSON that fixes every live parameter; read only through `scripts/cef/spec.py` | `ops/specs/`, `/spec-change` |
| **IC, TC, BR** | the signal's skill, the share of the ideal book that survives costs, and effective breadth: IR ≈ IC · TC · √BR | `docs/SYSTEM.md` §3 |
| **trial, counter** | one tested specification; each data source counts its own, and the bar to pass rises with the count (√(2 ln N)) | `docs/RESEARCH_STATE.md` |
| **pre-registration** | what a trial will test and what would kill it, written and approved before any return is computed | `/prereg` |
| **zero-trial** | measurement that computes no strategy return, so spends no trial | `docs/RESEARCH_STATE.md` |
| **D1–D7** | the verdict legend: no edge; costs eat it; old data only; it is beta; inventory; conditional; too few trades | `docs/RESEARCH_STATE.md` |
| **holdout** | data sealed until a pre-registered test opens it, once | `CLAUDE.md`, "Hard rules: research" |
| **gross, cost grid** | every table leads with gross P&L, with 5/15/30bp of cost beside it | `docs/BRIEF.md` H3 |
| **[V] [S] [U]** | provenance: verified, sourced but not re-read, uncertain | `docs/REFERENCES.md` |
| **armed, `DRY_RUN`** | whether prod sends orders. `DRY_RUN=1` always halts it | `docs/RUNBOOK.md` |
| **release tag** | `release-YYYYMMDD-N`: the commit prod runs | `docs/RUNBOOK.md` §1 |

---

## 7. When something is wrong

- **A document says something you think is false**: check it (`/repro`), then fix
  it in a PR with a dated correction note, not a silent edit
  (`.claude/rules/documents.md`, rule 5).
- **A figure you need is not in the repo**: it is a stated gap, never an estimate
  (`CLAUDE.md`, "Hard rules: data").
- **You are not sure whether something touches the live path**: it is in
  `docs/TEAM.md` §2, or it is not. If in doubt, say so in the PR.
- **Anything about prod, the VM or the book's account**: ask the team lead.
