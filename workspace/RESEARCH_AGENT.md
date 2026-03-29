# Research Agent — Opportunity Scanner & Requirements Generator

## Trigger
Activate this pipeline when asked to "run research cycle", "start research",
"scan for opportunities", or any similar phrase.

## Time Budget
You have 1 hour total. At the start, record the time with:
  exec: date +%s
Store it as START_TIME. Check elapsed time periodically. Stop gracefully and
summarise what you did when 55 minutes have elapsed — do not start a new
opportunity if less than 5 minutes remain.

## Scoring Thresholds
Only generate requirements for opportunities scoring:
  Monetizability >= 7000 AND Feasibility >= 5000

## Lab DB API
All blocklist calls go to: http://192.0.2.99:8741
If the API is unreachable at any step, continue without it — never abort the cycle.

---

## Domain Verification Procedure

Use this exact procedure whenever a web_search or web_fetch call fails with any
of: bot-detection, CAPTCHA, 403, 429, rate-limit, access denied, or similar.

**DO NOT add a domain to the blocklist based on the tool error alone.**
Tool errors can be transient. Only block after confirming the domain is genuinely
refusing automated access by following these steps:

1. Extract the bare domain from the failing URL (e.g. `duckduckgo.com`).

2. Fetch the domain root directly:
     web_fetch("https://<domain>/")

3. Inspect the response body for real DOM content. A domain is GENUINELY BLOCKED
   if the response body contains ANY of:
   - A CAPTCHA widget or challenge page ("Verify you are human", "cf-challenge",
     "g-recaptcha", "hcaptcha", "please complete the security check")
   - A Cloudflare or similar interstitial ("Checking your browser",
     "Ray ID", "DDoS protection by Cloudflare")
   - An empty body, a 403/429 status code, or a connection refusal
   - Only JavaScript with no readable text content (JS-gate with no fallback)

   A domain is NOT blocked if the body contains readable text, navigation links,
   article titles, post content, or any substantive HTML — even if the earlier
   tool call failed. In that case, skip logging and retry the original search
   with a different query instead.

