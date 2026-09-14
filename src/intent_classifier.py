"""
Intent classifier using Gemini Flash (Google AI Studio free tier).

Few-shot classification from approved_taxonomy.json.
Response caching to preserve free-tier quota.
Rate limiting with backoff.
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any

import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential


class IntentClassifier:
    """
    LLM-based few-shot intent classifier using Gemini.
    
    Caches all responses to disk keyed by input hash.
    Rate limited for free tier (15 req/min).
    """
    
    def __init__(
        self,
        taxonomy_path: Path,
        cache_dir: Path,
        api_key: str,
        model_name: str = "gemini-flash-lite-latest",
    ):
        self.taxonomy_path = taxonomy_path
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Load taxonomy
        with open(taxonomy_path, 'r', encoding='utf-8') as f:
            self.taxonomy = json.load(f)
        
        # Configure Gemini
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        
        # Rate limiting state
        self.last_request_time = 0
        self.min_request_interval = 60.0 / 15.0  # 15 req/min = 4 sec between requests
        
        # Build classification prompt
        self.system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self) -> str:
        """Build few-shot classification prompt from taxonomy."""
        prompt_parts = [
            "You are an intent classifier for customer support messages.",
            "",
            f"Brand: {self.taxonomy['brand']}",
            f"Number of intents: {self.taxonomy['num_intents']}",
            "",
            "# Intent Definitions",
            ""
        ]
        
        for intent_data in self.taxonomy['intents']:
            intent = intent_data['intent']
            desc = intent_data['description']
            disambig = intent_data['disambiguation_rule']
            examples = intent_data['example_utterances']
            
            prompt_parts.append(f"## {intent}")
            prompt_parts.append(f"**Description**: {desc}")
            prompt_parts.append(f"**Disambiguation**: {disambig}")
            prompt_parts.append("**Examples**:")
            for ex in examples:
                prompt_parts.append(f"  - \"{ex}\"")
            prompt_parts.append("")
        
        # Add critical design notes
        prompt_parts.extend([
            "# Critical Rules",
            "",
            "1. **Venting + Topic**: If customer is venting about a specific topic (delivery, order, refund), classify as THAT topic's intent, NOT complaint_no_action.",
            "   - 'Still don't have my order!' → delivery_status_inquiry",
            "   - 'NOTHING YET. WOW' (no topic) → complaint_no_action",
            "",
            "2. **Priority order**: Check delivery_status_inquiry FIRST, then order_issue, then refund_return_request, etc.",
            "",
            "3. **Explicit language required**:",
            "   - refund_return_request: Must say 'refund', 'return', 'money back'",
            "   - prime_membership_inquiry: Must mention subscription/membership, not just service quality",
            "",
            "4. **Output format**: Return ONLY valid JSON:",
            '   {"intent": "<intent_name>", "confidence": "<high|medium|low>", "reasoning": "<brief explanation>"}',
            "",
        ])
        
        return "\n".join(prompt_parts)
    
    def _get_cache_key(self, text: str) -> str:
        """Generate cache key from input text."""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()
    
    def _get_cache_path(self, cache_key: str) -> Path:
        """Get path to cached response."""
        return self.cache_dir / f"{cache_key}.json"
    
    def _load_from_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Load cached response if exists."""
        cache_path = self._get_cache_path(cache_key)
        if cache_path.exists():
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    
    def _save_to_cache(self, cache_key: str, response: Dict[str, Any]):
        """Save response to cache."""
        cache_path = self._get_cache_path(cache_key)
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(response, f, indent=2)
    
    def _rate_limit(self):
        """Enforce rate limit (15 req/min for free tier)."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            sleep_time = self.min_request_interval - elapsed
            time.sleep(sleep_time)
        self.last_request_time = time.time()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def _call_api(self, text: str) -> Dict[str, Any]:
        """Call Gemini API with retry logic."""
        # Rate limit
        self._rate_limit()
        
        # Build user prompt
        user_prompt = f"""Classify this customer message into one of the {self.taxonomy['num_intents']} intents.

Customer message:
\"\"\"{text}\"\"\"

Return ONLY valid JSON with intent, confidence (high/medium/low), and brief reasoning."""
        
        # Call API
        full_prompt = f"{self.system_prompt}\n\n{user_prompt}"
        response = self.model.generate_content(full_prompt)
        
        # Parse response
        response_text = response.text.strip()
        
        # Extract JSON (handle markdown code blocks)
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        try:
            result = json.loads(response_text)
            
            # Validate response format
            if 'intent' not in result:
                raise ValueError("Missing 'intent' field in response")
            if result['intent'] not in [i['intent'] for i in self.taxonomy['intents']]:
                raise ValueError(f"Invalid intent: {result['intent']}")
            
            # Add defaults
            result.setdefault('confidence', 'medium')
            result.setdefault('reasoning', 'No reasoning provided')
            
            return result
        
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON response: {response_text}") from e
    
    def classify(self, text: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        Classify customer message into intent.
        
        Args:
            text: Customer message
            use_cache: Whether to use cached responses (default True)
        
        Returns:
            {
                'intent': str,
                'confidence': str (high/medium/low),
                'reasoning': str,
                'cached': bool
            }
        """
        cache_key = self._get_cache_key(text)
        
        # Try cache first
        if use_cache:
            cached = self._load_from_cache(cache_key)
            if cached is not None:
                cached['cached'] = True
                return cached
        
        # Call API
        result = self._call_api(text)
        result['cached'] = False
        
        # Save to cache
        self._save_to_cache(cache_key, result)
        
        return result
    
    def classify_thread(self, thread: Dict[str, Any], use_cache: bool = True) -> Dict[str, Any]:
        """
        Classify a thread by its first customer message.
        
        Args:
            thread: Thread dict with 'messages' list
            use_cache: Whether to use cached responses
        
        Returns:
            Classification result (same as classify())
        """
        # Extract first customer message
        first_customer = next(
            (msg for msg in thread['messages'] if msg['author_role'] == 'customer'),
            None
        )
        
        if not first_customer:
            return {
                'intent': 'unknown',
                'confidence': 'low',
                'reasoning': 'No customer message found',
                'cached': False
            }
        
        return self.classify(first_customer['text'], use_cache=use_cache)
