"""
Routing decision logic: auto-handle vs escalate.

Applies safety/language filters first (mandatory escalation).
Then applies routing logic based on intent, confidence, grounding strength.
"""

from typing import Dict, Any
from pathlib import Path

from src.safety_filters import apply_safety_filters
from src.language_filter import is_likely_english


class Router:
    """
    Routing decision engine.
    
    Applies "when in doubt, escalate" bias matching human labeling.
    Uses safety filters, language filter, intent confidence, and grounding strength.
    """
    
    def __init__(self):
        # Routing thresholds (tunable, but conservative by default)
        self.confidence_threshold_auto = 'high'  # Only auto-handle high confidence
        self.grounding_threshold_auto = 0.34  # Recalibrated from empirical grounding_strength distribution: auto_handle         mean=0.362 vs escalate mean=0.284 (see outputs/eval_results.json, n=13 pilot run) 
        
        # Intents that lean escalate by default
        self.escalate_prone_intents = {
            'complaint_no_action',  # No clear action path
            'payment_billing_issue',  # Financial risk
        }
        
        # Intents safe to auto-handle if conditions met
        self.auto_handle_safe_intents = {
            'delivery_status_inquiry',
            'general_inquiry',
            'account_access_issue',  # Password resets etc.
        }
    
    def route(
        self,
        customer_message: str,
        intent: str,
        intent_confidence: str,
        grounding_strength: float,
    ) -> Dict[str, Any]:
        """
        Make routing decision.
        
        Args:
            customer_message: Customer's message text
            intent: Predicted intent
            intent_confidence: Classifier confidence (high/medium/low)
            grounding_strength: RAG grounding strength (0-1)
        
        Returns:
            {
                'routing': 'auto_handle' or 'escalate',
                'routing_reason': str (explanation),
                'safety_flagged': bool,
                'language_flagged': bool,
            }
        """
           # PRIORITY 1: Safety filter (mandatory escalation)
        safety_result = apply_safety_filters(customer_message)
        if safety_result['should_escalate']:
            return {
                'routing': 'escalate',
                'routing_reason': f"Safety flagged: {', '.join(safety_result['escalation_reasons'])}",
                'safety_flagged': True,
                'language_flagged': False,
            }
        
          # PRIORITY 2: Language filter (mandatory escalation)
        is_eng, lang_reason = is_likely_english(customer_message)
        if not is_eng:
            return {
                'routing': 'escalate',
                'routing_reason': f"Non-English message (out of scope): {lang_reason}",
                'safety_flagged': False,
                'language_flagged': True,
            }
        
        # PRIORITY 3: Intent-based routing
        
        # Escalate-prone intents (no clear action path)
        if intent in self.escalate_prone_intents:
            return {
                'routing': 'escalate',
                'routing_reason': f"Intent '{intent}' requires human judgment",
                'safety_flagged': False,
                'language_flagged': False,
            }
        
        # Low confidence → escalate
        if intent_confidence == 'low':
            return {
                'routing': 'escalate',
                'routing_reason': f"Low classifier confidence on intent '{intent}'",
                'safety_flagged': False,
                'language_flagged': False,
            }
        
        # Medium confidence + weak grounding → escalate
        if intent_confidence == 'medium' and grounding_strength < self.grounding_threshold_auto:
            return {
                'routing': 'escalate',
                'routing_reason': f"Medium confidence + weak grounding (similarity {grounding_strength:.2f})",
                'safety_flagged': False,
                'language_flagged': False,
            }
        
        # High confidence + safe intent + decent grounding → auto-handle
        if (intent_confidence == 'high' and 
            intent in self.auto_handle_safe_intents and
            grounding_strength >= self.grounding_threshold_auto):
            return {
                'routing': 'auto_handle',
                'routing_reason': f"High confidence, safe intent, strong grounding ({grounding_strength:.2f})",
                'safety_flagged': False,
                'language_flagged': False,
            }
        
        # High confidence + safe intent + weak grounding → escalate (when in doubt)
        if (intent_confidence == 'high' and 
            intent in self.auto_handle_safe_intents):
            return {
                'routing': 'escalate',
                'routing_reason': f"Weak grounding ({grounding_strength:.2f}), no strong match found",
                'safety_flagged': False,
                'language_flagged': False,
            }
        
        # Default: escalate (when in doubt)
        # Covers: order_issue, refund_return, prime_membership, etc.
        return {
            'routing': 'escalate',
            'routing_reason': f"Intent '{intent}' default escalation (policy/value risk)",
            'safety_flagged': False,
            'language_flagged': False,
        }
