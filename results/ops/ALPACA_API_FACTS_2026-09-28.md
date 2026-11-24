# Alpaca API facts for the runner — fetched 2026-09-28

**Why this file exists.** `docs/RUNNER.md` builds the order path on Alpaca facts, and
`CLAUDE.md` forbids recalled figures. Every fact below was read on a page fetched on
2026-09-28 (raw markdown of `docs.alpaca.markets/us/...` pages, which embed the OpenAPI
definitions; `alpaca.markets/support` and `alpaca.markets/learn` HTML; Discourse JSON for
forum threads). Nothing here was sent to Alpaca: no order, no key, no network call to the
trading API.

Labels: **[V]** read now on an Alpaca-owned page (key phrase quoted); **[S]** a forum
post (staff marked), or an Alpaca page older than its claim may still hold; **[U]** not
found in any source, or sources disagree. A [U] item is a question for the paper
probes (`docs/ROADMAP.md` phase 3), never a default in code.

Page dates (`updatedAt` in the fetched markdown): Placing Orders 2026-08-10, User
Protection 2026-09-16, Paper Trading 2026-07-07, Market Data FAQ 2026-09-21, About
Market Data 2026-07-16, Working with /orders 2026-08-18, Get Account 2026-05-27.

---

## 0. Findings that change the RUNNER.md design — read these first

1. **`cls` may be gated behind Elite Smart Router.** Alpaca Learn: *"Please note that
   OPG and CLS orders are only available to Elite Smart Router users."* The Placing
   Orders TIF table marks CLS for market/limit orders `Yes*`, where *"Please contact the
   sales team for any TIF marked with a \*"*. Neither page says whether **paper**
   enforces this. The account is not Elite as far as anything in the repo shows. **[V]
   that the statement exists; [U] whether paper rejects `cls` for us.** This is roadmap
   3.1, and it is a go/no-go for "Order type stays MOC". If paper rejects `cls`,
   `POST /v2/orders` should return an error and the runner must fail the session. It
   must never re-send as `day`.
2. **A long→short flip as two `cls` orders in one session will probably be rejected.**
   Learn "Insufficient qty" (403): *"When you submit a sell order ... the shares tied to
   that order are reserved until the order is filled or canceled"*, and *"you hold 100
   shares long and submit a sell order for 200 shares ... Alpaca does not support holding
   long and short positions in the same symbol at the same time ... confirm the long
   position is fully closed before submitting a new order to open a short position."*
   Staff (forum, 2023): *"The first order to 'sell' just to get the position to 0, and a
   second 'sell short' for the remaining shares. Alpaca currently doesn't support
   creating two orders like that."* A `cls` close only fills at 16:00, so the long is not
   closed when the second sell arrives. **[V] for the reservation rule and the advice;
   [S] for the staff statement; [U] whether `position_intent=sell_to_open` changes it.**
   RUNNER.md's "a flip split into two orders" should become: **close today, open the
   other side at the next session**, unless a paper probe shows otherwise. The team lead
   has to decide this.
