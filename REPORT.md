# AI Customer Support Agent for AmazonHelp — Report

## 1. Problem Framing

### What "good" means for this brand

AmazonHelp handles an extremely heterogeneous volume of support requests — delivery
delays, product defects, refund disputes, billing questions, account access, Prime
membership, and a large volume of messages that are not really support requests at
all (compliments, sarcasm, social chatter, off-topic content pulled in by thread
reconstruction). Given this, "good" for this system means three specific things:

1. **Correctly separating messages that need a human from messages that don't**,
   with a strong bias toward precision on the auto-handle side. A wrongly
   auto-handled ticket (e.g. a customer with a genuinely lost package told to
   "wait a bit longer") is worse than an unnecessary escalation. This is why the
   evaluation explicitly weights auto-handle precision alongside accuracy.
2. **Grounding replies in real historical resolutions**, not generic templates,
   so that drafted replies reflect how this specific brand actually resolves
   specific issue types.
3. **Failing safely** — i.e., messages containing safety-relevant content (crisis
   language, abuse, PII) or falling outside the system's declared scope (non-English)
   must escalate regardless of what the intent classifier thinks, as a hard rule
   that sits above the rest of the routing logic.

### What I chose not to build

- **Multi-turn conversational drafting.** The system classifies and drafts a
  reply from the *first* customer message in a thread. It does not track
  conversation state across multiple back-and-forth turns, even though many real
  threads (see Failure Analysis) run 10-50+ messages. Building stateful
  multi-turn drafting was out of scope given time constraints.
- **Fine-tuned or embedding-based semantic retrieval.** After a local
  sentence-transformers install failed to import on the development machine
  (a persistent native crash, unresolved across three package versions) and a
  Gemini-embeddings approach hit a hard daily free-tier quota after ~1,000 calls,
  retrieval was rebuilt on TF-IDF cosine similarity. This is a real, disclosed
  scope reduction (see Decision Log and Limitations).
- **Full multilingual support.** The system is explicitly scoped to English.
  Non-English messages (~17% of the sampled data, consistent with the dataset's
  natural language mix) are detected heuristically and force-escalated rather than
  processed.
- **Automated threshold learning.** The grounding-strength threshold used for
  routing was hand-calibrated against empirical data from the golden set, not
  learned via a proper train/validation split. With more time this would be a
  first candidate for a small logistic regression over multiple signals
  (intent, confidence, grounding strength) rather than a single hand-set
  threshold.

### Brand and taxonomy

**Brand: AmazonHelp**, selected from the full ~2.8M-tweet dataset using volume,
multi-turn engagement rate, and — critically — a **reply-diversity check** (unique
templates vs. total replies) to avoid picking a brand that just repeats a handful
of canned responses. AmazonHelp had the highest volume among high-diversity
candidates (82,555 threads; ~90% of replies normalized to unique templates once
mentions/numbers/URLs were stripped), meaning RAG grounding on its history has
real signal to work with, not one repeated script.

**Taxonomy (8 intents)**, derived iteratively from the brand's own data (not
imported from Banking77, which was explicitly kept out of the taxonomy source
per assignment rules):
`delivery_status_inquiry`, `order_issue`, `refund_return_request`,
`payment_billing_issue`, `account_access_issue`, `prime_membership_inquiry`,
`general_inquiry`, `complaint_no_action`.

