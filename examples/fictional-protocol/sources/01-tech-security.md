# M1 Technology and security (fictional)
As of: 2026-10-08
## Findings
- Vault proxy 0x1111...1111 is an ERC-4626 vault behind a transparent proxy; implementation verified on the explorer [confidence: H] (https://explorer.example/address/0x1111111111111111111111111111111111111111, accessed 2026-10-08)
- ProxyAdmin owner is a 2-of-3 Safe with no modules, no guard and no timelock [confidence: H] (https://explorer.example/address/0x2222222222222222222222222222222222222222, accessed 2026-10-08)
- `cast call --from <Safe>` of `upgradeAndCall` succeeds; the same call from a random address reverts: the Safe can upgrade user funds' contract instantly [confidence: H] (local simulation, 2026-10-08)
- One audit (fictional firm, 2026-06), 0 critical, 2 high fixed; the deployed code is 140 lines larger than the audited commit [confidence: M] (https://audits.example/acme-vaults-2026.pdf, accessed 2026-10-08)
## Open questions / not verifiable
- Bug bounty: n/d
## Red flags
- Instant upgrade path over user funds (admin-key cap applies)