3. **`/v2/clock.is_open` means "open right now", not "a trading day".** Gate 4 ("market
   is open today") should use `/v2/calendar?start=<today>&end=<today>`: a row for today
   means today is a trading day, and its `close` is the close. [V]
4. **The `cls` cutoff on early-close days is not documented.** Alpaca documents only
   3:50pm ET. [U]. RUNNER.md's "calendar close minus 10 minutes" is our own margin, not
   an Alpaca rule.

---

## 1. Trading API — endpoints, auth, fields

### Base URL and auth
- Paper Trading API host `paper-api.alpaca.markets`; market data `data.alpaca.markets`.
  *"If you have a paper account, you can call: Trading API endpoints on
  `paper-api.alpaca.markets` / Market Data API endpoints on `data.alpaca.markets`"*. [V]
  <https://docs.alpaca.markets/us/docs/authentication>
- Every Trading API reference page lists servers `Paper: https://paper-api.alpaca.markets`
  and `Live: https://api.alpaca.markets`. [V] (e.g. <https://docs.alpaca.markets/us/reference/getaccount-1>)
- Auth headers `APCA-API-KEY-ID` and `APCA-API-SECRET-KEY` (the "Legacy" flow). HTTP
  Basic auth is the alternative. The OAuth client-credentials flow *"is not yet
  available for Trading API"*. [V] <https://docs.alpaca.markets/us/docs/authentication>
- Keys are per account: *"you cannot use your live account's credentials with the paper
  API"*. Deleting a paper account and creating a new one needs new keys. [V] (same page;
  <https://docs.alpaca.markets/us/docs/paper-trading>)

### GET /v2/account — every numeric field is a **string**
<https://docs.alpaca.markets/us/reference/getaccount-1>. Schema `required: [id, status]`,
so every other field may be absent and the client must raise if one is missing. [V]

| field | type | doc text (quoted) |
|---|---|---|
| `equity` | string | "Cash + long_market_value + short_market_value" |
| `last_equity` | string | "Equity as of previous trading day at 16:00:00 ET" |
| `buying_power` | string | "If multiplier = 4, this is your daytrade buying power which is calculated as (last_equity - (last) maintenance_margin) * 4; If multiplier = 2, buying_power = max(equity - initial_margin,0) * 2; If multiplier = 1, buying_power = cash" |
| `regt_buying_power` | string | "Your buying power under Regulation T (your excess equity - equity minus margin value - times your margin multiplier)" |
| `multiplier` | string | "valid values 1 ..., 2 (reg T margin account ...), 4 (PDT account with 4x intraday buying power and 2x reg T overnight buying power)" |
| `shorting_enabled` | boolean | "whether or not the account is permitted to short" |
| `trading_blocked` | boolean | "If true, the account is not allowed to place orders." |
| `account_blocked` | boolean | "If true, the account activity by user is prohibited." |
| `trade_suspended_by_user` | boolean | "If true, the account is not allowed to place orders." |
| `short_market_value` | string | "Real-time MtM value of all short positions" (the equity formula adds it, so it is negative for shorts [inferred]) |
| `status` | enum string | ACTIVE, ... |

The equity formula implies `short_market_value` is ≤ 0 for a short book. That is
inferred, not stated. [U]

### GET /v2/positions
<https://docs.alpaca.markets/us/reference/getallopenpositions>. All numeric fields are
strings. `required` includes `symbol, qty, side, avg_entry_price, market_value,
current_price, lastday_price, asset_marginable`. [V]
- `side`: enum `long | short`. [V]
- `qty`: "The number of shares" (string). **The docs do not say whether `qty` is
  negative for a short.** [U] Read `side` and treat `qty` defensively: take the sign
  from `side`, and raise if `qty` has the opposite sign.
- `qty_available`: "Total number of shares available minus open orders". [V]
- `avg_entry_price`: "Average entry price of the position"; `current_price`: "Current
  asset price per share"; `lastday_price`: "based on the closing value of the last
  trading day". [V]

### GET /v2/orders
<https://docs.alpaca.markets/us/reference/getallorders-1> [V]
- `status`: `open | closed | all`. *"Defaults to open."*
- `limit`: *"Defaults to 50 and max is 500."*
- `after` / `until`: *"submitted after this timestamp (exclusive)"* / *"submitted until
  this timestamp (exclusive)"*.
- `direction`: `asc | desc`, *"Defaults to desc"*. `nested`: roll up multi-leg orders.
  `symbols`: comma-separated list. `side`: filter.
- `before_order_id` / `after_order_id`: *"Do not combine with `after`/`until`."*
- There is no page token. A day with more than 500 orders needs time-windowed
  paging. Our book sends a few dozen at most.

### POST /v2/orders
<https://docs.alpaca.markets/us/reference/postorder> [V]
- Body `required: [type, time_in_force]`. `symbol` and `side` are required for
  non-`mleg` orders. `qty` is a **string** ("number of shares to trade").
- `time_in_force` enum includes `cls`. `type` is `market`.
- `client_order_id`: *"A unique identifier for the order. Automatically generated if not
  sent. (<= 128 characters)"*. **The allowed character set is not documented.** [U] Our
  `cef-YYYYMMDD-SYMBOL-leg` format uses `[a-z0-9A-Z-]` and is 128 characters or fewer,
  which should be safe but is unverified.
- `position_intent`: enum `buy_to_open | buy_to_close | sell_to_open | sell_to_close`,
  *"Represents the desired position strategy."* It exists for equities, but its effect
  on the flip rule and on paper is undocumented. [U]
- `extended_hours` only works with limit orders and `day`/`gtc`. Leave it unset. [V]
- Responses: **403** *"Buying power or shares is not sufficient."* **422** *"Input
  parameters are not recognized."* [V]
- The response is an `Order` object: `id` (uuid), `client_order_id`, `status`, `symbol`,
  `side`, `qty`, `filled_qty`, `filled_avg_price` (string|null), `filled_at`,
  `submitted_at`, `time_in_force`, `type`, `position_intent`, `expires_at`. [V]

### GET /v2/orders:by_client_order_id
`?client_order_id=<id>` (query, required). *"Retrieves a single order specified by the
client order ID."* [V] <https://docs.alpaca.markets/us/reference/getorderbyclientorderid>
- The endpoint does not say which order it returns when an id was reused after the
  first order became inactive. [U]

### GET /v2/clock
<https://docs.alpaca.markets/us/reference/legacyclock> [V]. Fields: `timestamp`,
`is_open` (*"Whether or not the market is open."*), `next_open`, `next_close`. All are
RFC-3339 with offset (example `"2025-06-24T16:00:00-04:00"`). There is a newer
`GET /v3/clock?markets=...`, which the runner does not need.

### GET /v2/calendar
<https://docs.alpaca.markets/us/reference/legacycalendar> [V]
- Params `start`, `end` (inclusive), `date_type` = `TRADING` (default) or `SETTLEMENT`.
- Row fields (all required): `date` (YYYY-MM-DD), `open` and `close` (*"HH:MM format"*),
  `session_open` and `session_close` (*"HHMM format"*), `settlement_date`.
- *"the response also contains the specific open and close times for the market days,
  taking into account early closures."* Covers *"1970 to 2029"*. The timezone of
  `open`/`close` is not stated. Presumably ET. [U]

### GET /v2/assets/{symbol_or_asset_id}
<https://docs.alpaca.markets/us/reference/get-v2-assets-symbol_or_asset_id> [V]
- `required`: `id, class, exchange, symbol, name, status, tradable, marginable,
  shortable, fractionable`, all booleans except the strings. 404 if not found.
- `borrow_status`: enum `easy_to_borrow | hard_to_borrow`. This is the documented field.
- `easy_to_borrow` (boolean) appears in the doc's **example** but not in the schema
  properties. Our own probe on 2026-09-28 received both `borrow_status` and
  `easy_to_borrow` (AWF: `"borrow_status": "easy_to_borrow", "easy_to_borrow": true`).
  Code should key on `shortable` and `borrow_status` (documented) and raise if they are
  absent. [V doc + V repo probe]
- `margin_requirement_long/short` are decimal strings. `maintenance_margin_requirement`
  is deprecated. [V]

### GET /v2/account/activities and /v2/account/activities/FILL
<https://docs.alpaca.markets/us/reference/getaccountactivities-2>,
<https://docs.alpaca.markets/us/reference/getaccountactivitiesbyactivitytype-1> [V]
- Params: `activity_types` (comma list; the generic endpoint only), `category`
  (`trade_activity|non_trade_activity`), `order_id`, `date` (*"Filter activities by their
  creation date (created_at), not the activity's settlement date"*), `until`, `after`,
  `direction` (default `desc`), `page_size` (default 100, **max 100**), `page_token`
  (*"the ID of the last activity from the last page"*).
- FILL record fields: `activity_type` ("FILL"), `id` (`"<ts>::<uuid>"`, used as a page
  token), `order_id`, `symbol`, `side` (*"buy or sell"*), `qty`, `cum_qty`, `leaves_qty`,
  `price` (*"The per-share price that the trade was executed at"*), `transaction_time`,
  `type` (`fill|partial_fill`), `order_status`. Numbers are strings. The schema has no
  `required` list. [V]
- Fees show up as activity_type `FEE` with sub-types `REG`, `TAF`, `CAT` and others.
  Dividends are `DIV`. [V]

---

## 2. Order rules

- **`cls` definition and cutoff**: *"This order is eligible to execute only in the market
  closing auction. Any unfilled orders after the close will be cancelled. CLS orders
  submitted after 3:50pm but before 7:00pm ET will be rejected. CLS orders submitted
  after 7:00pm will be queued and routed to the following day's closing auction."* Also,
  *"On open/on close orders are routed to the primary exchange."* [V]
  <https://docs.alpaca.markets/us/docs/orders-at-alpaca>
  - **Implication**: a `cls` order sent after 19:00 ET is *queued for the next day's
    close*. A runner firing late (for example a retry after midnight) still produces a
    live MOC order. Gate 4 must refuse outside the [session open, 15:45] window. It must
    not rely on Alpaca rejecting the order.
- **`cls` availability**: see §0.1 (Elite-only statement). [V statement / U effect on paper]
  <https://alpaca.markets/learn/13-order-types-you-should-know-about>
- **Early-close cutoff**: not documented. [U]
- **Cancel**: *"An order may be canceled through the API up until the point it reaches a
  state of either `filled`, `canceled`, or `expired`."* DELETE returns 204, or 422 *"The
  order status is not cancelable."* Neither page gives a `cls`-specific cancel deadline.
  [V for the general rule; U for the `cls` cancel cutoff. NYSE's own MOC cancel rule is
  not Alpaca's and was not fetched here.]
  <https://docs.alpaca.markets/us/reference/deleteorderbyorderid-1>
- **Replace (PATCH)**: allowed fields include `qty` ("You can only patch full shares")
  and `time_in_force` (enum includes `cls`). *"Order cannot be replaced when the status is
  `accepted`, `pending_new`, `pending_cancel` or `pending_replace`."* The page states no
  `cls`-specific restriction. [V] <https://docs.alpaca.markets/us/reference/patchorderbyorderid-1>.
  The runner never replaces orders.
- **`client_order_id` uniqueness**: the API reference says only "A unique identifier".
  Alpaca Learn: *"it likely means a duplicate client_order_id was used for another
  active order ... `{"code":40010001,"message":"client_order_id must be unique"}` (HTTP
  422) ... Make sure to use a unique client_order_id for each active order."* [V that
  the uniqueness check applies among active orders; U whether reuse after fill or cancel
  is accepted. The Learn wording implies it is, but no page says so.]
  <https://alpaca.markets/learn/how-to-fix-common-trading-api-errors-at-alpaca>
- **Wash-trade rule** (403): *"If we detect a possible wash trade, we reject the order
  and send back an error message with the HTTP status code 403 (Forbidden)."* The table
  says `market buy` existing + `market sell` new is *"always rejected"*, and so is
  `market sell` + `market buy`. It lists order types, not TIF, so a `cls` market order
  is presumably a "market" order for this purpose. [V; the cls mapping is U]. *"Our wash
  trade protection also applies to your paper trading account."* [V]
  <https://docs.alpaca.markets/us/docs/user-protection>
  - **Same-side second order** (for example a pending sell-to-close plus a new
    sell-short): the wash table does not cover it (both are sells). It is governed
    instead by the **qty-reservation / no-boxed-position** rule in §0.2, which probably
    rejects it (403 "insufficient qty"). [V rule / U exact outcome for `cls`]
  - Staff (2023): with 0 shares, a buy then a sell is rejected with *"cannot have a
    short sell order open at the same time as a long buy"*. With 100 shares, a sell of
    150 is rejected with *"insufficient quantity available"*. [S]
    <https://forum.alpaca.markets/t/simultaneous-buy-and-sell-orders/11992>
- **One sell crossing long→0→short**: *"Right now you cannot flip position side in one
  order. You need to flatten the position first."* (staff, 2020) [S]
  <https://forum.alpaca.markets/t/can-i-flip-my-position-from-short-to-long/1738>.
  Confirmed in spirit by Alpaca Learn §0.2. [V]
- **A second same-side order in a symbol while one is open**: allowed if quantity is
  available. For sells, the reserved shares count against it (Learn: *"While that order
  is still open, you submit another sell order for the same 10 shares ... The second
  request is rejected"*). [V] Our design sends one netted order per symbol, which avoids
  this.
- **Buying power check on orders**: *"Alpaca applies a buying power check to both long
  buys and short sells ... For market short orders, the value is simply (3% above the
  current ask price) \* order quantity ... your available buying power is reduced by
  existing open buy long and sell short orders. Your sell long and buy to cover orders do
  not replenish your available buying power until they are executed."* [V]
  <https://docs.alpaca.markets/us/docs/orders-at-alpaca>. The exposure gate must model
  the short leg at ask × 1.03, and must not count the pending closes as freeing buying
  power.
- **Short sales**: *"In order to trade on margin or sell short, you must have $2,000 or
  more account equity."* ETB: *"$0 locate and borrow fees on all ETB shares for Trading
  API users."* HTB: *"requires an approved locate before a short-sale order can be
  submitted"*. `hard_to_borrow`: *"A locate is strictly required before opening a short
  position."* The locate endpoints are *"not available in paper trading"*. [V]
  <https://docs.alpaca.markets/us/docs/margin-and-short-selling>,
  <https://docs.alpaca.markets/us/llms.txt>. Behaviour of an HTB short on **paper** (where
  locates don't exist) is [U]. The gate should refuse `borrow_status != easy_to_borrow`
  as well as `shortable != true` (a team-lead decision; RUNNER.md gate 7 checks only
  `shortable`).
- **Maintenance margin, shorts**: *"SHORT share price >= $5.00: Greater of $5.00/share
  or 30%"*. *"SHORT share price < $5.00: Greater of $2.50/share or 100%"*. Initial margin
  is 50% for marginable securities. [V] (same page)
- **Equity/order ratio**: *"Alpaca will restrict the account to closing transactions
  when an account has a position that is 600% larger than the equity"*. [V]
  <https://docs.alpaca.markets/us/docs/user-protection>
- **Rate limit (Trading API)**: *"the API is throttled, currently 200 requests per
  minute, per account ... a '429- Too Many Requests' status will be returned"* (support
  page dated December 2022). [S, because the page is old but first-party]
  <https://alpaca.markets/support/usage-limit-api-calls>. The reference pages document
  429 and the headers `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
  (*"The UNIX epoch when the remaining quota changes"*). [V]
  <https://docs.alpaca.markets/us/reference/legacyclock>
- **HTTP codes**: 403 = buying power/shares insufficient (POST orders), wash trade (User
  Protection), or an account permission / insufficient-qty problem (Learn). 422 = input
  not recognized, `client_order_id must be unique`, order not cancelable. 429 = rate
  limit. 404 = asset not found. [V]

---

## 3. Market Data API

- Base URL `https://data.alpaca.markets/{version}`. [V]
  <https://docs.alpaca.markets/docs/historical-api>. Same key headers. [V]
  <https://docs.alpaca.markets/us/docs/about-market-data-api>
- **Basic (free) plan**: *"Real-time market coverage: IEX"*, *"Historical data
  limitation\*: latest 15 minutes"*, *"Historical API calls: 200 / min"*, history *"Since
  2016"*. [V] (same page). FAQ: *"For historical queries, the `end` parameter must be at
  least 15 minutes old to query SIP data without a subscription."* The error is
  `{"code":42210000,"message":"subscription does not permit querying recent SIP data"}`.
  [V] <https://docs.alpaca.markets/us/docs/market-data-faq>
- The Paper Trading page says *"As an Alpaca Paper Only Account holder, you are only
  entitled to receive and make use of IEX market data."* The FAQ says SIP history older
  than 15 minutes is free. These two statements pull in different directions. Whether
  our paper key can read SIP auctions/bars older than 15 minutes is [U] until probed.
  <https://docs.alpaca.markets/us/docs/paper-trading>
  **Probed 2026-09-28 19:50 ET [V]:** yes, with explicit timestamps. `start=end=<date>`
  returns HTTP 403 *"subscription does not permit querying recent SIP data"* even hours
  after the close (the bare-date window runs up to now). `start=<date>T04:00:00Z`,
  `end=<date>T20:30:00Z` returned closing prints for all 13 names on 2026-09-25 and
  2026-09-28. NYSE (`N`) prints at `M` and `6` were equal on the two names inspected
  (PDI 13.90, MHD 10.27 on 09-28); the `N`/`M` prints matched the yfinance closes in
  `data/cef/cef_prices.parquet` within half a cent on all 26 name-days.
- **GET /v2/stocks/auctions** [V] <https://docs.alpaca.markets/us/reference/stockauctions-1>
  - Params: `symbols` (required, comma list), `start`, `end` (inclusive, RFC-3339 or
    YYYY-MM-DD), `limit` (default 1000, max 10000, *"applies to the total number of data
    points, not per symbol"*), `asof`, `feed` (*"Only `sip` is valid for auctions."*),
    `currency`, `page_token`, `sort`.
  - Response: `{"auctions": {SYM: [ {d, o:[...], c:[...]} ]}, "next_page_token"}`. Per
    day: `d` date, `o` opening auctions, `c` closing auctions (*"Every price / exchange /
    condition triplet is only shown once, with its earliest timestamp."*). Each print has
    `t` (ts), `x` (exchange code), `p` (price, number), `s` (size, optional), and `c`
    (condition, a single string).
  - The example shows **several closing prints per day from different exchanges** (x=P
    and x=Q, conditions `6` and `M`, prices 138.36 vs 138.34). Condition codes (FAQ
    table): `M` = *"Market Center Official Close"*, `6` = *"Market Center Closing
    Trade"*, `Q` = *"Market Center Official Open"*, `O` = *"Market Center Opening
    Trade"*. [V]
  - **Selecting "the official closing auction print"** needs the primary listing
    exchange's code (the asset's `exchange`, e.g. `NYSE`, mapped to the SIP exchange
    code) and condition `M` or `6`. The mapping (`/v2/stocks/meta/exchanges`) was not
    fetched. Whether to use `M` or `6` is a design decision. [U]
- **GET /v2/stocks/bars** [V] <https://docs.alpaca.markets/us/reference/stockbars>
  - `timeframe=1Day`. `adjustment`: `raw` (default) | `split` | `dividend` | `spin-off`
    | `all`, comma-combinable. `feed`: `iex | otc | sip | boats`. `limit` max 10000.
    Pagination is via `next_page_token`. Bar fields are `t, o, h, l, c, v, n, vw`.
  - **Default `feed` conflicts between sources**: the reference schema says
    `"default": "sip"`; the FAQ says *"The default value for `feed` is always the 'best'
    available feed based on the user's subscription"* (IEX on Basic). Always pass
    `feed` explicitly. [U which default applies]
  - The daily bar close is updated by condition `6` (closing trade) but not by `M`
    (official close) (FAQ table). A daily-bar `c` is therefore not guaranteed to equal
    the official close. [V]

---

## 4. Paper-trading specifics

- *"the system simulates the order filling based on the real-time quotes"*. *"all
  orders submitted in paper trading will be matched against the best available current
  market price (NBBO)"*. Paper does not account for *"Regulatory fees"* or *"Dividends"*.
  Borrow fees: *"⛔️ (Coming Soon!)"*. *"When orders are eligible to be filled, they
  will receive partial fills for a random size 10% of the time."* *"Your order quantity
  is not checked against the NBBO quantities."* [V]
  <https://docs.alpaca.markets/us/docs/paper-trading>
- MOC on paper, staff (2021-05-18): *"Currently, paper trading doesn't simulate MOO and
  MOC order prices. It treats those orders as regular market orders which simulate
  prices using the bid and ask (ie buy orders fill at the ask and sell orders fill at
  the bid)."* Staff (2023-01-24): *"paper trading doesn't differentiate Market On Open
  (MOO) and Market On Close (MOC) orders."* Neither post says when (at what time) a paper
  `cls` order fills. [S]
  <https://forum.alpaca.markets/t/accurate-opg-and-cls-prices-for-paper-trading/3762>,
  <https://forum.alpaca.markets/t/opening-and-closing-market-prices-in-paper-trading/11664>
  - **Implication for verify.py**: a paper `cls` fill can be a *partial fill* (random
    10%), so reconcile must handle `partially_filled` / `leaves_qty > 0`. It must not
    assume full fills.
- **PDT**: the Account schema still describes `multiplier=4` as "PDT account". Alpaca's
  page on FINRA's new intraday margin rule says the legacy "$25,000" and "four trades in
  five days" framework is being replaced. Our probe on 2026-09-28 got no
  `daytrade_count` / `pattern_day_trader` fields back. The runner does not day-trade (at
  most one MOC order per symbol per day), so this is low risk. Whether paper still
  enforces a PDT check is [U].
  <https://docs.alpaca.markets/us/docs/understanding-finras-new-intraday-margin-rule-and-the-end-of-pdt>
- **FILL activities for `cls` orders on paper**: no page says so either way. [U]
  (roadmap 3.5). Paper does not simulate dividends, so no `DIV` records are expected.
  Whether paper emits `FEE` records is [U]. The docs say regulatory fees are not
  accounted for. **Corrected 2026-11-08: it does.** The cef paper account shows 37 FEE
  activities (SEC and CAT) over 2026-09-29..10-30 [V:
  `results/cef/LIVE_ATTRIBUTION_2026-11-02.md`].

---

## 5. Open questions (for paper probes or the team lead)

1. Does the paper account accept `time_in_force=cls` without Elite? (If not, MOC is
   impossible and the order-type rule needs a team-lead decision.)
2. With a pending `cls` sell-to-close for the full long, is a second `cls` sell (short)
   rejected, and with what message? Does `position_intent` change that? Until this is
   answered, design flips as close today, open tomorrow.
3. The `cls` submission cutoff on early-close days (Alpaca documents only 3:50pm).
4. Is `client_order_id` reusable after the first order is filled or canceled? What
   characters are allowed?
5. Is `positions[].qty` negative for shorts?
6. When and at what price does a paper `cls` fill happen (at submit, or near 16:00)?
   Does it produce a FILL activity?
7. Can the Basic-plan paper key read `feed=sip` auctions and daily bars older than 15
   minutes (FAQ says yes; Paper page says "only IEX")? **Answered 2026-09-28: yes for auctions, with timestamp
   start/end (see above) [V].**
8. Which exchange code and condition (`M` vs `6`) define "the official closing auction
   print" for NYSE-listed CEFs? This needs `/v2/stocks/meta/exchanges`.
9. Can HTB names be shorted on paper (locates are unavailable on paper)?
10. Timezone of `/v2/calendar` `open`/`close`.