The single most consequential taxonomy design decision was the **"venting + topic"
rule**: a frustrated message about a specific topic (e.g. "still don't have my
order!!") routes to that topic's intent, not to `complaint_no_action`.
`complaint_no_action` is reserved for messages with genuinely no identifiable
subject matter (e.g. "NOTHING YET. WOW"). This rule took several iterations to
get right — an early version of the bootstrapping classifier used to derive the
taxonomy repeatedly over-assigned `general_inquiry` (69% of the sample) or,
after a first fix, over-corrected into `complaint_no_action` (45% of the sample)
before the topic-vs-topicless distinction was made explicit and enforced.

---

## 2. Results vs. Baselines

All numbers below are computed by the same evaluation harness
(`scripts/08_evaluate.py`) against **60 of the 150 hand-labeled golden-set
examples** (evaluation was capped at 60 due to Gemini free-tier daily quota
limits on the classifier's `generateContent` calls; see Limitations).

| System | Intent Accuracy | Intent Macro F1 | Routing Accuracy | Auto-handle Precision | Auto-handle Recall |
|---|---|---|---|---|---|
| **Trivial** (always predict `delivery_status_inquiry` / always `escalate`) | 44.0% | 0.076 | **72.7%** | 0.0% | 0.0% |
| **Simple** (keyword rules, no LLM) | 38.0% | 0.257 | 30.0% | 27.5% | 95.1% |
| **My system** (LLM classifier + TF-IDF RAG + rule-based router) | **53.3%** | **0.346** | 65.0% | 50.0% | 19.0% |

**Intent classification: my system wins clearly.** 53.3% vs. 44% (trivial) vs. 38%
(simple keywords), and a much healthier macro F1 (0.346 vs. 0.076 / 0.257). The
LLM classifier is doing real work beyond what a majority-class guess or basic
keyword rules can do, particularly on categories requiring judgment about
ambiguous language (sarcasm, venting-with-topic, "prime" mentioned as an aside
vs. as the actual subject).

**Routing: my system loses to the trivial baseline on raw accuracy** — 65.0% vs.
72.7%. This is discussed at length in Section 4, since it is the most important,
least flattering, and most informative single result in this report. Auto-handle
precision (50%) is meaningfully better than the simple keyword baseline's 27.5%,
meaning when my system does choose to auto-handle, it is right about half the
time (vs. the keyword system's 1-in-4). But its low recall (19%) means it rarely
takes that chance, defaulting to escalate for the large majority of cases —
close to, but not quite as conservative as, the trivial "always escalate" baseline.

**Reply quality (LLM-as-judge, n=54 of 60 scored; 6 hit a rate limit):**

| Dimension | Judge score (avg /5) |
|---|---|
| Correctness/Groundedness | 4.57 |
| Tone | 4.41 |
| Completeness | 4.20 |
| Actionability | 4.57 |
| **Overall** | **4.44** |

**Judge-human agreement (n=15 independently hand-scored by me, blind to judge
scores before scoring):**

| Dimension | Mean absolute difference | Exact match | Within 1 point |
|---|---|---|---|
| Correctness | 0.47 | 60% | 93% |
| Tone | 0.47 | 53% | 100% |
| Completeness | 0.53 | 53% | 93% |
| Actionability | 0.60 | 53% | 87% |

My own independent average scores on the same 15-example subset (4.47–4.67
across dimensions) were comparable to or slightly higher than the judge's — so
the high aggregate judge scores do not appear to be pure judge leniency; they
partly reflect that this batch of drafted replies was genuinely decent quality
on the dimensions scored. That said, a known hallucination case (see Failure
Mode 1) happened to fall outside this 15-example subset and is not reflected in
either the judge or human-agreement numbers — a real gap in this sampling that
I flag explicitly rather than paper over.

---

## 3. Failure Analysis

### Failure Mode 1: Hallucinated specifics in drafted replies

**Example:** Customer: *"bummed that all of a sudden @115821 won't deliver my
#WWE2K18 deluxe game today that I pre-ordered in June."* Drafted reply: *"I've
checked your order #115821 and it's still in transit..."*

`@115821` is Amazon's own Twitter account handle, not an order number — the
model misread an @-mention as a specific order identifier and then claimed to
have "checked" it, which never happened. **Hypothesis:** the drafting prompt
does not explicitly instruct the model to avoid treating @-mentions as order/
account numbers, and the model's tendency toward confident, specific-sounding
language (encouraged by the "be concise, ground in the historical case" prompt)
produces a plausible-looking but false claim. This is a genuine correctness risk
in a production system: a customer could be told something specific and false
about their own order.

### Failure Mode 2: Routing accuracy is beaten by the trivial "always escalate" baseline

As shown in Section 2, my system's 65.0% routing accuracy is *lower* than a
system that does nothing intelligent at all and just always says "escalate"
(72.7%). **Hypothesis:** escalation is the majority class in the golden set
(109/150, 72.7%), so any system that occasionally attempts auto-handling incurs
real risk — every wrong auto-handle attempt is a accuracy loss relative to the
"always safe" baseline, and my system's grounding-based auto-handle attempts are
only right about half the time. This is the single most important, least
flattering result in this report, and it is discussed in depth in Section 4.

### Failure Mode 3: Payment and refund intents are systematically misclassified

`payment_billing_issue` scored 0% precision/recall (n=6) and `refund_return_request`
scored 0% precision/recall (n=3) in the 60-example evaluation. Looking at
specific cases — e.g. *"@AmazonHelp Dash button settings lists old prices... you
don't realise price has gone up until bought. Sneaky!"* (human-labeled
`payment_billing_issue`, classified as `general_inquiry`) — the classifier
appears to under-weight pricing/charge language when it's phrased as a
site-feature complaint rather than an explicit "I was charged" statement.
**Hypothesis:** the taxonomy's disambiguation rules for these two intents
require fairly explicit language ("refund", "charge", "billing"), and real
customer phrasing is often more oblique ("sneaky", "price went up") — a rule
tuned to be precise (avoiding false positives from delivery/order venting
bleeding into these categories) ended up too strict to catch the real variety
of phrasing for these two intents specifically. Given both categories had small
support (n=3-6) in this evaluation slice, this should be re-checked against the
full 150-label set before treating it as a firm conclusion, but the direction
of the error is consistent and worth further taxonomy refinement.

### Failure Mode 4: A likely false positive in the safety filter

Thread: *"I will never understand people who steal packages. To the person who
did that, I hope you enjoy the book and pumpkin seed crackers.
#disappointedinhumanity"* — flagged by the safety filter as "Severe abusive
language detected." Reading the message, there is no abuse here at all — it's
resigned sarcasm about package theft. **Hypothesis:** the keyword-based safety
filter's abuse-detection list likely matches on a word or phrase pattern present
in this message without adequate context-sensitivity (a plain keyword match
cannot distinguish "steal" used descriptively from actual directed abuse). This
is a real, disclosed limitation: a keyword-based safety filter trades false
negatives (missed real abuse, e.g. creative phrasing like "U idiot" which does
NOT appear on the trigger list) against false positives like this one, and
neither failure mode was fully eliminated.

### Failure Mode 5: Thread-reconstruction noise (missing openings, unrelated merges)

Several evaluated threads either (a) started mid-conversation with the actual
opening customer complaint missing entirely (e.g. thread reconstruction pulling
in only messages 7 onward of a longer exchange), or (b) merged in an entirely
unrelated tweet at the root (e.g. a cricket-highlights tweet from a different
customer sharing a reply-chain ancestor with a real support thread). **Hypothesis:**
the DFS-based thread reconstruction (walking `in_response_to_tweet_id` chains)
correctly follows the graph structure of the data but has no semantic check that
messages in a reconstructed "thread" are actually about the same topic or from
the expected participants — a structural correctness issue, not a logic bug. This
adds noise to both the RAG corpus and evaluation set that a smarter thread-boundary
heuristic (e.g. topic-similarity check between consecutive messages, or a time-gap
cutoff) could reduce.

---

## 4. What Is Misleading About My Headline Number

If I only reported "53.3% intent accuracy, 65% routing accuracy, 4.44/5 average
reply quality," a reader would reasonably conclude this system works
reasonably well. Several things complicate that picture:

1. **The routing accuracy number is beaten by doing nothing intelligent at all.**
   A system that always says "escalate" scores 72.7% on this exact same
   golden set — higher than my system's 65.0%. Raw routing accuracy is a
   genuinely misleading headline metric here because escalation is the
   majority class (73%): a system can score arbitrarily high by refusing to
   ever automate anything, which would be useless in practice despite a
   flattering accuracy number. The more honest metric is auto-handle precision
   (50%, real improvement over the 27.5% keyword baseline) weighed against how
   much genuine automation coverage that represents (recall of only 19% — the
   system rarely attempts it).

2. **Small evaluation samples substantially overstated performance.** I ran the
   same evaluation harness at n=13, 15, 30, and 60 examples as I incrementally
   expanded the sample (largely gated by free-tier API quota limits). Intent
   accuracy read 61.5% → 60.0% → 63.3% → **53.3%** as sample size grew, and the
   grounding-threshold separation between auto-handle and escalate examples
   (mean difference) shrank from 0.078 → 0.059 → 0.027 → **0.015** — nearly
   vanishing. Had I stopped at n=13-30 (which is a completely plausible amount
   of testing to do under time pressure), I would have reported meaningfully
   better numbers than what a larger, more representative sample shows. This is
   the single clearest piece of evidence in this whole project that small
   pilot evaluations can be actively misleading, not just noisy.

3. **Rare-intent metrics are statistically unreliable at this sample size.**
   `complaint_no_action`, `prime_membership_inquiry`, `refund_return_request`,
   and `payment_billing_issue` each have 0-6 examples in the 60-example
   evaluation slice. A single misclassification swings a rare class's F1 score
   by 15-33 percentage points. The reported **macro F1 (0.346)** gives these
   noisy small-sample classes equal weight to `delivery_status_inquiry`
   (n=19, F1=0.750), which is a legitimate way to surface weakness in
   under-served categories, but it is not a stable, precise number at this n —
   it should be read as directional, not exact.

4. **Reply-quality scores may partly reflect an easy evaluation subset.** The
   drafted-reply judge scores were computed on the same 60 examples used for
   intent/routing evaluation, most of which involve reasonably well-defined,
   common issue types (delivery delays, simple product questions). The one
   clear hallucination case identified in manual review (Failure Mode 1) did
   not fall into the 15-example human-agreement subset by chance, so the
   headline judge-human agreement numbers do not reflect that specific known
   failure at all.

5. **The RAG-retrieval technology itself is a downgrade from the original
   design**, switched from planned dense embeddings (sentence-transformers,
   then Gemini's embedding API) to TF-IDF cosine similarity after both earlier
   approaches failed for environment and quota reasons respectively. TF-IDF
   captures keyword/topic overlap well but misses paraphrase-level semantic
   similarity (e.g. "no clue where the shipment is" vs. "haven't received my
   order" won't match as strongly as they would with dense embeddings). The
   grounding-strength numbers throughout this report should be read with that
   ceiling in mind — a dense-embedding version of this same system would likely
   show a cleaner separation between auto-handle and escalate cases.

---

## 5. What I'd Do Next With One More Week

1. **Finish labelling and re-run the full evaluation.** 150 of 197 sampled
   golden-set examples are hand-labeled, but only 60 were run through the full
   evaluation pipeline due to daily API quota limits split across sessions.
   Completing all 150 (and ideally all 197) would substantially firm up the
   rare-intent metrics that are currently unreliable at n=0-6.
2. **Fix the payment/refund intent under-classification** (Failure Mode 3) by
   expanding the taxonomy's example set and disambiguation language for these
   two categories specifically, informed by the concrete misses surfaced here,
   then re-evaluate.
3. **Replace TF-IDF with a working dense-embedding retriever.** Given more time,
   I would resolve the sentence-transformers native-crash issue properly (likely
   a torch/DLL ABI conflict specific to this Windows environment) rather than
   working around it, or budget for a paid embeddings tier to avoid the daily
   free-quota wall that forced the TF-IDF pivot.
4. **Combine multiple routing signals into a learned model** instead of a
   single hand-calibrated grounding threshold. With the full 150-197 labeled
   examples, a simple logistic regression over intent, classifier confidence,
   and grounding strength would likely outperform the current single-threshold
   rule, and would let me report a properly held-out train/test split rather
   than calibrating and evaluating on overlapping data.
5. **Add a semantic thread-boundary check** to reduce the reconstruction noise
   identified in Failure Mode 5 (unrelated tweets merged into threads, missing
   opening messages).
6. **Widen the safety filter's abuse-detection beyond exact keyword matching**
   (e.g. a small classifier for abusive-language detection) to reduce both the
   false positive found here and the likely false negatives (creative
   phrasing like "U idiot" that doesn't match any listed keyword).
7. **Re-run the LLM-judge and human-agreement check on a larger, randomly
   re-sampled set** that specifically includes known hard cases (hallucination-
   prone examples, non-English slip-throughs, safety-filter edge cases) rather
   than a subset that happened to miss the one clear failure case found in
   manual review.

---

## 6. Decision Log

Non-obvious decisions made during this project, and why:

1. **Chose AmazonHelp over higher-scoring alternatives on volume alone** by
   adding a reply-diversity check (unique templates vs. total replies) to the
   brand-selection criteria — a brand with high volume but templated,
   repetitive replies would make RAG grounding trivial and uninformative.
2. **Explicitly excluded Banking77 from taxonomy derivation**, using it only as
   a stated optional aid for classifier design, per the assignment's own
   guidance that Banking77 is a different domain (banking, not e-commerce/
   logistics) and using it as the taxonomy source would poison the
   brand-specific nature of the categories.
3. **Adopted a "venting + topic" rule for the taxonomy** after two rounds of
   the bootstrapping classifier over-assigning either `general_inquiry` (69%)
   or, after a naive fix, `complaint_no_action` (45%) — the fix required
   distinguishing topic-present venting from truly topic-less venting, not
   just moving the dump-bucket from one label to another.
4. **Deliberately oversampled rare intents** (`account_access_issue`,
   `complaint_no_action`, `prime_membership_inquiry`) in the golden-set
   sampling strategy, accepting that the golden set's class distribution would
   not match the natural ~1-3% base rate of these categories, and explicitly
   noting this trade-off rather than treating aggregate accuracy as fully
   representative of production performance.
5. **Enforced a hard, code-level golden-set exclusion assertion** in the RAG
   corpus-building step (`build_corpus` raises `AssertionError` if any
   golden-set thread ID appears in the retrieval corpus) rather than relying
   on a code comment or manual check, since this is the single most important
   guarantee against silent evaluation leakage.
6. **Scoped the system to English-only**, force-escalating non-English
   messages via a heuristic language filter, after confirming during golden-set
   sampling that non-English content made up ~17% of the brand's real traffic —
   too large a share to silently ignore, too resource-intensive to properly
   support given the project's time budget.
7. **Added a dedicated pre-classification safety filter** (crisis language,
   threats, PII exposure, severe abuse) that forces escalation independent of
   the intent classifier or grounding score, after encountering a real message
   in the raw sample referencing a stalking/suicide-adjacent situation —
   treating safety escalation as a hard rule rather than something the
   taxonomy or LLM classifier should be trusted to catch reliably.
8. **Abandoned local sentence-transformers embeddings** after a persistent,
   unresolved native crash (`sentence_transformers.models` import failure)
   that survived three different package version attempts (2.2.2, 2.7.0, 2.4.0)
   with no combination of torch/transformers/huggingface-hub versions resolving
   it on this Windows environment.
9. **Abandoned Gemini's embedding API as a fallback** after it hit a hard daily
   free-tier quota (1,000 requests/day) partway through building a planned
   5,000-entry RAG corpus, with no practical same-day workaround given the
   project deadline.
10. **Pivoted to TF-IDF cosine similarity for retrieval**, explicitly
    documenting this as a capability trade-off (keyword/topic overlap vs. true
    semantic similarity) rather than presenting it as equivalent to the
    originally planned dense-embedding approach.
11. **Empirically recalibrated the routing grounding-strength threshold**
    (from an initial default of 0.6, clearly miscalibrated for TF-IDF's lower
    typical similarity range, down to 0.34) using real grounding-strength
    distributions split by human-labeled routing decision, rather than
    guessing a new number — while explicitly noting that the separation
    between auto-handle and escalate groups weakened as sample size grew,
    meaning this single threshold is a moderate, not strong, signal.
12. **Used two different LLM providers for drafting vs. judging** (Groq for
    reply drafting, Gemini for both intent classification and the LLM-judge)
    specifically to reduce the risk of a model grading its own output
    favorably — a deliberate design choice, not an accident of API availability.
13. **Stopped hand-labelling at 150 of 197 sampled examples**, meeting the
    assignment's stated 150-250 minimum rather than completing the full
    stratified sample, as an explicit time-budget trade-off — noting that this
    likely reduces coverage of the deliberately oversampled rare intents
    relative to what the full 197 would have provided.
14. **Discovered and fixed a stale-cache bug producing empty drafted replies**
    (root cause: a reasoning-style Groq model consuming its entire token
    budget on internal reasoning before writing a visible reply, at an
    original `max_tokens=200` limit) by increasing the token budget to 600 and
    invalidating the affected cache before running the quality evaluation —
    catching this before judging avoided scoring broken output as low quality
    for the wrong reason.
15. **Ran the evaluation harness at increasing sample sizes (13 → 15 → 30 → 60)
    rather than treating the first successful run as final**, which is what
    surfaced the small-sample-inflation finding described in Section 4 — a
    result that would have been invisible had the project stopped at the first
    convenient evaluation size.

---

## Limitations Summary (Restated)

- RAG retrieval uses TF-IDF, not dense embeddings, due to unresolved local
  environment and API-quota constraints.
- Full evaluation was run on 60 of 150 labeled examples due to daily API quota
  limits on the intent classifier's free tier.
- The golden set (150 of 197 sampled threads) intentionally over-represents
  rare intents relative to their natural base rate.
- The safety filter is keyword-based and has both a confirmed false positive
  and likely false negatives for creatively-phrased abuse.
- The system does not track multi-turn conversation state; it classifies and
  drafts from the first customer message only.
