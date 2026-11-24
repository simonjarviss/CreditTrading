# Which broker can replace Alpaca for a Canadian-resident book — 2026-10-28

**Read-only research; no account opened, nothing traded.** The team lead asked for the best broker, because
IBKR is hard to use for systematic trading. Their answers: the account holder is a **Canadian resident**,
the broker should **replace Alpaca entirely**, and the book trades **paper only for now**. Every source
was read on 2026-10-28. [V] means fetched and read; [S] means named, not read; [U] means unconfirmed. There
is no reproducer script: the sources are web pages, listed in `docs/REFERENCES.md` §12bk.

## The answer

1. **IBKR Canada is the only candidate that meets every hard requirement**: Canadian eligibility, API
   order placement for a personal account, closing- and opening-auction orders (MOC, LOC, MOO, LOO), and
   short selling with a borrow flag and pre-borrow.
2. **Alpaca live is not open to Canadian residents.** "Alpaca Clearing & Custody Canada Ltd. is not yet a
   CIRO Dealer Member" [V, alpaca.markets/ca/disclosures]. **Real capital cannot go to Alpaca today**,
   whatever the paper plan. Re-check each quarter.
3. **No broker open to a Canadian was found whose paper account processes corporate actions.** IBKR
   paper: "certain corporate actions like dividends and splits won't be processed" [V, IBKR Campus]. Alpaca
   paper: none [V, staff replies; `docs/REFERENCES.md` §12pc]. Moving paper accounts does not fix the
   corporate-action gap. The book and the event sleeves must apply corporate actions in their own ledger,
   from an independent source.

## Eliminated, and why

| candidate | fails on | source |
|---|---|---|
| Questrade | API trading: "If you are a Questrade partner developer, you can also use the API to place trades." Personal apps get data only | [V] questrade.com/api/documentation/getting-started |
| Moomoo Canada (Futu OpenAPI) | US auction orders: AUCTION and AUCTION_LIMIT are "Valid for HK stocks early and closing auctions only". Paper allows limit and market only | [V] openapi.futunn.com/futu-api-doc/en/trade/trade.html |
| Alpaca live | Canadian eligibility: the entity is not yet a CIRO Dealer Member | [V] alpaca.markets/ca/disclosures |
| Tradier | lists Canada among the countries where it "CANNOT open accounts" | [S] support.tradier.com permitted-and-blocked-countries |
| Webull Canada | no OpenAPI for Canadian accounts was found | [U] |
| TradeStation, tastytrade, Lightspeed, Cobra, CenterPoint Canada | Canadian eligibility is absent, withdrawn or unconfirmed | [S/U], see the research agent's table in this session |
| TradeZero Canada | its API places only Market, Limit, Stop and StopLimit, so no MOC | [S] developer.tradezero.com |
| Lime | the API fits (on-open and on-close orders), but Canadian eligibility is unconfirmed | [U] |
| Canadian banks and discount brokers | no public trading API found | [U] |

## IBKR Canada: what it costs to run unattended [S unless marked]

- **Headless operation is the weak point.**
  - **IB Gateway** restarts itself daily, but needs a human 2FA re-login each week.
  - **IBC**, the open-source auto-login tool, was archived on 2026-09-01; ib-gateway-docker is still
    maintained.
  - The **Client Portal Web API** needs a browser login every day, and IBKR "does not support an automated
    authentication process".
  - **OAuth (fully headless)** is offered to advisors, brokers, proprietary trading groups and funds, **not
    individuals**. An entity account could apply.
- **Costs:** US stocks USD 0.0035 per share tiered (USD 0.35 minimum) or USD 0.005 fixed (USD 1 minimum).
  The US snapshot data bundle is USD 10 a month, waived above USD 30 of commissions.
- **Margin:** IBKR Canada applies CIRO margin, 50% on stocks at or above CAD 2.
- **Rule 3200:** API orders are barred for Canadian-listed securities only. US-listed names are unaffected.

## Team lead, 2026-10-28

Recorded in `docs/SYSTEM.md` §5.
- **Real capital waits for Alpaca Canada.** IBKR was not chosen.
- **Paper stays on Alpaca.**
- **E1 is parked until real capital.**
- **Re-check Alpaca's Canadian status each quarter:** CIRO membership, and whether the trading API,
  closing-auction (`cls`) orders, short selling and paper are offered to Canadian retail.
