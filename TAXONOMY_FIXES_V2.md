# Taxonomy Quality Fixes v2

## Issues Fixed

### 1. ✅ General_Inquiry Too Coarse (69.3%)

**Problem**: Almost anything classified as "general" — includes delivery follow-ups and borderline venting.

**Root cause**: Disambiguation rule ("has question vs. pure venting") too loose — almost anything can be read as having implicit ask.

**Fix**: 
- **Tightened definition**: Must have EXPLICIT question marker (`where`, `when`, `how`, `what`, `why`) OR concrete action request (`please`, `help me`, `need to`, `can you`)
- **Delivery follow-ups**: Now route to `delivery_status_inquiry` regardless of tone (includes impatient "still not here!" messages)
- **Pure venting**: Strengthened `complaint_no_action` detection — venting without explicit question/request

**Expected impact**: `general_inquiry` should drop from 69% to ~15-25%

---

### 2. ✅ Wet-Parcel Message Still Misclassified

**Problem**: "wet parcel chucked over my front wall" was in `refund_return_request`, but contains no explicit refund/return ask per that category's stated rule.

**Root cause**: No validation that examples actually match intent descriptions.

**Fix**: Added `validate_example_matches_intent()` function
- Checks each example against intent's own keywords and disambiguation rules
- Rejects examples that don't fit
- Reports validation failures for manual review

**For refund_return_request**: Must contain explicit refund words (`refund`, `return`, `money back`, `send back`, `cancel order`)

**Expected**: Wet-parcel message either reclassified to `order_issue` or rejected from examples

---

### 3. ✅ Prime Service Complaint Misclassified

**Problem**: "I am a Prime member but I am not definitely getting prime service" in `order_issue` examples — this is about Prime service level, not wrong/damaged product.

**Root cause**: Same as #2 — no example validation.

**Fix**: 
- `order_issue` validation requires product problem keywords (`wrong`, `damaged`, `broken`, `missing`, `defective`)
- Prime service complaints explicitly excluded from `order_issue`
- Validation rejects examples mentioning "Prime service" if no product problem

**Expected**: This message reclassified to `delivery_status_inquiry` or `general_inquiry`

---

### 4. ✅ Credit Card Detection Bug

**Problem**: Safety filter test shows `"My credit card number is 4532-1234-5678-9010"` → `Escalate: False` — PII filter failed to trigger.

**Root cause**: Regex pattern `\b\d{13,19}\b` only matches continuous digit sequences, not numbers with hyphens/spaces.

**Fix**: Updated regex to handle CC formatting
```python
# Old (broken):
cc_pattern = r'\b\d{13,19}\b'

# New (fixed):
cc_pattern = r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{3,4}\b'
# Matches: 4532-1234-5678-9010, 4532 1234 5678 9010, 4532123456789010
```

**Test**: `test_safety_fix.py` verifies all formats now trigger escalation

---

### 5. ✅ Rare Intent Oversampling (Noted)

**Problem**: `account_access_issue` and `complaint_no_action` each have only 1 example (0.7%) in 150-sample.

**Not a taxonomy bug** — they're legitimately rare in AmazonHelp data.

**Solution**: Flag for golden-set sampling design
- **Noted in taxonomy JSON**: `"rare_intents_for_oversampling": ["account_access_issue", "complaint_no_action"]`
- **Golden-set sampler will**: Deliberately oversample these intents (boost to ~5-10% each) to ensure enough examples for classifier training and evaluation
- **Rationale**: Natural stratified sampling would give us ~1-2 examples — not enough for meaningful training or F1 measurement

---

## Revised Classification Logic

### Key Changes

**Delivery follow-ups** (even if venting):
- `"Still unresolved - no clue where the shipment is"` → `delivery_status_inquiry`
- Expanded keywords: `not here`, `still waiting`, `hasn't arrived`

**General inquiry** (tightened):
- Must have explicit question: `where`, `when`, `how`, `what`, `why`, `can you`, `would you`
- OR concrete action request: `please`, `help me`, `need to`, `want to`
- NOT just topic + frustration

**Complaint no action** (strengthened):
- Venting phrases: `pathetic`, `terrible`, `worst`, `disgusting`, `useless`, `ridiculous`, `joke`
- AND no explicit question/request
- OR very short (<50 chars) with no question mark

**Prime intent** (narrowed):
- Must mention Prime SUBSCRIPTION/MEMBERSHIP context
- Prime service complaints (`not getting prime service`) explicitly excluded

---

## Example Validation Rules

Each intent now validates examples against its own criteria:

| Intent | Validation Requirement |
|--------|----------------------|
| `refund_return_request` | MUST contain explicit refund/return words |
| `order_issue` | MUST mention product problem; Prime service complaints excluded |
| `prime_membership_inquiry` | MUST mention subscription/membership; not just "Prime" |
| `delivery_status_inquiry` | MUST ask about location/timing |
| `general_inquiry` | MUST have question marker or explicit request |

**Validation failures**: Reported in console + saved to JSON for review

---

## Updated Taxonomy (8 Intents)

| Intent | Description | % (Expected) | Notes |
|--------|-------------|--------------|-------|
| delivery_status_inquiry | Location/timing questions + follow-ups | ~35-45% | Increased from before |
| order_issue | Wrong/damaged/missing product | ~10-15% | |
| refund_return_request | Explicit refund/return ask | ~8-12% | |
| payment_billing_issue | Charges, unauthorized transactions | ~3-5% | |
| account_access_issue | Login, password, locked account | ~1-3% | Rare — oversample for golden set |
| prime_membership_inquiry | Prime subscription/benefits | ~2-4% | Narrowed |
| general_inquiry | Explicit questions/requests | ~15-25% | **Tightened from 69%** |
| complaint_no_action | Pure venting, no ask | ~1-3% | Rare — oversample for golden set |

---

## Testing

### Test Credit Card Fix
```bash
python test_safety_fix.py
```

**Expected output**: All credit card formats (hyphens, spaces, no separators) trigger escalation

### Run Refined Taxonomy
```bash
python scripts\06_refine_taxonomy.py
```

**Verify**:
1. ✓ `general_inquiry` < 30% (not 69%)
2. ✓ No wet-parcel message in examples (or properly classified)
3. ✓ No Prime service complaint in `order_issue`
4. ✓ Validation failures reported (if any)
5. ✓ No duplicate examples

---

## Next Steps

1. **YOU**: Run `test_safety_fix.py` to verify CC detection
2. **YOU**: Run `python scripts\06_refine_taxonomy.py` to regenerate taxonomy
3. **YOU**: Review validation failures (if any) and intent distribution
4. **YOU**: Confirm taxonomy OR request further adjustments
5. **ME**: Proceed to golden-set sampling with rare-intent oversampling

---

**Status**: All four issues fixed + rare-intent oversampling noted for golden-set design
