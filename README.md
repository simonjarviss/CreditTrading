# CreditTrading

Systematic trading code for **Event Driven Trading**, a pod within QUANTT, the Queen's
University Algorithmic Network & Trading Team.

**Website: [event-driven.quantt.ca](https://event-driven.quantt.ca)**

[![checks](https://github.com/quanttqueensu/CreditTrading/actions/workflows/checks.yml/badge.svg)](https://github.com/quanttqueensu/CreditTrading/actions/workflows/checks.yml)

## Overview

The team runs three systematic books, managed as one portfolio:

| Book | What it trades |
|---|---|
| Fixed Income | Leveraged credit closed-end funds, long the widest discounts and short the richest, dollar-neutral |
| Equity Cross-Asset | Equity, preferred and multi-asset closed-end funds, on discount and relative-value signals |
| Event | Strategies around scheduled corporate events, from fund distributions to trust terminations |

Each book trades automatically every day on a paper account at Alpaca Markets. Live
results are on the website.

## Repository

| Path | Contents |
|---|---|
| [`quantt/`](quantt/) | The trading runner: decide, check, send and verify each session |
| [`src/deploy/`](src/deploy/) | The strategies |
| [`ops/`](ops/) | Frozen specs, book settings and operations tools |
| [`scripts/`](scripts/) | Research and data fetchers, never on the trading path |
| [`dashboard/`](dashboard/) | The website build |
| [`docs/`](docs/) | Documentation; [`docs/INDEX.md`](docs/INDEX.md) says which file answers what |

## Team members

- Setup: [`docs/ONBOARDING.md`](docs/ONBOARDING.md)
- Lanes, branches and pull requests: [`docs/TEAM.md`](docs/TEAM.md)
- How the system works: [`docs/SYSTEM.md`](docs/SYSTEM.md)
- The rules, for people and agents alike: [`CLAUDE.md`](CLAUDE.md)
- The current state of the books: `python3 -m ops.orient`

## Disclaimer

All results come from paper-trading accounts or backtests. No client or outside capital
is invested. Nothing in this repository is investment advice.
