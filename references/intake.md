# Intake questions (evm-dd)

Ask these before any research. Use the `AskUserQuestion` tool when the host has it (at most 4 questions per call, 2 to 4 options each, recommended option first), otherwise a short numbered list in plain text. Ask in the user's language. Skip anything the user already said. Two rounds at most, then summarise and wait for a yes.

## Round 1 (always)

| # | Question | Options | Why it matters | Default if skipped |
|---|---|---|---|---|
| 1 | How deep should the DD go? | **Full** (5 parallel agents, cross-check, report + 1-pager, typically 30 to 60 min) / **Quick scan** (one pass, 1-pager only, confidence marked Low) / **Report only** (full research, no 1-pager) | Sets cost, time and how many agents run | Full |
| 2 | X sentiment pass? | **Free reach-only** (fxtwitter, no key) / **Paid Grok pass** (about $4 to $15, needs `XAI_API_KEY`) / **Skip** | The paid pass is the only way to classify mention sentiment; it costs money | Free reach-only when no key is configured, otherwise ask |
| 3 | What do you want at the end? | **Private web page + A4 PDF** / **PDF only** / **Local HTML only** | Decides whether to publish an artifact | Private web page + PDF |
| 4 | Whose angle? | **Investor** (back / watch / avoid) / **User** (is it safe to deposit or use?) / **Partner** (should we integrate or list it?) | Changes the verdict wording and the emphasis of the risk register; the rubric stays the same | Investor |

## Round 2 (only what is still unknown)

- **Project and links.** Name, website, and any docs, X, GitHub, explorer or contract links the user already has. Why: the official channels anchor everything; impersonators exist.
- **Known leads or worries.** Anything the user has heard (a rumour, an incident, a token unlock). Why: leads go into every agent brief and get checked, not repeated.
- **Conflicts of interest.** Does the user hold the token, invest in or work with the team or a competitor? Why: it is disclosed in the report footer and keeps the user's own posts out of the sentiment sample.
- **Deadline and language.** Default: no deadline, English.
- **Workspace.** Where projects live (`EVM_DD_HOME`, default `~/evm-dd`). Ask before creating it.

## Summary to confirm

> I will run a {depth} due diligence on {Name} ({url}) from the {angle} angle, with {X option}. Output: {output}. Known leads: {leads or none}. Conflicts: {none / disclosed}. Estimated time {t} and paid API cost {cost}. OK to start?

Start only after a clear yes.
