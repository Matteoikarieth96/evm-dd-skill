# Acme Vaults: Due Diligence Report

**Project:** Acme Vaults (https://acme-vaults.example) | **Sector:** DeFi yield vaults | **Chain:** fictional | **Angle:** investor | **As of:** 2026-10-08
**Final rating: 4.8 / 10** (simple average of 8 categories, average confidence Medium) | **Verdict: WATCH, do not back yet**

This is a **fictional example**: the project, people, numbers and sources are invented to show the format. Evidence base: `sources/01` to `06`, `sources/09-crosscheck.md`. Numbers marked *verified* were reproduced from the primary source or onchain; numbers marked *claimed* come from the website. Not investment advice.

---

## TL;DR

1. Acme Vaults runs curated USDC vaults and keeps a 10% performance fee on the yield.
2. Verified deposits are $41.2M from 2,310 wallets, fourth of seven direct peers.
3. The homepage claims $120M because it counts reward tokens at list price.
4. A 2-of-3 Safe can upgrade the vault instantly; the deployed code differs from the audited commit.
5. Rating 4.8, WATCH: a timelock and a second audit would move it up.

---

# Page 1: Overview and business

## What it is

Depositors put USDC into an ERC-4626 vault; a curator allocates it to lending markets and the protocol keeps 10% of the yield.

## How the money flows (verified)

Deposits sit in the vault proxy; yield accrues to share price; the fee is minted as shares to the treasury Safe at each harvest.

## Key metrics: claimed versus verified

| Metric | Claimed | Verified | Source and date |
|---|---|---|---|
| TVL | $120M | $41.2M deposits | `totalAssets()`, 2026-10-08 |
| Users | "5,000+" | 2,310 wallets | explorer holders, 2026-10-08 |

## Weekly deposits

Deposits rose during the points boost and fell 35% after it ended.

---

# Page 2: Technology, legal, team

## Technology and security (M1)

The vault is verified and audited once. The ProxyAdmin owner is a 2-of-3 Safe with no timelock: a simulated `upgradeAndCall` from the Safe succeeds, from a random address it reverts. The admin-key cap applies.

## Legal and regulatory (M2)

The ToS names Acme Vaults Ltd; no registry entry was found (n/d). No licence is claimed. The ToS excludes US persons but the app does not geoblock.

## Team (M4)

| Person | Role | Background | Verified how |
|---|---|---|---|
| Founder A (fictional) | CEO | Former DeFi BD lead | Public profile |
| Founder B (fictional) | CTO | Former vault engineer | GitHub history |

---

# Page 3: Market, traction, community, risks, verdict

## Market, peers and relative valuation (M7)

| Peer | Tier | Chain | Token | Mcap | FDV | TVL | Revenue (annualised) | Mcap/TVL | vs project |
|---|---|---|---|---|---|---|---|---|---|
| Peer A | A | EVM | yes | $310M | $620M | $900M | n/d | 0.34 | 22x larger |
| Peer B | A | Solana | yes | $95M | n/d | $210M | n/d | 0.45 | 5x larger |
| Peer C | B | Move | none | n/a | n/a | $60M | n/d | n/a | 1.5x larger |

Illustrative band if tokenised: $12M to $22M, not a price target.

## Risk register

| Risk | Likelihood | Impact | Why |
|---|---|---|---|
| Malicious or mistaken upgrade | Low | High | No timelock over user funds |
| Deposit flight after boosts | Medium | Medium | -35% after the last boost |

## Key questions for the team

1. When will the ProxyAdmin move behind a timelock?
2. Why does the deployed code differ from the audited commit?

## Investor verdict: WATCH, do not back yet

A real but small fee business with fixable control risks.

---

# Scorecard

| # | Category | Score | Confidence | Rationale |
|---|---|---|---|---|
| M1 | Technology and security | **4.0** | High | Admin-key cap (about 5.5 without it) |
| M2 | Legal and regulatory | **3.5** | Medium | No registry entry, no licence, unenforced ToS |
| M3 | Business model and economics | **5.0** | Medium | Real fee income, modest |
| M4 | Team | **6.0** | High | Doxxed, relevant track record |
| M5 | Traction and metrics | **5.5** | High | Verified deposits, falling after boost |
| M6 | Tokenomics and governance | **4.5** | Medium | No token, opaque points |
| M7 | Market, peers and valuation | **5.0** | Medium | Crowded category |
| M8 | Community and X sentiment | **5.2** | Low | Free reach pass only |
| | **Final rating (average)** | **4.8 / 10** | Medium | (4.0 + 3.5 + 5.0 + 6.0 + 5.5 + 4.5 + 5.0 + 5.2) / 8 |

Caps applied: M1 capped at 4.
