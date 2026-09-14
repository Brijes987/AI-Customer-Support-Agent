# Intent Taxonomy Derivation - AmazonHelp

## Brand Confirmed

**Selected**: AmazonHelp

**Justification**:
- **Volume**: 82,555 threads (highest in dataset)
- **Multi-turn engagement**: 49.8% (strong for testing escalation logic)
- **Template diversity**: 90.8% unique templates (genuinely varied resolutions)
- **Top-5 concentration**: 0.4% (NOT canned spam — real problem-solving)
- **Resolution rate**: 79.2% (lowest of top 10, but acceptable given broader issue range)

**Deliberate trade-off**: Lower resolution rate accepted due to Amazon's diverse issue types (delivery, orders, payments, accounts, Prime, returns). This complexity makes the assignment more realistic and challenging.

---

## Taxonomy Derivation Process

### Step 1: Sample Representative Threads

**Script**: `scripts/04_sample_for_taxonomy.py`

**Purpose**: Extract 150 stratified threads from AmazonHelp for analysis

**Stratification**:
- **Thread length**: Short (2-3), Medium (4-6), Long (7+)
- **Resolution status**: Resolved (ends with brand) vs. Unresolved (ends with customer)
- **Engagement**: Single-turn vs. Multi-turn brand responses

**Run**:
```bash
python scripts\04_sample_for_taxonomy.py --brand AmazonHelp --sample-size 150
```

**Outputs**:
- `outputs/taxonomy_sample.jsonl` — 150 sampled threads (JSON Lines)
- `outputs/taxonomy_sample_display.txt` — Human-readable format with:
  - Quick scan: First 50 initial customer messages
  - Full details: First 30 complete threads with all messages

### Step 2: Propose Taxonomy from Patterns

**Script**: `scripts/05_propose_taxonomy.py`

**Purpose**: Analyze sampled threads and propose 6-10 intent categories

**Analysis methods**:
1. **Keyword analysis**: Count occurrences of domain keywords (delivery, refund, account, etc.)
2. **Question patterns**: Identify common question structures ("where is", "when will", "how do i")
3. **Pattern clustering**: Group messages by keyword overlap

**Run**:
```bash
python scripts\05_propose_taxonomy.py
```

**Output**:
- `outputs/proposed_taxonomy.json` — Structured taxonomy with:
  - Intent name
  - Description
  - Keywords
  - 3-5 example utterances per intent

### Step 3: Human Review and Confirmation

**YOU must**:
1. Read `outputs/taxonomy_sample_display.txt` to see actual customer messages
2. Review `outputs/proposed_taxonomy.json` for the automated proposal
3. Validate intent boundaries (are they distinct? overlapping? missing categories?)
4. Confirm or adjust taxonomy before proceeding to classifier

---

## Expected Intents (Hypothesized)

Based on AmazonHelp domain knowledge, expect to see:

1. **Delivery/Shipping Status Inquiry**
   - "Where is my package?"
   - "Tracking shows delivered but I didn't receive it"
   - "When will my order arrive?"

2. **Order Issue (Wrong/Missing/Damaged Item)**
   - "Received wrong item"
   - "Package is missing items"
   - "Product arrived damaged"

3. **Refund/Return Request**
   - "How do I return this?"
   - "Need a refund for order #12345"
   - "Want to cancel my order"

4. **Payment/Billing Issue**
   - "Why was I charged twice?"
   - "Unauthorized charge on my account"
   - "Payment method declined"

5. **Account Access Issue**
   - "Can't log in to my account"
   - "Password reset not working"
   - "Account locked"

6. **Prime Membership Question**
   - "How does Prime work?"
   - "Cancel Prime subscription"
   - "Prime benefits question"

7. **General Inquiry / Other**
   - Catch-all for diverse or unclear requests
   - May need to split if patterns emerge

**Final count**: Aim for 6-10 intents (not more — taxonomy should be manageable)

---

## Validation Criteria

### Good taxonomy:
- ✅ **Distinct**: Intents don't heavily overlap (customer message clearly belongs to one)
- ✅ **Balanced**: No single intent dominates >40% of messages (except maybe "general")
- ✅ **Actionable**: Each intent suggests different resolution patterns
- ✅ **Grounded**: Intents derived from actual data, not assumed categories
- ✅ **Coverage**: <10% of messages fall into "other" catch-all

### Bad taxonomy:
- ❌ **Overlapping**: "Refund request" vs. "Order issue" blur together
- ❌ **Too granular**: 20+ micro-categories that are hard to distinguish
- ❌ **Too coarse**: 3 intents with everything lumped together
- ❌ **Assumed**: Based on Banking77 or generic support categories, not AmazonHelp data

---

## Quick Start Commands

### Option A: Run both steps together
```bash
# Windows batch file
run_taxonomy_derivation.bat

# Or manually:
python scripts\04_sample_for_taxonomy.py --brand AmazonHelp --sample-size 150
python scripts\05_propose_taxonomy.py
```

### Option B: Step by step (if you want to inspect samples first)
```bash
# Step 1: Sample threads
python scripts\04_sample_for_taxonomy.py --brand AmazonHelp --sample-size 150

# Inspect: outputs\taxonomy_sample_display.txt

# Step 2: Propose taxonomy
python scripts\05_propose_taxonomy.py

# Review: outputs\proposed_taxonomy.json
```

---

## After Confirmation

Once you confirm the taxonomy:

1. **Lock it**: Save approved taxonomy as `golden_set/approved_taxonomy.json`
2. **Document**: Add justification for intent boundaries to decision log
3. **Proceed to**: Golden set sampling (use stratified sampling BY INTENT)

---

**Status**: Scripts ready, awaiting your execution and taxonomy confirmation
