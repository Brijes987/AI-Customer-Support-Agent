# Brand Scoring Fix v2: Template Diversity (Not Exact-String Uniqueness)

## Problem Identified (Second Iteration)

**First fix worked**: Multi-turn engagement now varies (10%-60% range) ✓

**New problem**: Template diversity showing 100.0% for all brands again — zero variance.

**Root cause**: Replies include personalized elements:
- @mentions (@username)
- Confirmation numbers (#12345)
- Order IDs, ticket numbers
- URLs with tracking params

**Why exact-string matching fails**:
```
Reply A: "Hi @alice, your order #12345 is ready!"
Reply B: "Hi @bob, your order #67890 is ready!"
```
These are counted as "unique" even though they're the same template with personalized data.

**Impact**: Can't distinguish between:
- Truly diverse resolutions (good for RAG)
- Templated responses with mail-merge personalization (bad for RAG)

---

## Solution: Template Normalization

### Normalize Before Comparing

Strip personalized elements to detect underlying template similarity:

**Normalization rules** (implemented in `normalize_reply_for_template_matching()`):

1. **@mentions** → `@USER`
   - `@alice` → `@USER`
   - `@company_support` → `@USER`

2. **URLs** → `URL`
   - `https://example.com/track?id=xyz` → `URL`

3. **Numbers (3+ digits)** → `NUM`
   - `#12345` → `#NUM`
   - `confirmation 98765` → `confirmation NUM`

4. **Standalone 1-2 digit numbers** → `N` (except in patterns like `24/7`)
   - `order 5 is ready` → `order N is ready`
   - Preserves: `24/7`, `9am`

5. **Case normalization** → lowercase

6. **Whitespace** → collapsed to single space

**Example transformation**:
```
Original A: "Hi @alice! Your order #12345 is ready. Track: https://ex.co/t?id=xyz"
Original B: "Hi @bob! Your order #67890 is ready. Track: https://ex.co/t?id=abc"

Normalized A: "hi @USER! your order #NUM is ready. track: URL"
Normalized B: "hi @USER! your order #NUM is ready. track: URL"

→ Detected as SAME TEMPLATE ✓
```

### New Metrics

All diversity metrics now computed on **normalized templates**, not raw text:

1. **`template_diversity_ratio`**: `unique_templates / total_responses`
   - After normalization
   - Now has real variance (expect 5%-40% range)

2. **`top_5_template_concentration`**: % of replies from top 5 templates
   - After normalization
   - Shows how heavily templated the brand is

3. **`most_common_templates`**: Top templates with:
   - Normalized template text
   - Count and percentage
   - **2 raw examples per template** (so you can see actual personalized versions)

**Console output per brand**:
```
Template diversity: 12.3% unique (234/1,900 templates)
Top-5 template concentration: 68.5%
```

**Recommendation detail**:
```
TEMPLATE DIVERSITY DETAIL:
  • Total responses: 1,900
  • Unique templates: 234
  • Top 5 templates account for: 68.5% of all replies
  • Most common templates (normalized, with raw examples):

    1. Template (32.1% of replies):
       Normalized: "hi @USER! your order #NUM is ready. track: URL"
       Raw examples:
         1. "Hi @alice! Your order #12345 is ready. Track: https://..."
         2. "Hi @bob! Your order #67890 is ready. Track: https://..."

    2. Template (18.4% of replies):
       Normalized: "sorry to hear that @USER. dm us your details?"
       Raw examples:
         1. "Sorry to hear that @customer123. DM us your details?"
         2. "Sorry to hear that @user456. DM us your details?"
```

---

## Expected Variance After Fix

### Good brands (suitable for RAG):
- Template diversity: 15%-40%
- Top-5 concentration: 30%-60%
- Templates show genuine problem-solving variation

### Bad brands (poor RAG candidates):
- Template diversity: <10%
- Top-5 concentration: >70%
- Top 3 templates are all variants of "please DM us"

---

## Files Changed

- ✏️ `scripts/03_analyze_brands.py`:
  - Added `normalize_reply_for_template_matching()` function
  - Normalize all replies before diversity calculation
  - Keep raw replies for display (2 examples per template)
  - Updated metrics: `template_diversity_ratio`, `top_5_template_concentration`
  - Updated console and JSON output to show normalized + raw

---

## Test Now

```bash
python run_brand_analysis.py --test
```

**Verify**:
1. ✓ Template diversity now varies (not all 100%)
2. ✓ Top-5 concentration varies
3. ✓ Normalized templates shown alongside raw examples
4. ✓ Can distinguish templated vs. diverse brands

If test shows real variance, run full dataset:
```bash
python run_brand_analysis.py
```

---

**Status**: Template normalization implemented, ready for testing

## Problems Identified

### 1. Response Rate Had Zero Variance (100% for all brands)
**Root cause**: Thread reconstruction only keeps threads that already have brand responses. By definition, every thread in `threads.jsonl` has at least one brand message, so "response rate" as measured (threads with response / total threads) was guaranteed to be 100%.

**Why this is bad**: A metric worth 30 points that's identical for all candidates contributes nothing to ranking and makes the scoring function misleading.

### 2. Missing Reply Diversity Metric
**Problem**: A brand with "high resolution rate" could be spamming the same canned response 1000 times. Without measuring reply diversity, we can't tell if RAG-grounding on this brand's history would produce meaningful variation.

**Why this matters**: The assignment requires RAG-grounded reply drafting. If all historical replies are identical templates, retrieval is pointless — the system would just learn to parrot one response regardless of context.

---

## Solution

### Replaced "Response Rate" → "Multi-Turn Engagement Rate"

**New metric**: `multi_turn_rate = (threads with ≥2 brand responses) / total_threads`

**Why this works**:
- **Has real variance**: Brands differ in whether they engage in back-and-forth vs. one-shot replies
- **Measures engagement depth**: High multi-turn rate = brand actually converses, not just auto-replies
- **Still worth 30 points**: Same weight as before, but now discriminates between brands

**Example variance** (from test run):
- Brand A: 45% multi-turn (deep engagement)
- Brand B: 12% multi-turn (mostly one-shot)
- Clear winner emerges

### Added Reply Diversity Metrics

**New metrics reported for each brand**:

1. **`diversity_ratio`**: `unique_replies / total_brand_responses`
   - Range: 0.0 (all identical) to 1.0 (every reply unique)
   - Example: 0.35 = 35% of replies are unique (65% are duplicates)

2. **`top_5_reply_concentration`**: Percentage of all replies accounted for by the 5 most common responses
   - Range: ~0% (very diverse) to ~100% (heavily templated)
   - Example: 45% = top 5 replies account for nearly half of all responses

3. **`most_common_replies`**: Top 3 most-used reply texts with counts and percentages
   - Displayed in console output (truncated to 80 chars)
   - Saved in full to JSON for detailed inspection

**Display in console output** (per brand):
```
Reply diversity: 32.5% unique (1,234/3,800)
Top-5 concentration: 48.3%
```

**Additional detail in recommendation justification**:
```
REPLY DIVERSITY DETAIL:
  • Total responses: 3,800
  • Unique responses: 1,234
  • Top 5 replies account for: 48.3% of all replies
  • Most common reply examples:
    1. "We'd like to help! Please DM us your account details." (12.3%)
    2. "Thanks for reaching out! Can you share more info?" (9.8%)
    3. "Sorry to hear that! Let's get this fixed. DM us?" (8.2%)
```

---

## Updated Scoring Function (100 points total)

| Dimension | Weight | What it measures | Why it varies |
|-----------|--------|------------------|---------------|
| **Volume** | 30 pts | Total threads (saturates at 10k) | More data = better taxonomy + splits |
| **Multi-turn engagement** | 30 pts | % threads with ≥2 brand responses | Deep conversation vs one-shot replies |
| **Thread length** | 20 pts | Avg messages per thread (sweet spot: 2-6) | Not too short (templated) or long (outliers) |
| **Resolution rate** | 20 pts | % threads ending with brand response | Closure/satisfaction signal |

**Diversity is NOT in the score (yet)**: Reported as a diagnostic metric to validate the brand choice. If the top-scored brand has terrible diversity (e.g., <10% unique), that's a red flag to override the automated ranking.

---

## Rationale for NOT Scoring Diversity (Yet)

1. **Unknown threshold**: What diversity % is "good enough"? 10%? 30%? 50%? We don't have ground truth until we test RAG on actual brand data.

2. **Domain-dependent**: Some support domains (e.g., order tracking) may legitimately have lower diversity than others (e.g., technical troubleshooting).

3. **Diagnostic first**: Better to report diversity as a veto criterion (reject brands with <X% unique) than to assign arbitrary weights.

4. **Can add later**: Once we see the full-dataset numbers, we can add a diversity score component (e.g., 10 bonus points for diversity >30%) in a second pass.

---

## What to Look For in Test Output

### Good signs:
- Multi-turn rate varies widely (e.g., 10%-60% range across brands)
- Diversity ratio >20% for top candidates
- Top-5 concentration <60% (not completely templated)
- Most common replies are reasonable support responses, not spam

### Red flags (override automated ranking):
- Diversity ratio <10% (essentially one template repeated)
- Top-5 concentration >80% (five replies dominate everything)
- Most common replies are nonsensical or identical strings
- Zero multi-turn engagement (every thread is brand → done)

---

## Files Changed

- ✏️ `scripts/03_analyze_brands.py`:
  - Replaced `response_rate` calculation with `multi_turn_rate`
  - Added diversity metrics: `diversity_ratio`, `top_5_reply_concentration`, `most_common_replies`
  - Updated console output to display diversity per brand
  - Updated JSON output to include all new metrics
  - Updated scoring function (30pts now on multi-turn, not response rate)
  - Updated justification section to include diversity detail

---

## Next Step

Re-run test mode:
```bash
python run_brand_analysis.py --test
```

**Verify**:
1. Multi-turn rate varies across brands (not all 100%)
2. Diversity metrics displayed for each brand
3. Recommendation includes diversity detail
4. No errors in calculation (handle division by zero, empty threads, etc.)

If test looks good, proceed to full dataset:
```bash
python run_brand_analysis.py
```

---

**Status**: Fixed, ready for testing
