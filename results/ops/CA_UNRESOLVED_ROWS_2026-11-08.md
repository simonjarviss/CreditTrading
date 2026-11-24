# The corporate-action gate: the ISIN fix, and the three unresolved rows to re-rule (2026-11-08)

> **2026-11-24, before merge.** The team lead ruled "Fix first, block later" (`docs/SYSTEM.md` §5,
> 2026-11-24; `EVIDENCE_LOG` E-2026-11-24-11): the fix and the CUSIP check ship with both books still
> in `report`. Where this note says the gate goes back to `halt` in the release, that was the
> 2026-11-09 plan, which never shipped. `halt` waits for a later ruling. The measured figures below
> are as of 2026-11-08 and 2026-11-09 and were not re-run for the merge.

> For the team lead, ruling of 2026-11-08 ("Start the fix"). Part 1 is the bond-ISIN
> fix (branch `ca-isin-fix`). Part 2 brings the three rows for a ruling. **Nothing here
> changes either book json's `corporate_actions.mode`, and no `ca-ack` was run.**
> Labels: [V] verified by a fetch or a measurement named here, [S] sourced but not
> re-read, [U] uncertain. The feed figures are from one read through the repo's own
> client on 2026-11-08 of process dates 2025-11-01 → 2028-11-08 (`data_quality=all`,
> the 13 non-dividend types, 3,638 rows; the raw pages are not committed).
> Reproducer for every measured figure: `results/ops/ca_unresolved_2026-11-08/measure.py`
> (read-only, GET only; the recorded-window figures also need the private plan copies).

> **Updated 2026-11-09.** The team lead ruled "Accept all three" on §2's rows and "Build a
> check against our CUSIPs" on §3's open question; the check is built and §5 says what it
> changes (branch `ca-isin-fix`, unreleased; both books stay in `report`). §1–§3 are the
> note as written on 2026-11-08, with dated corrections where a statement has been overtaken.

## 1. What was wrong, and what the fix changes

**The bug [V].** `quantt/broker/alpaca.py` `_ca_symbol` accepts a value only if it
matches the ticker pattern (`_SYMBOL_RE`: a capital letter, then at most nine more of
`A-Z 0-9 .`). A value that does not is reported as "not a symbol", and `_ca_read`
then treats every such value as a **missing party**. `corp_actions.blocking_events`
judges a missing party as each of the gate's held and targeted names in turn.

Alpaca's feed sends real identifiers in these fields, which were never missing:

| what the field holds | fields, process dates 2025-11-01 → 2028-11-08 | how `_ca_read` treated it (origin/main) |
|---|---|---|
| a bond's ISIN (12 chars, e.g. `USU67540AA98`) | 58 rows: 57 partial calls, one reorganization [V] | missing party, judged as each of our names |
| a CUSIP-format value starting with a digit (`816CVR021`, `47010C847`, `929CNT012`) | 148 rows (151 fields) [V] | missing party, judged as each of our names |
| an exchange-suffixed code (`NOEA:XETR`, `NOEA:XTER`) | 2 rows [V] | missing party, judged as each of our names |
| null or empty, the ruling's original case | 0 rows [V] | missing party |

Every one of the 208 unresolved rows in that read carries an identifier; none is
actually empty [V]. The word "missing" in the book json notes and the records is
what the code said, not what the row held.

The 58 bond ISINs are the fix's target: every one is a US ISIN whose check digit
holds and whose CUSIP part equals the row's own `cusip` field, and all carry an
alphabetic issue code (CUSIP positions 7–8, the debt convention) [V].

