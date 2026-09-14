# Template Normalization for Reply Diversity

## The Problem

**Observation**: Reply diversity = 100% for all brands (exact same issue as response rate)

**Root Cause**: Customer support replies include personalized elements that make each reply unique as a string, even when the underlying template is identical:

```
"Hi @alice, your order #12345 is ready!"
"Hi @bob, your order #67890 is ready!"
```

These are the **same template** with different personalization, but exact-string matching counts them as two unique replies.

**Why This Matters**: 
- Can't tell if a brand has genuinely diverse resolutions or just mail-merge templates
- RAG system grounded on templated responses will learn nothing useful
- Need to know **before** picking a brand whether replies show real problem-solving variety

---

## The Solution

### Normalize to Detect Template Structure

Strip personalized elements **before** comparing, to reveal the underlying template:

#### Normalization Rules

| Element | Pattern | Replacement | Example |
|---------|---------|-------------|---------|
| **@mentions** | `@\w+` | `@USER` | `@alice` → `@USER` |
| **URLs** | `https?://\S+` | `URL` | `https://track.co/xyz` → `URL` |
| **Long numbers** | `\b\d{3,}\b` | `NUM` | `#12345` → `#NUM` |
| **Short numbers** | `\b\d{1,2}\b(?!/)` | `N` | `order 5` → `order N` (keeps `24/7`) |
| **Case** | — | lowercase | `Hi` → `hi` |
| **Whitespace** | `\s+` | single space | Multiple spaces collapsed |

#### Example Transformation

**Input (two "unique" replies)**:
```
A: "Hi @alice! Your order #12345 is ready. Track: https://ex.co/t?id=xyz"
B: "Hi @bob! Your order #67890 is ready. Track: https://ex.co/t?id=abc"
```

**After normalization**:
```
A: "hi @USER! your order #NUM is ready. track: URL"
B: "hi @USER! your order #NUM is ready. track: URL"
```

**Result**: Detected as **1 template** (used twice), not 2 unique replies ✓

---

## Updated Metrics

### 1. `template_diversity_ratio`
- **Formula**: `unique_templates / total_responses`
- **Computed on**: Normalized text (after stripping personalization)
- **Expected range**: 5%-40% for real brands
- **Interpretation**:
  - <10% = Heavily templated (may be poor RAG candidate)
  - 15%-30% = Moderate diversity (good for RAG)
  - >40% = High diversity (excellent for RAG, or possibly messy/inconsistent)

### 2. `top_5_template_concentration`
- **Formula**: Sum of top 5 template counts / total responses
- **Shows**: How much of all support is covered by just 5 templates
- **Expected range**: 30%-80%
- **Interpretation**:
  - >70% = Very templated (5 templates handle most issues)
  - 40%-70% = Balanced (common patterns + variety)
  - <30% = Highly varied (many distinct resolution patterns)

### 3. `most_common_templates` (with raw examples)
- **Top 3-5 templates** ranked by frequency
- **Shows both**:
  - **Normalized template** (after stripping personalization)
  - **2 raw examples** (actual replies with personalization intact)
- **Purpose**: Validate normalization worked, inspect actual reply quality

---

## Output Format

### Console (per brand)
```
Template diversity: 12.3% unique (234/1,900 templates)
Top-5 template concentration: 68.5%
```

### Recommendation Detail
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

## What Makes a Good RAG Candidate

### ✅ Good Signs (Pick This Brand)
- Template diversity: **15%-35%**
- Top-5 concentration: **40%-65%**
- Common templates show genuine problem-solving (not just "DM us")
- Raw examples show contextual variation within templates

### ⚠️ Borderline (Review Carefully)
- Template diversity: **10%-15%** or **35%-50%**
- Top-5 concentration: **30%-40%** or **65%-75%**
- Some templates are generic, but others show detail
- May still work for RAG if top templates are informative

### ❌ Red Flags (Override Automated Ranking)
- Template diversity: **<10%** (essentially 5-10 templates repeated)
- Top-5 concentration: **>75%** (nearly all replies are variants of 5 templates)
- Top templates are all "Please DM us" / "Sorry to hear that" with no resolution detail
- Raw examples show zero contextual adaptation

---

## Implementation

**File**: `scripts/03_analyze_brands.py`

**Function**: `normalize_reply_for_template_matching(text)`
- Takes raw reply text
- Applies regex substitutions in order
- Returns normalized template string

**Used in**: `analyze_brand()` function
- Normalizes all brand replies before diversity calculation
- Keeps raw text separately for display/debugging
- Maps normalized templates back to raw examples

---

## Alternative: Embedding Clustering

**Not implemented yet**, but available if normalization proves insufficient:

```python
from sentence_transformers import SentenceTransformer
from sklearn.cluster import DBSCAN

model = SentenceTransformer('all-MiniLM-L6-v2')
embeddings = model.encode(brand_replies)
clusters = DBSCAN(eps=0.3, min_samples=5).fit(embeddings)
n_unique_clusters = len(set(clusters.labels_)) - (1 if -1 in clusters.labels_ else 0)
```

**Pros**: Captures semantic similarity beyond literal text
**Cons**: Slower, less interpretable, requires tuning DBSCAN params

**When to use**: If normalization still shows 100% diversity (unlikely), or if we want to measure "semantic templates" vs. "lexical templates"

---

## Test Now

```bash
python run_brand_analysis.py --test
```

**Expected variance after fix**:
- Template diversity: 8%-35% (varies by brand)
- Top-5 concentration: 40%-80% (varies by brand)
- Clear winner/loser separation

---

**Status**: Implemented, ready for validation