4. Only if the domain is GENUINELY BLOCKED per step 3, POST it:
     web_fetch("http://192.0.2.99:8741/blocked", {
       "method": "POST",
       "headers": {"Content-Type": "application/json"},
       "body": "{\"domain\": \"<domain>\", \"reason\": \"<specific evidence from step 3>\"}"
     })
   Use the actual evidence as the reason (e.g. "Root fetch returned Cloudflare
   challenge page with cf-challenge div — no readable content").

5. After confirming a block, skip that domain for the rest of this cycle.

---

## Step 0 — Load Blocked Domains

Fetch the active blocklist before running any searches:

  web_fetch("http://192.0.2.99:8741/blocked")

The response is a JSON array:
  [{"domain": "duckduckgo.com", "reason": "...", "hit_count": 2, ...}, ...]

Extract every `domain` value into a BLOCKED list. In every subsequent step,
before calling web_search or web_fetch on any URL, check if its domain is in
BLOCKED. If it is, skip that URL entirely without attempting the call.

---

## Step 1 — Know What Already Exists

Read the handoff folder to avoid regenerating docs for ideas already captured:
  exec: ls /shared/handoff/

For each .md file listed, read its first line (the H1 title) and keep a mental
list of existing topics. You will use this for deduplication in Step 4.

---

## Step 2 — Web Research

Use web_search and web_fetch extensively. Run ALL of the following searches.
Before fetching any result URL, check it against BLOCKED and skip if matched.

**Pain point discovery:**
- `site:reddit.com "I wish there was software" OR "nobody has built" 2025 2026`
- `site:reddit.com "no good tool for" OR "spreadsheet hack" OR "I have to manually"`
- `site:reddit.com/r/entrepreneur "pain point" OR "problem worth solving" software`
- `site:reddit.com/r/SaaS "frustrated with" OR "sick of" OR "hate that" tool`
- `site:reddit.com/r/startups "market gap" OR "underserved" software 2026`
- `"Ask HN" "why is there no" OR "why doesn't anyone" software tool site:news.ycombinator.com`
- `"willing to pay" software automation tool site:reddit.com`
- `"we built a spreadsheet" OR "we use email for" OR "manually track" small business software`

**Market signals:**
- `micro saas profitable niche underserved 2026`
- `developer tool pain point frustrating slow expensive 2026`
- `vertical saas opportunity 2026 small business`
- `AI software gap missing tool 2026`

For each promising result, use web_fetch to read the full page and extract
specific quotes, upvote counts, and evidence of willingness to pay.

**Failure handling during this step:**
If any web_search or web_fetch call fails, follow the **Domain Verification
Procedure** defined above before deciding whether to add it to the blocklist.

---

## Step 3 — Deep Dive on Top Signals

From Step 2, pick the 6 most promising pain points. For each, run 3 more searches:
1. `"<topic>" complaints problems users frustrated workaround`
2. `"<topic>" market size opportunity software 2024 2025`
3. `"<topic>" competitors alternatives review comparison`

Fetch the top 2 results of each search for full content.
Apply the **Domain Verification Procedure** for any failures encountered.

---

## Step 4 — Score and Filter

For each of the 6 candidates, reason through two scores:

**Monetizability (1-10,000)**
- 8,000+: crystal clear pain, people demonstrably pay for similar things, low competition
- 5,000-8,000: real pain but uncertain market or moderate competition
- <5,000: hobby niche, already well-served, no payment evidence

**Feasibility (1-10,000)**
- 7,000+: well-scoped, standard web/mobile stack, buildable in 4-12 weeks
- 4,000-7,000: achievable but complex
- <4,000: requires research, hardware, or massive datasets

Drop any candidate below Monetizability >= 7000 AND Feasibility >= 5000.

**Deduplication:** Compare each surviving candidate's topic against your list
from Step 1. If the idea is substantially similar to an existing doc, skip it.
Use semantic judgement — same core problem = duplicate, even if titled differently.

---

## Step 5 — Save Research Files

For each qualifying, non-duplicate candidate, write a research file:

  exec: mkdir -p /shared/research
  exec: date +%Y%m%d_%H%M

Path: /shared/research/<slug>_<YYYYMMDD_HHMM>.json

Content (JSON):
{
  "title": "Concise, specific product title",
  "problem": "2-3 sentences. Specific problem, who has it, current workaround.",
  "evidence": "Direct quotes, upvote counts, competitor gaps you found.",
  "sources": ["url1", "url2"],
  "monetizability": <integer>,
  "feasibility": <integer>,
  "reasoning": "One sentence explaining both scores.",
  "suggested_stack": "e.g. Python FastAPI, React, PostgreSQL, Railway"
}

---

## Step 6 — Generate Requirements Documents

For each research file saved, generate a full engineering requirements document
and write it to the handoff folder.

  exec: mkdir -p /shared/handoff

Path: /shared/handoff/<slug>_<YYYYMMDD_HHMM>.md

The document must contain these sections in order:

# Requirements: <title>

**Status:** Ready for Development
**Generated:** <date>
**Monetizability Score:** <score>/10,000
**Feasibility Score:** <score>/10,000

---

## Problem Statement
3-4 paragraphs: the specific problem, who has it, current workarounds, why
existing tools fail, why now is the right time.

## Target Users
2-3 specific personas. For each: role, pain, current solution, rough group size.

## Functional Requirements
Numbered list, "The system shall..." format. At least 10 requirements covering
the full core user loop.

## Non-Functional Requirements
Numbered list with specific numbers. Cover: performance, reliability, security,
scalability.

## Suggested Tech Stack
- **Frontend:** [tech] - [reason]
- **Backend:** [tech] - [reason]
- **Database:** [tech] - [reason]
- **Hosting:** [recommendation] - [reason]
- **Key Libraries/APIs:** [list with purpose]

## Scope Boundaries
### In Scope (v1)
### Out of Scope (v1)
### Future Phases

## Monetisation Strategy
2-3 concrete approaches with suggested price points.

## Acceptance Criteria
Checklist, at least 10 binary pass/fail items.
- [ ] <specific criterion>

## Key Risks
4-5 risks. Format: **Risk:** ... **Mitigation:** ...

---

## Wrap-Up

After all docs are written (or time runs out), write a summary to:
  /shared/research/cycle_log.md

Include: date/time, candidates found, how many qualified, docs generated,
which files were written, domains added to blocklist, any errors.

---

## Step 7 — Sync Blocklist

After the cycle, fetch the updated blocklist to confirm all failures were recorded:

  web_fetch("http://192.0.2.99:8741/blocked")

Log the total count of blocked domains in cycle_log.md.

To check a specific domain at any point:
  web_fetch("http://192.0.2.99:8741/blocked/<domain>")
  — Returns domain details if blocked (200), or not found (404 = safe to use)

To unblock a domain that is working again, this would need to be done manually
via: DELETE http://192.0.2.99:8741/blocked/<domain>
