"""
Reply drafting using Groq (free tier) with RAG grounding.

Drafts replies based on retrieved historical resolutions.
Response caching to preserve free-tier quota.
"""

import hashlib
import json
import time
from pathlib import Path
from typing import List, Dict, Any

from groq import Groq
from tenacity import retry, stop_after_attempt, wait_exponential


class ReplyDrafter:
    """
    Groq-based reply drafter with RAG grounding.
    
    Takes customer message + retrieved historical resolutions.
    Drafts appropriate response grounded in historical examples.
    Caches all responses.
    """
    
    def __init__(
        self,
        cache_dir: Path,
        api_key: str,
        model_name: str = "openai/gpt-oss-20b",  # Fast free-tier model
    ):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.client = Groq(api_key=api_key)
        self.model_name = model_name
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 0.5  # Conservative for free tier
    
    def _get_cache_key(self, customer_message: str, retrieved_examples: List[Dict]) -> str:
        """Generate cache key from inputs."""
        # Include customer message + retrieved thread IDs in cache key
        cache_input = customer_message + "|" + "|".join(
            str(ex['thread_id']) for ex in retrieved_examples
        )
        return hashlib.sha256(cache_input.encode('utf-8')).hexdigest()
    
    def _get_cache_path(self, cache_key: str) -> Path:
        """Get path to cached response."""
        return self.cache_dir / f"{cache_key}.json"
    
    def _load_from_cache(self, cache_key: str) -> Any:
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
        """Enforce rate limit."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()
    
    def _build_prompt(
        self,
        customer_message: str,
        retrieved_examples: List[Dict[str, Any]],
    ) -> str:
        """Build grounded reply prompt."""
        prompt_parts = [
            "You are a customer support agent for Amazon. Draft a helpful reply to the customer.",
            "",
            "# Customer Message",
            f"\"{customer_message}\"",
            "",
            "# Similar Historical Cases (for grounding)",
            ""
        ]
        
        for i, example in enumerate(retrieved_examples, 1):
            similarity = example['similarity_score']
            customer_msg = example['customer_message'][:200]  # Truncate long messages
            resolution = example['brand_resolution'][:300]
            
            prompt_parts.append(f"## Example {i} (similarity: {similarity:.2f})")
            prompt_parts.append(f"Customer: \"{customer_msg}...\"")
            prompt_parts.append(f"Resolution: \"{resolution}...\"")
            prompt_parts.append("")
        
        prompt_parts.extend([
            "# Instructions",
            "- Draft a helpful, professional reply",
            "- Ground your response in the similar historical cases above",
            "- Be concise (2-3 sentences)",
            "- Use appropriate tone for the situation",
            "- If similar cases show a clear resolution pattern, follow it",
            "",
            "Draft reply:"
        ])
        
        return "\n".join(prompt_parts)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def _call_api(
        self,
        customer_message: str,
        retrieved_examples: List[Dict[str, Any]],
    ) -> str:
        """Call Groq API with retry logic."""
        self._rate_limit()
        
        prompt = self._build_prompt(customer_message, retrieved_examples)
        
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful customer support agent for Amazon."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=600,  # Increased from 200: gpt-oss-20b is a reasoning model that consumes tokens on internal thinking before the final reply; 200 was too tight and caused empty outputs on some inputs
        )
        
        return response.choices[0].message.content.strip()
    
    def draft_reply(
        self,
        customer_message: str,
        retrieved_examples: List[Dict[str, Any]],
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        Draft a reply grounded in retrieved examples.
        
        Args:
            customer_message: The customer's message
            retrieved_examples: Top-k similar historical cases from RAG
            use_cache: Whether to use cached responses
        
        Returns:
            {
                'drafted_reply': str,
                'grounding_strength': float (avg similarity of top-3 examples),
                'num_examples_used': int,
                'cached': bool
            }
        """
        cache_key = self._get_cache_key(customer_message, retrieved_examples)
        
        # Try cache
        if use_cache:
            cached = self._load_from_cache(cache_key)
            if cached is not None:
                cached['cached'] = True
                return cached
        
        # Call API
        drafted_reply = self._call_api(customer_message, retrieved_examples)
        
        # Calculate grounding strength (avg similarity of top-3)
        top_sims = [ex['similarity_score'] for ex in retrieved_examples[:3]]
        grounding_strength = sum(top_sims) / len(top_sims) if top_sims else 0.0
        
        result = {
            'drafted_reply': drafted_reply,
            'grounding_strength': grounding_strength,
            'num_examples_used': len(retrieved_examples),
            'cached': False
        }
        
        # Save to cache
        self._save_to_cache(cache_key, result)
        
        return result
