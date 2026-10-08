# Security

This skill makes Claude browse the open web, read smart contracts and write a report about real people and companies. The main risks are untrusted content steering the agent, accidental onchain actions, leaking secrets or the user's identity, unsafe HTML in the published page, and unfair claims about third parties. This file lists what the skill does about each.

## Threat model and mitigations

| Risk | Mitigation | Where |
|---|---|---|
| Prompt injection from websites, docs, repos, token metadata, X posts | Everything fetched is data; agents quote injection attempts instead of acting on them | `references/agent-brief.md`, `references/DD-PROCESS.md` sections 0 and 11 |
| Accidental transactions or key exposure | Onchain access is read-only (`cast call/code/storage`, local `anvil` forks); never `cast send`, never sign, never handle a funded key | `agent-brief.md`, DD-PROCESS section 11 |
| Running a project's malicious code | Agents read cloned repos but do not run install scripts, tests, build hooks or binaries | `agent-brief.md` |
| Leaking the user's identity | No contact headers, form fields or sign-ups; generic User-Agent | `agent-brief.md`, `scripts/x_sentiment.py` |
| API key leaks | `XAI_API_KEY` is read from the git-ignored workspace `.env` or the environment, passed to curl through a 0600 temporary header file (not argv), never printed or written to evidence | `scripts/x_sentiment.py`, `.gitignore` |
| XSS in the published page (project names, taglines, links come from the web) | All text HTML-escaped; links must be absolute http(s) URLs (`javascript:`, `data:`, relative URLs are dropped); logo must be a plain file name inside `assets/`; SVG logos are either reduced to path data or embedded as `<img>` (scripts in SVG do not run there) | `scripts/build.py`, `scripts/ddlib.py`, tests in `tests/test_scripts.py` |
| Path traversal through slugs, handles or file names | Slugs `^[a-z0-9][a-z0-9-]{0,63}$`, X handles `^[A-Za-z0-9_]{1,15}$`, asset names validated before any file is touched | `scripts/ddlib.py`, `scripts/new_project.py`, `scripts/x_*.py` |
| Bypassing bot protection or paywalls | Not allowed; use another source and note it | DD-PROCESS section 11 |
| Unfair or defamatory wording | Verified fact, inference and allegation kept apart; court outcomes only as "reported"; no legal names for pseudonymous people; never "scam"; reports private by default | DD-PROCESS section 11, QA checklist section 6 |

## Residual risks (read before use)

- `charts.py` in a project folder is **executed** by `build.py`. Only build projects whose `charts.py` you or the skill wrote, and review it if it came from someone else.
- The Grok pass sends search terms (project name, handles) to xAI. Nothing about the user is sent, but the query itself reveals interest in the project.
- The published page loads Google Fonts (a request to Google). Remove the `<link>` in `shell_head()` if that matters to you.
- A report is an opinion based on evidence at a date. It can be wrong; the footer says "not investment advice".
- Research agents can still make mistakes. The lead cross-check (step 5) exists because of that; do not skip it.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting on this repository (Security tab, "Report a vulnerability"). Do not open a public issue for security problems.
