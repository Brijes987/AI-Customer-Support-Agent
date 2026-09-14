# Classifier Architecture Decision

## Your Question

> Is this rule-based/keyword classification logic in 06_refine_taxonomy.py meant to be thrown away once we lock in the taxonomy definition, or is it becoming the actual production intent classifier?

## Answer: THROW IT AWAY

**This keyword logic is ONLY for taxonomy derivation**, not production classification.

### Why It Exists

**Purpose**: Bootstrap the taxonomy from raw data
- Cluster messages by keyword patterns
- Identify common issue types in the sample
- Generate example utterances per intent
- **Not** meant to be a production classifier

**Once taxonomy is confirmed**: This script's job is done.

---

## Production Classifier Architecture

### Recommended: LLM-Based Few-Shot Classification

**Why**:
1. **Zero training data needed** — just provide taxonomy + examples in prompt
2. **Handles variation** — understands paraphrasing, synonyms, context
3. **Free-tier viable** — Gemini Flash is fast + free
4. **Handles edge cases** — "wet parcel chucked over wall" doesn't need keyword rules

**Implementation**:
```python
# Gemini few-shot prompt
prompt = f"""
You are classifying customer support messages into intents.

Intents:
1. delivery_status_inquiry: Location/timing questions about delivery
   Examples: "Where is my package?", "When will it arrive?"

2. order_issue: Wrong/damaged/missing product
   Examples: "Received wrong item", "Package damaged"

... (all 8 intents)

Classify this message into ONE intent:
"{customer_message}"

Reply with ONLY the intent name.
"""
```

**Advantages**:
- No keyword engineering (your pain right now)
- Handles French/non-English gracefully (returns "unsupported" or classifies)
- Generalizes to unseen phrasings
- Can explain reasoning if needed

---

## Alternative: Trained Model (If LLM Not Viable)

**Only if**:
- LLM quota concerns (but Gemini Flash is very generous)
- Need offline/on-prem deployment
- Latency requirements (<100ms)

**Approach**: Fine-tune sentence-transformer + small classifier head
- Embed message with `all-MiniLM-L6-v2`
- Train logistic regression on golden set labels (150-250 examples)
- Fast inference, local

**Disadvantage**: Requires labeled training data (your golden set IS this)

---

## Recommendation for This Assignment

**Use LLM few-shot classification (Gemini)**

**Why**:
1. **Assignment focus is RAG + evaluation**, not classifier engineering
2. **Golden set is for evaluation**, not training
3. **Keyword rules are brittle** — you've seen this (wet parcel, Prime service, French, etc.)
4. **Gemini Flash free tier**: 15 requests/min, plenty for 150-250 eval examples
5. **Shows real-world approach** — most production systems use LLM classification now

---

## What Happens to 06_refine_taxonomy.py

**After taxonomy confirmation**:
1. ✅ **Keep**: The taxonomy JSON (intents, descriptions, examples)
2. ✅ **Keep**: The validation logic (as a test suite for golden set quality)
3. ❌ **Throw away**: The keyword classification logic
4. ❌ **Throw away**: All the pain of perfecting keyword rules

**Replace with**: 50-line Gemini few-shot classifier that uses the taxonomy JSON

---

## Implementation Plan (After Taxonomy Confirmed)

### Step 1: Lock Taxonomy (Now)
- Confirm 8 intents with clean examples
- Save as `golden_set/approved_taxonomy.json`

### Step 2: Build LLM Classifier (Next)
```python
# src/intent_classifier.py
import google.generativeai as genai

class IntentClassifier:
    def __init__(self, taxonomy_path):
        self.taxonomy = load_taxonomy(taxonomy_path)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
    
    def classify(self, text):
        prompt = build_few_shot_prompt(self.taxonomy, text)
        response = self.model.generate_content(prompt)
        return parse_intent(response.text)
```

### Step 3: Cache LLM Responses
- Hash input → cached classification
- Avoids re-classifying during dev
- Preserves quota

### Step 4: Evaluate on Golden Set
- Your hand-labeled 150-250 examples
- Measure accuracy, per-class F1
- Compare to baselines

---

## Decision: Stop Perfecting Keywords

**Current state**:
- 4 specific cases fixed ✓
- general_inquiry still 57% (target 15-30%)
- French example passed validation ✗

**Options**:
A. **Keep fixing keyword rules** (more pain, diminishing returns)
B. **Lock taxonomy now, move to LLM classifier** (assignment-appropriate)

**Recommendation**: **Option B**

**Why**:
- Assignment is about RAG + evaluation rigor, not keyword engineering
- LLM classifier will handle all edge cases naturally
- Golden set is for measuring classifier quality, not training it
- You've identified the 8 intents — that's the hard part
- Examples are good enough to seed few-shot prompts

---

## Next Steps (If You Accept B)

1. **Accept current taxonomy** with understanding that:
   - Some examples may be imperfect (French, borderline cases)
   - These will be filtered/fixed during golden set hand-labeling
   - Taxonomy intents are solid even if keyword rules aren't perfect

2. **Move to golden set sampling**:
   - Stratified by intent (including oversampling rare ones)
   - Apply language filter NOW (English-only)
   - Apply safety filters NOW (crisis/PII escalation)
   - YOU hand-label 150-250 CLEAN examples

3. **Build LLM classifier**:
   - Uses approved taxonomy JSON
   - Few-shot Gemini prompting
   - Caching + rate limiting

4. **Evaluate**:
   - LLM classifier on YOUR golden labels
   - Two baselines (trivial + simple)
   - Report includes classifier quality metrics

---

## My Recommendation

**Stop** trying to perfect keyword rules. The French example and 57% general_inquiry tell you keyword rules are fundamentally limited.

**Accept** the taxonomy as-is (8 intents are correct, even if auto-classification isn't perfect).

**Move forward** to:
1. Golden set sampling (with language + safety filters)
2. Hand-labeling (you fix edge cases manually)
3. LLM classifier (handles variation properly)
4. Evaluation (the actual assignment focus)

**This gets you to the evaluation phase (the hard part) faster, with a better classifier.**

---

## Your Call

Do you want to:
- **A**: Keep perfecting keyword rules to hit 15-30% general_inquiry
- **B**: Lock taxonomy now, move to LLM classifier + golden set

I recommend **B** based on assignment priorities, but you decide.
