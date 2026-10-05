# Safety Q&A: choosing the routing model

**Date:** 2026-10-05
**Command:** `cd backend && .venv/bin/python scripts/guidance_router_eval.py --model <model-id>`
**Question set:** `backend/tests/fixtures/guidance_router_eval.json`, 42 fixed questions:
29 that should match a reviewed entry and 13 that must be declined (predictions,
decisions, off-topic questions, a data question, a question about a specific fire, and
instruction-override attempts). Emergency wording is excluded because a deterministic
check handles it before any model is called.

**Bar (agreed in the design):** at least 90% first choice correct on the questions that
should match, at least 90% correctly declined, and no unavailable calls.

## Result

| Run | Model | First choice correct | Correctly declined | Wrong ids | Unavailable | Median latency | Against the bar |
|---|---|---|---|---|---|---|---|
| 1. First question set | `nvidia/nemotron-3-super-120b-a12b` | 28 of 29 (96.6%) | 13 of 13 (100.0%) | 0 | 0 | 446 ms | Meets it |
| 2. Independent question set | `nvidia/nemotron-3-super-120b-a12b` | 28 of 29 (96.6%) | 13 of 13 (100.0%) | 0 | 0 | 392 ms | Meets it |

**Why there are two runs.** A review of the first run found that 9 of the 29 questions that should
match were near copies (similarity of 0.8 or more) of questions and phrasings the router is already
shown, so they tested very little. Those nine were rewritten in different words, a test now fails
if any such near copy comes back, and the evaluation was run again. The result did not change.

No other model was compared: none was supplied, and the current model already meets the bar.

**The one miss, in both runs:** "Which way should the gas bottle valves face on a high-risk day?" returned
no id (it should have chosen `extreme-day-home`). That is a safe failure: the person sees the
fixed "no reviewed answer" message and the suggested questions, not a wrong answer. It was not rewritten
and no phrasing was added to catch it, because tuning the phrasings to the question set would stop the
set being independent.

## Decision

Keep `nvidia/nemotron-3-super-120b-a12b` as `DEFAULT_ROUTER_MODEL`. It is the model the
rendezvous explanation already uses, so no new provider or key is needed.

## What this result does not show

- It is one run per set over 42 sentences written by the team, with phrasings (`asked_as`) written by
  the same author. Real people will word things less tidily, so expect lower accuracy in use.
- The questions are in English and short. Longer, messier or non-English questions are untested.
- Nothing here measures how often a person is shown an answer that is correct but not the one
  they meant. The service shows at most two reviewed answers, and every id is checked against
  the reviewed list, so a wrong choice still shows correct advice for a neighbouring question.

## When to run it again

Run the script again, and record the result here, whenever the model, the prompt in
`backend/app/providers/nvidia_guidance_router.py`, the reviewed entries or their `asked_as`
phrasings change. Add real questions that were missed to the question set as they come up.
The key is read from `AI_API_KEY` or from that one line of `.env`; the hosted quota is shared
with the rendezvous explanation, so the script pauses between calls.