**The fix.** A value is classified as a bond by `_ca_bond_isin` when it is
ISO 6166-shaped with a correct check digit, is a US ISIN, its CUSIP part matches
the row's own CUSIP field for that party, and its issue code is alphabetic. Such a
party never enters `parties`, so it cannot be matched against a ticker. The row is
recorded (`bond_rows` in the gate's record), not dropped, and blocks nothing. A
value that fails any test stays a missing party, unchanged, and each such row now
carries `saw`: what the field actually held and why it was not read as a bond.

**Why an alphabetic issue code cannot be one of ours.** All 87 of the book's
funds (13 core, 74 C4), 88 CUSIPs in all, have numeric issue codes (84 `10`, 3 `20`
and one `87`, IGR's second CUSIP `12504G878`, on Alpaca's own dividend rows for
2025-05-01 → 2026-11-08) [V]. That numeric = equity and alphabetic = fixed
income is the CUSIP convention [S]; the measurement is what the gate relies on.
An equity-format ISIN stays unresolved (it could be a share class we hold).

**What changes in the gate's output, for the rows currently seen [V]:**
- 58 rows leave `events`/`unresolved` and appear under `bond_rows`. No other event
  changes (the old and new parsers agree on all other rows, apart from the new
  `saw` field on unresolved rows; the 24 `skipped_malformed` rows are the same in both).
- Real blocking on the recorded sessions (distinct action ids, from the private plan
  copies, feed as read today): core 11-03 3→2, 11-04 3→2, 11-05 5→4; C4 11-04 0→0,
  11-05 2→2. In each core session the one row removed is db0847b7.
- Measured against every session's window, flat book (the same measure as the
  17-of-23 figure in the C4 book json, reproduced exactly on today's read): **core
  and C4 alike, 17 of 23 sessions refused → 15 of 23 (2026-10-01..11-02), and 4 of 5
  → 4 of 5 (11-03..11-09)** [V]. The fix removes the bond rows. All 22 rows that still
  block a flat book over 10-01..11-09 hold a CUSIP-format value (§3) [V].
- In report mode (both books now), sends are unaffected. Nothing here changes
  what trades.

## 2. The three rows, for the team lead to rule on

Ids in the plan records and the feed agree on all three. All feed facts are the row
as Alpaca served it on 2026-11-08 [V]. "Ours" means the 13 core or 74 C4 funds, read
from the frozen specs through `spec_params` [V].

### db0847b7-9523-4b2f-afba-ae51ddb77ec5: partial call on a bond (ISIN)

- **Event.** `partial_call`, `symbol` `USU67540AA98`, `cusip` `U67540AA9`; record
  2026-10-21, lottery 2026-10-22, payable and process 2026-10-30, `price` 1000
  (the feed's figure, as it gives it) [V: feed]. A sibling row `c1d17316` is the
  same bond, processed 2026-10-15 [V: feed].
- **Security.** The bond is the Reg S tranche of Office Properties Income
  Intermediate Holdco II Trust's 8.375% Senior Secured Limited OPI Guaranteed Notes
  due 2029: OpenFIGI maps the ISIN to `OFF PPTYS INC INT HCO II`, `OPI 8.375 12/31/29
  REGS`, security type EURO-DOLLAR, market sector Corp [V: OpenFIGI, 2026-11-08];
  JPMorgan Trust II's N-MFP3 filed 2026-09-08 lists CUSIP `U67540AA9` as a corporate
  debt collateral issue of `OFFICE PROPERTIES INC`, coupon 8.375, maturity
  2029-12-31 [V: EDGAR]; OPI's EX-4.1 of 2026-09-24 names the notes
  (`New Intermediate Holdco 2029 Secured Notes`) [V: EDGAR].
- **Whether the call itself is announced.** I did not find an SEC notice of this
  particular partial call: EDGAR full-text search on the CUSIP returned only the
  N-MFP3 holdings, and OPI's 8-K of 2026-09-24 is about the new 8.75% notes, not this
  call [U]. The row is the only source for the event; the security's identity is [V].
- **Could it be ours?** No. Its one party is a bond ISIN; `U67540AA9` is not one of the
  88 CUSIPs of our 87 funds [V], and an alphabetic issue code cannot be a CEF's
  common share (§1).
- **After the fix.** Resolved: the row moves to `bond_rows` and blocks nothing [V].
- **Recommended ruling: NO ACTION** (no ca-ack needed once the fix ships).

### e34ddd44-1ed2-4b30-b668-be3f16e11dce: SNTI's contingent value rights (CVR)

- **Event.** `spin_off`, `source_symbol` SNTI (`source_cusip` 816944102),
  `new_symbol` and `new_cusip` `816CVR021`, 1 new for 1 old, ex-date and record
  2026-10-30, payable and process 2026-11-02 [V: feed].
- **What it is.** Senti Biosciences' distribution of contingent value rights: the
  board fixed 2026-10-30 as the record date for the CVR distribution, in connection
  with the 2026-10-21 closing of the merger with ST NewCo Limited [V: 8-K filed
  2026-10-27, accession 0001628280-26-067624]. One CVR per share of common stock; the
  CVRs "are not certificated, will not have any voting or dividend rights ... and will
  not be transferable except in limited circumstances" [V: 8-K filed 2026-10-26,
  accession 0001140361-26-040772]. Alpaca models it as a 1-for-1 spin-off with no
  ticker. `816CVR021` has no OpenFIGI mapping; `816944102` maps to SNTI common [V].
- **Could it be ours?** No. SNTI is in neither universe [V]; `816CVR021` is not one
  of our 88 CUSIPs [V]; and the "new" security is a non-transferable contractual
  right, not a fund share.
- **After the fix.** **Still unresolved**: `816CVR021` is a CUSIP-format value, not
  an ISIN, and this fix does not classify CUSIPs. Treated as each of our names in the
  `new` role on the long window, it blocks held names whose window reaches 10-30
  (on the core's record of 2026-11-05 it still blocks) [V].
- **Recommended ruling: ACK** with `ca-ack`, in **both** books' state dirs on the VM,
  when the gate returns to `halt`: `python3 -m quantt.session ca-ack --book cef --id
  e34ddd44-1ed2-4b30-b668-be3f16e11dce --reason "<one line>"` and the same with
  `--book c4`. Reason: a non-transferable CVR of a non-universe company; no fund's
  share count can move on it. KEEP-BLOCKING would refuse the session for nothing;
  no action would leave it blocking every session a held name's window reaches back
  to 10-30 (under `halt` nothing trades, so the window never moves past it).

### 6abeb209-f747-4bf3-a231-67b8c0984d4a: JAGX Series R conversion

- **Event.** `stock_merger`, `acquiree_symbol` and `acquiree_cusip` `47010C847`,
  `acquirer_symbol` JAGX (`acquirer_cusip` 47010C854), `acquiree_rate` 1,
  `acquirer_rate` 5, effective, payable and process 2026-11-02 [V: feed].
- **What it is.** Jaguar Health's Series R Convertible Preferred converted into common
  at 5:1 on 2026-11-02: "each of the then outstanding shares of Series R Preferred
  Stock automatically converted into five shares of Common Stock", leaving 13,345,986
  shares outstanding [V: 8-K filed 2026-11-03, accession 0001193125-26-445055].
  Alpaca's `47010C847` is the Series R: the feed's JAGX spin-off row `3656d534` issues
  it 1-for-1 with record 2026-10-13, payable 2026-10-15, ex 2026-10-16, which are the
  dates Jaguar reports for the Series R dividend [V: 8-K filed 2026-10-28, accession
  0001193125-26-436334]. No filing fetched quotes the CUSIP itself, so that it is the
  Series R is by this match of dates and ratio [U]. Alpaca models the conversion as a
  merger; it is Jaguar's own securities on both sides. `47010C847` has no OpenFIGI
  mapping; `47010C854` maps to JAGX common [V].
- **Could it be ours?** No. JAGX is in neither universe [V]; `47010C847` is not one of
  our 88 CUSIPs [V].
- **After the fix.** **Still unresolved**: a CUSIP-format acquiree, not an ISIN.
  Judged as each of our names in the `acquiree` role (long window), it blocks held
  names whose window reaches 11-02 [V].
- **Recommended ruling: ACK** with `ca-ack`, both books' state dirs on the VM
  (`--book cef` and `--book c4`, id above). Reason: a conversion between Jaguar's own
  securities; no fund's share count can move on it.

## 3. What still stands between these rulings and `halt`

> *Corrected 2026-11-09: item 1 below is what was open on 2026-11-08. The team lead has
> since ruled, and the CUSIP check is built (§5). Item 3 still stands; §5 lists what
> remains now.*

1. **The CUSIP-format rows, by far the largest item.** The fix classifies bonds by
   ISIN only. The other two rows above are CUSIP-format, and so is every other row
   that still blocks a flat book over 10-01..11-09 (22 rows in all) [V]. On today's read, a flat book would still be refused on 15 of the
   23 sessions in 10-01..11-02 and 4 of 5 in 11-03..11-09 [V]; the next-session rows
   include the worthless removals `0147191d` and `0d1c6887` (`929CNT012`, `929CNT020`,
   process date 2026-11-05) and the name change `2babc616` (`ELMES` → `939ESC075`,
   process date 2026-11-06, blocking a flat book on 11-06 and 11-09). The feed
   carries 66 still-unresolved rows dated 2026-07-01..11-20 (market date, else process
   date), in 18 of about 20 weeks: about three a week [V].
   Under `halt` each one that lands in a held name's window refuses the session until
   someone acknowledges it, row by row.
   **This needs a team-lead ruling before the halt release**; the ISIN fix does not
   address it. A CUSIP in a party field cannot be told from one of our funds' CUSIPs at
   run time, because the live path holds no CUSIP table (`_ca_read` docstring); a
   per-row ack keeps that judgement with the team lead, at about three rows a week.
   Option, not built: fetch the universe's CUSIPs at run time from Alpaca's dividend
   rows (the measurement in §1 does this), and read a CUSIP-format party that is not
   one of them as naming nobody, recorded like a bond row. That is a new, separate
   change with its own ruling.
   Also relevant to any such rule [V]: `_ca_symbol` reads a **letter-led** CUSIP as a
   ticker (14 fields in the read, e.g. `G29CVR019`, `M26CNT069`): it reaches the
   parser as a present party named nothing of ours, while a **digit-led** CUSIP is
   read as a missing party that could be any of ours.
2. **The two acks above**, per book (`ca_acks.json` is per book; state dirs on the
   VM). They're needed only once `halt` is back (report mode refuses nothing). `ca-ack`
   needs a recorded session and the row still in the feed [V: `run.ca_ack_main`].
3. **A release** carrying this fix, and in the same commit the book json `mode` and
   the two pins that hold it at `report`
   (`test_the_deployed_book_sets_report_until_the_unresolved_rows_are_re_ruled` for the
   core, and the C4 twin in `test_c4_ca_unresolved.py`). That is the separate step after
   the rulings; this branch does not touch it.
4. **An `ack_mismatch` trap to know about:** an ack holds only while the row is
   unchanged [V: `corp_actions` ACKNOWLEDGEMENTS]. Alpaca may yet complete these rows;
   a revised row blocks again and needs a new ack.

## 4. Final table: one row per item, the ruling, and what the code now does

Rulings: team lead, 2026-11-09, "Accept all three" (`docs/SYSTEM.md` §5).

| item | event | parties, identifiers | could be ours? | after the ISIN fix | after the CUSIP check, table PROVED | ruling (team lead, 2026-11-09) |
|---|---|---|---|---|---|---|
| **db0847b7-9523-4b2f-afba-ae51ddb77ec5** | partial call, process 2026-10-30, Office Properties Holdco II 8.375% 2029 Reg S [V] | `symbol` USU67540AA98 (ISIN), `cusip` U67540AA9 [V] | No: a bond; not one of the 88 fund CUSIPs [V] | Resolved: `bond_rows`, blocks nothing [V] | Resolved, as before [V] | **Accepted: no action** |
| **e34ddd44-1ed2-4b30-b668-be3f16e11dce** | spin-off of non-transferable CVRs, ex 2026-10-30, payable 2026-11-02 [V] | SNTI (source, 816944102); `new_symbol`/`new_cusip` 816CVR021 [V] | No: SNTI not in either universe; 816CVR021 not a fund CUSIP [V] | Still unresolved (a CUSIP, not an ISIN) [V] | Proved foreign: `foreign_cusip_rows`, blocks nothing [V] | **Accepted: ack with `ca-ack`, core and C4, at the return to `halt`.** While the table is PROVED the row is not an event, so `ca-ack` refuses it and it blocks nothing: the ack is needed only on a day the table cannot be proved. |
| **6abeb209-f747-4bf3-a231-67b8c0984d4a** | stock merger: JAGX Series R converts to common 5:1, effective 2026-11-02 [V] | JAGX (acquirer, 47010C854); `acquiree_symbol`/`acquiree_cusip` 47010C847 [V; that it is the Series R is by match of dates and ratio, U] | No: JAGX not in either universe; 47010C847 not a fund CUSIP [V] | Still unresolved (a CUSIP, not an ISIN) [V] | Proved foreign: `foreign_cusip_rows`, blocks nothing [V] | **Accepted: ack with `ca-ack`, core and C4, at the return to `halt`.** As for e34ddd44 |

## 5. The CUSIP check (team lead, 2026-11-09, "Build a check against our CUSIPs")

`alpaca._CaCusipTable`. At run time, when a CUSIP-format party appears, the gate reads every
CUSIP seen for every fund of the book's universe across the last 731 days (the fund's
cash-dividend rows and every non-dividend row naming it). **A CUSIP-format party leaves
`unresolved` only on proof it is none of ours**: the table read in full with a CUSIP for
every fund, no split, reorganisation or CUSIP change left unconfirmed, the row dated inside
the table's coverage, the value corroborated by a CUSIP field of its own row, and nothing
on the row (a party ticker, a CUSIP field, a shared six-character issuer base) naming one
of ours. It is then recorded under `foreign_cusip_rows` and blocks nothing. Anything else
stays unresolved, naming the fund and the reason in `saw`; a party matching a CUSIP of ours,
a superseded one included, also names that fund, and the row cannot block less than it did.
Digit-led and letter-led CUSIPs take this one path. **The two rulings it depends on are the
team lead's; the design choices that follow are this session's, listed so they can be challenged:**
the 731-day lookback (it must exceed the longest gap between a fund's dividend rows, 374 days
measured [V]); the issuer-base guard (a new CUSIP after a reverse split keeps its base [V for
IGR and JAGX]); and the corroboration and coverage conditions.

**What the table cannot see [U].** A CUSIP change with a new issuer base, unlisted by Alpaca,
inside the gap since the fund's last dividend row. The table holds all it has seen and
Alpaca is its only source.

**Measured [V]** (`results/ops/ca_unresolved_2026-11-08/measure.py`, the feed as read
2026-11-09). The table is PROVED for both books: 13 funds and 13 CUSIPs for the core, 74
funds and 75 CUSIPs for C4 (IGR's two). No fund's change is unconfirmed: the one split in
the lookback, IGR's, names both CUSIPs. The real read takes about 1 to 4 seconds. On the
3,643 rows over process dates 2025-11-01 → 2028-11-09: 58 rows are bonds, 162 are proved
foreign CUSIP rows, 2 stay unresolved (§ below), the 24 malformed rows are unchanged, and
no row was added or changed in the gate's events.

Sessions `halt` would have refused, **2026-10-01..11-09 (28 sessions)**, the table as read
today, not as each past session could have read it:

| book | before any fix | ISIN fix only | ISIN fix + CUSIP check |
|---|---|---|---|
| flat core | 21 of 28 [V] | 19 of 28 [V] | **0 of 28** [V] |
| flat C4 | 21 of 28 [V] | 19 of 28 [V] | **0 of 28** [V] |
| core as actually held (from its own account's closed orders) | 25 of 28 [V] | 25 of 28 [V] | **5 of 28** (10-01 to 10-07 only) [V] |
| C4 as actually held | 2 blocking on 11-05 [V, recorded]; 3 on 11-06, 4 on 11-09 [upper bound, §] | 2, 3, 3 | **0 on 11-04 and 11-05 [V, recorded]; 0 on 11-06 and 11-09** [upper bound, §] |

C4's held figures for 11-06 and 11-09 are upper bounds on 11-05's held windows: C4's keys are
not on this machine, so its account could not be read; its windows on those days can only be
narrower. C4 first traded on 11-04 (`results/report/data/live/c4/verify.csv`), and its gate
records start there.

The 5 core sessions that remain, and the only rows still unresolved anywhere in the read,
are 3afd31c6 and 70f6398e: worthless removals dated 2026-09-28 whose party is an
exchange-suffixed code, `NOEA:XETR` and `NOEA:XTER`, neither a ticker, an ISIN nor a CUSIP [V].
They stayed in the core's held windows until the windows passed them on 10-07 [V]. Nothing blocks
a held or flat book on 11-09 [V]. A new row of that shape would stay unresolved and need
`ca-ack`, as the 2026-11-02 ruling says.

**What still stands between this and `halt`:** a review and release of this branch, which
sets both books' `mode` back to `halt` and updates the two pins in the same commit (§3,
item 3). The table read adds a few seconds, inside the late-market send's time budget; a
read that stalls is the same class of risk as the gate's own read. Under `halt`, a day the
table cannot be proved is a day every CUSIP-format row inside a held name's window refuses
the session, naming why (`cusip_table` in the record).

*Added 2026-11-09, after the team lead's answers (`docs/SYSTEM.md` §5): "Halt in tonight's
release", and the acks for e34ddd44 and 6abeb209 are dropped unless needed. Commit 1aab61d
sets both books' `mode` to `halt` and moves the two pins. Against a clear feed the session's
output is unchanged byte for byte apart from the gate's mode string (the re-derived pins in
`quantt/session/tests/test_panels_noop.py` and `src/deploy/tests/test_level_signal.py`).*

*Added 2026-11-09, after the release-check on dd2c084 returned NO-GO. Four defects in the table,
all reproduced on a fake session and fixed at 4a3cf51, each with a test that fails on dd2c084:
a renamed fund's old CUSIP was never held, so a row quoting only it was proved foreign; an
unreadable field on a CUSIP row raised out of the read, so only a release could clear it; a
list-valued party on another lookback row turned the table off; and a repeated page token
made 1,000 GETs. Re-measured after the fix, the feed as read that evening [V]: the table is
PROVED with 13 funds and 13 CUSIPs for the core and 74 and 75 for C4, unchanged, so no fund
of ours carries a rename the table had missed; a flat book is refused on 0 of 28 sessions
and the core as held on 5 (10-01 to 10-07); the reads took 1.22 s and 1.61 s from the laptop.
The columns before the fix moved by one since the morning's read (22 and 20, were 21 and 19);
the cause was not examined [U]. **A consequence the first draft understated:** "a day the
table cannot be proved" lasts as long as its cause. A failed read lasts that read, but one
fund row with no CUSIP keeps the table unproved until the row leaves the lookback, up to
about two years, and each row it refuses in that time needs `ca-ack`. None exists today.*
