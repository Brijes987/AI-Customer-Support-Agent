#!/usr/bin/env python3
"""
End-to-end customer support AI pipeline.

Components:
1. Intent classification (Gemini few-shot)
2. RAG retrieval (sentence-transformers + FAISS)
3. Reply drafting (Groq grounded generation)
4. Routing decision (safety + language + logic)

Usage:
    python scripts/run_pipeline.py --test "Where is my package?"
    python scripts/run_pipeline.py --build-corpus  # First time setup
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any

from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.intent_classifier import IntentClassifier
from src.rag_retriever import RAGRetriever
from src.reply_drafter import ReplyDrafter
from src.router import Router


class CustomerSupportPipeline:
    """
    End-to-end pipeline for customer support AI.
    
    Takes customer message → returns intent, drafted reply, routing decision.
    """
    
    def __init__(
        self,
        taxonomy_path: Path,
        threads_path: Path,
        golden_set_path: Path,
        cache_dir: Path,
        gemini_api_key: str,
        groq_api_key: str,
    ):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        print("Initializing pipeline components...")
        
        self.classifier = IntentClassifier(
            taxonomy_path=taxonomy_path,
            cache_dir=cache_dir / "classifier_cache",
            api_key=gemini_api_key,
        )
        print("✓ Intent classifier initialized")
        
        self.retriever = RAGRetriever(
            corpus_cache_dir=cache_dir / "rag_cache",
        )
        # Load corpus from cache (fast — cache already built via --build-corpus)
        self.retriever.build_corpus(
            threads_path=threads_path,
            golden_set_path=golden_set_path,
        )
        print("✓ RAG retriever initialized")
        
        self.drafter = ReplyDrafter(
            cache_dir=cache_dir / "drafter_cache",
            api_key=groq_api_key,
        )
        print("✓ Reply drafter initialized")
        
        self.router = Router()
        print("✓ Router initialized")
        
        # Store paths for corpus building
        self.threads_path = threads_path
        self.golden_set_path = golden_set_path
    
    def build_corpus(self, force_rebuild: bool = False):
        """Build RAG corpus (first-time setup)."""
        print("\n" + "=" * 80)
        print("Building RAG Corpus")
        print("=" * 80)
        
        self.retriever.build_corpus(
            threads_path=self.threads_path,
            golden_set_path=self.golden_set_path,
            force_rebuild=force_rebuild,
        )
        
        print("=" * 80)
        print("✓ Corpus build complete")
        print("=" * 80)
    
    def process(
        self,
        customer_message: str,
        use_cache: bool = True,
        retrieve_k: int = 5,
    ) -> Dict[str, Any]:
        """
        Process a customer message end-to-end.
        
        Args:
            customer_message: Customer's message text
            use_cache: Whether to use cached responses
            retrieve_k: Number of similar cases to retrieve
        
        Returns:
            {
                'customer_message': str,
                'intent': str,
                'intent_confidence': str,
                'intent_reasoning': str,
                'retrieved_examples': List[Dict],
                'drafted_reply': str,
                'grounding_strength': float,
                'routing': str (auto_handle/escalate),
                'routing_reason': str,
                'safety_flagged': bool,
                'language_flagged': bool,
            }
        """
        print("\n" + "=" * 80)
        print("Processing Customer Message")
        print("=" * 80)
        print(f"\nCustomer: \"{customer_message}\"\n")
        
        # Step 1: Intent classification
        print("[1/4] Classifying intent...")
        classification = self.classifier.classify(customer_message, use_cache=use_cache)
        intent = classification['intent']
        intent_confidence = classification['confidence']
        intent_reasoning = classification['reasoning']
        cached_str = " (cached)" if classification['cached'] else ""
        print(f"✓ Intent: {intent} (confidence: {intent_confidence}){cached_str}")
        print(f"  Reasoning: {intent_reasoning}")
        
        # Step 2: RAG retrieval
        print(f"\n[2/4] Retrieving top-{retrieve_k} similar cases...")
        retrieved = self.retriever.retrieve(customer_message, k=retrieve_k, use_cache=use_cache)
        print(f"✓ Retrieved {len(retrieved)} examples")
        if retrieved:
            top_sim = retrieved[0]['similarity_score']
            print(f"  Top similarity: {top_sim:.3f}")
        
        # Step 3: Draft reply
        print("\n[3/4] Drafting reply...")
        draft_result = self.drafter.draft_reply(
            customer_message,
            retrieved,
            use_cache=use_cache
        )
        drafted_reply = draft_result['drafted_reply']
        grounding_strength = draft_result['grounding_strength']
        cached_str = " (cached)" if draft_result['cached'] else ""
        print(f"✓ Reply drafted{cached_str}")
        print(f"  Grounding strength: {grounding_strength:.3f}")
        print(f"  Reply: \"{drafted_reply[:100]}...\"")
        
        # Step 4: Routing decision
        print("\n[4/4] Making routing decision...")
        routing_result = self.router.route(
            customer_message=customer_message,
            intent=intent,
            intent_confidence=intent_confidence,
            grounding_strength=grounding_strength,
        )
        routing = routing_result['routing']
        routing_reason = routing_result['routing_reason']
        print(f"✓ Routing: {routing.upper()}")
        print(f"  Reason: {routing_reason}")
        
        # Compile result
        result = {
            'customer_message': customer_message,
            'intent': intent,
            'intent_confidence': intent_confidence,
            'intent_reasoning': intent_reasoning,
            'retrieved_examples': retrieved,
            'drafted_reply': drafted_reply,
            'grounding_strength': grounding_strength,
            'routing': routing,
            'routing_reason': routing_reason,
            'safety_flagged': routing_result['safety_flagged'],
            'language_flagged': routing_result['language_flagged'],
        }
        
        print("\n" + "=" * 80)
        print("✓ Pipeline complete")
        print("=" * 80)
        
        return result


def main():
    parser = argparse.ArgumentParser(
        description="Customer support AI pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # First time: build RAG corpus
  python scripts/run_pipeline.py --build-corpus
  
  # Test with a message
  python scripts/run_pipeline.py --test "Where is my package?"
  
  # Test with multiple messages
  python scripts/run_pipeline.py --test-file test_messages.txt
        """
    )
    
    parser.add_argument(
        '--build-corpus',
        action='store_true',
        help='Build RAG corpus (first time setup)'
    )
    parser.add_argument(
        '--force-rebuild',
        action='store_true',
        help='Force rebuild corpus even if cache exists'
    )
    parser.add_argument(
        '--test',
        type=str,
        help='Test with a single customer message'
    )
    parser.add_argument(
        '--test-file',
        type=Path,
        help='Test with messages from file (one per line)'
    )
    parser.add_argument(
        '--output',
        type=Path,
        help='Save results to JSON file'
    )
    parser.add_argument(
        '--no-cache',
        action='store_true',
        help='Disable caching (force fresh API calls)'
    )
    parser.add_argument(
        '--retrieve-k',
        type=int,
        default=5,
        help='Number of similar cases to retrieve (default: 5)'
    )
    
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    gemini_api_key = os.getenv('GOOGLE_API_KEY')
    groq_api_key = os.getenv('GROQ_API_KEY')
    
    if not gemini_api_key:
        print("❌ GOOGLE_API_KEY not found in environment")
        print("   Set it in .env file or export GOOGLE_API_KEY=...")
        return 1
    
    if not groq_api_key:
        print("❌ GROQ_API_KEY not found in environment")
        print("   Set it in .env file or export GROQ_API_KEY=...")
        return 1
    
    # Paths
    taxonomy_path = Path('golden_set/approved_taxonomy.json')
    threads_path = Path('data/processed/threads.jsonl')
    golden_set_path = Path('golden_set/unlabeled_sample.jsonl')
    cache_dir = Path('cache/pipeline')
    
    # Initialize pipeline
    pipeline = CustomerSupportPipeline(
        taxonomy_path=taxonomy_path,
        threads_path=threads_path,
        golden_set_path=golden_set_path,
        cache_dir=cache_dir,
        gemini_api_key=gemini_api_key,
        groq_api_key=groq_api_key,
    )
    
    # Build corpus if requested
    if args.build_corpus:
        pipeline.build_corpus(force_rebuild=args.force_rebuild)
        return 0
    
    # Test with single message
    if args.test:
        result = pipeline.process(
            args.test,
            use_cache=not args.no_cache,
            retrieve_k=args.retrieve_k,
        )
        
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2)
            print(f"\n✓ Result saved to {args.output}")
        
        return 0
    
    # Test with file
    if args.test_file:
        if not args.test_file.exists():
            print(f"❌ File not found: {args.test_file}")
            return 1
        
        with open(args.test_file, 'r', encoding='utf-8') as f:
            messages = [line.strip() for line in f if line.strip()]
        
        results = []
        for i, message in enumerate(messages, 1):
            print(f"\n{'=' * 80}")
            print(f"Message {i}/{len(messages)}")
            print('=' * 80)
            
            result = pipeline.process(
                message,
                use_cache=not args.no_cache,
                retrieve_k=args.retrieve_k,
            )
            results.append(result)
        
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2)
            print(f"\n✓ Results saved to {args.output}")
        
        return 0
    
    # No action specified
    parser.print_help()
    return 1


if __name__ == "__main__":
    exit(main())
