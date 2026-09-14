"""
RAG retrieval system for grounded reply drafting.

Uses local TF-IDF (scikit-learn) for retrieval instead of dense embeddings.
No API calls, no daily quota limits, no native-library crashes.
Explicitly excludes golden set threads from corpus.

NOTE: Originally attempted local sentence-transformers (crashed on this
Windows machine across 3 versions), then Gemini embedding API (hit daily
free-tier quota after ~1000 calls). Switched to TF-IDF cosine similarity
as a pragmatic, fully local fallback. Trade-off: TF-IDF captures
keyword/topic overlap well for support tickets but misses paraphrase-level
semantic similarity that dense embeddings would catch. Documented as a
known limitation in the report.
"""

import json
import hashlib
import pickle
from pathlib import Path
from typing import List, Dict, Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from tqdm import tqdm


class RAGRetriever:
    """
    Retrieval system for finding similar historical resolutions.

    Builds corpus from AmazonHelp threads, EXCLUDING golden set.
    Uses TF-IDF + cosine similarity (local, no API, no quota).
    """

    def __init__(
        self,
        corpus_cache_dir: Path,
        model_name: str = "tfidf",  # kept for interface compatibility
    ):
        self.corpus_cache_dir = corpus_cache_dir
        self.corpus_cache_dir.mkdir(parents=True, exist_ok=True)

        self.model_name = model_name

        self.corpus = None
        self.vectorizer = None
        self.tfidf_matrix = None  # sparse matrix, shape (n_corpus, n_features)

    def build_corpus(
        self,
        threads_path: Path,
        golden_set_path: Path,
        force_rebuild: bool = False,
        max_corpus_size: int = 10000,  # TF-IDF is local/free — can afford a much larger corpus
    ):
        """
        Build retrieval corpus from historical threads.

        CRITICAL: Excludes all threads in golden_set to prevent leakage.
        """
        corpus_cache = self.corpus_cache_dir / "corpus.pkl"
        vectorizer_cache = self.corpus_cache_dir / "vectorizer.pkl"
        matrix_cache = self.corpus_cache_dir / "tfidf_matrix.pkl"

        # Check cache
        if not force_rebuild and corpus_cache.exists() and vectorizer_cache.exists() and matrix_cache.exists():
            print("Loading cached corpus and TF-IDF index...")
            with open(corpus_cache, 'rb') as f:
                self.corpus = pickle.load(f)
            with open(vectorizer_cache, 'rb') as f:
                self.vectorizer = pickle.load(f)
            with open(matrix_cache, 'rb') as f:
                self.tfidf_matrix = pickle.load(f)
            print(f"✓ Loaded {len(self.corpus)} corpus entries from cache")
            return

        print("Building corpus from scratch...")

        # Load golden set thread IDs (EXCLUDE THESE)
        print(f"Loading golden set from {golden_set_path}...")
        golden_set_ids = set()
        with open(golden_set_path, 'r', encoding='utf-8') as f:
            for line in f:
                thread = json.loads(line)
                golden_set_ids.add(thread['thread_id'])
        print(f"✓ Golden set: {len(golden_set_ids)} threads (WILL BE EXCLUDED)")

        # Load all threads
        print(f"Loading all threads from {threads_path}...")
        all_threads = []
        with open(threads_path, 'r', encoding='utf-8') as f:
            for line in tqdm(f, desc="Loading threads"):
                thread = json.loads(line)
                # Filter for AmazonHelp only (check brand messages' author field)
                is_amazon = any(
                    msg.get('author_role') == 'brand' and msg.get('author') == 'AmazonHelp'
                    for msg in thread.get('messages', [])
                )
                if is_amazon:
                    all_threads.append(thread)
        print(f"✓ Loaded {len(all_threads)} AmazonHelp threads")

        # Build corpus entries (EXCLUDE GOLDEN SET)
        print("Building corpus entries...")
        self.corpus = []
        excluded_count = 0

        for thread in tqdm(all_threads, desc="Building corpus"):
            thread_id = thread['thread_id']

            # CRITICAL: Skip golden set threads
            if thread_id in golden_set_ids:
                excluded_count += 1
                continue

            first_customer = next(
                (msg for msg in thread['messages'] if msg['author_role'] == 'customer'),
                None
            )
            last_brand = next(
                (msg for msg in reversed(thread['messages']) if msg['author_role'] == 'brand'),
                None
            )

            if first_customer and last_brand:
                self.corpus.append({
                    'thread_id': thread_id,
                    'customer_message': first_customer['text'],
                    'brand_resolution': last_brand['text'],
                    'full_thread': thread,
                })

        print(f"✓ Built corpus: {len(self.corpus)} entries")
        print(f"  Excluded {excluded_count} golden-set threads")

        # CRITICAL ASSERTION: No golden set thread should be in corpus
        corpus_ids = {entry['thread_id'] for entry in self.corpus}
        leaked_ids = corpus_ids.intersection(golden_set_ids)
        if leaked_ids:
            raise AssertionError(
                f"GOLDEN SET LEAKAGE DETECTED: {len(leaked_ids)} golden-set threads found in corpus! "
                f"First few leaked IDs: {list(leaked_ids)[:5]}"
            )
        print("✓ Assertion passed: No golden-set threads in corpus")

        # Cap corpus size (generous, since TF-IDF is local/free)
        if len(self.corpus) > max_corpus_size:
            print(f"Capping corpus to {max_corpus_size} entries (random sample)...")
            rng = np.random.default_rng(seed=42)
            idx = rng.choice(len(self.corpus), size=max_corpus_size, replace=False)
            self.corpus = [self.corpus[i] for i in idx]

        # Build TF-IDF index (local, instant, no API calls)
        print("Building TF-IDF index (local, no API calls)...")
        customer_messages = [entry['customer_message'] for entry in self.corpus]
        self.vectorizer = TfidfVectorizer(
            max_features=20000,
            ngram_range=(1, 2),
            stop_words='english',
            min_df=1,
        )
        self.tfidf_matrix = self.vectorizer.fit_transform(customer_messages)
        print(f"✓ TF-IDF index built: {self.tfidf_matrix.shape[0]} docs, "
              f"{self.tfidf_matrix.shape[1]} features")

        # Save to cache
        print("Saving to cache...")
        with open(corpus_cache, 'wb') as f:
            pickle.dump(self.corpus, f)
        with open(vectorizer_cache, 'wb') as f:
            pickle.dump(self.vectorizer, f)
        with open(matrix_cache, 'wb') as f:
            pickle.dump(self.tfidf_matrix, f)
        print("✓ Saved to cache")

    def _get_retrieval_cache_key(self, query: str, k: int) -> str:
        cache_input = f"{query}|{k}"
        return hashlib.sha256(cache_input.encode('utf-8')).hexdigest()

    def retrieve(
        self,
        query: str,
        k: int = 5,
        use_cache: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve top-k most similar historical threads using TF-IDF cosine similarity.

        Returns list of dicts with customer_message, brand_resolution,
        similarity_score, thread_id.
        """
        if self.corpus is None or self.vectorizer is None or self.tfidf_matrix is None:
            raise RuntimeError("Corpus not built. Call build_corpus() first.")

        cache_key = self._get_retrieval_cache_key(query, k)
        cache_path = self.corpus_cache_dir / f"retrieval_{cache_key}.json"

        if use_cache and cache_path.exists():
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)

        # Vectorize query with the SAME fitted vectorizer (no API call)
        query_vec = self.vectorizer.transform([query])

        # Cosine similarity against all corpus entries
        similarities = cosine_similarity(query_vec, self.tfidf_matrix)[0]

        # Top-k indices
        top_k_idx = np.argsort(similarities)[::-1][:k]

        results = []
        for idx in top_k_idx:
            score = float(similarities[idx])
            if score <= 0:
                continue  # skip zero-similarity (no keyword overlap at all)
            corpus_entry = self.corpus[idx]
            results.append({
                'customer_message': corpus_entry['customer_message'],
                'brand_resolution': corpus_entry['brand_resolution'],
                'similarity_score': score,
                'thread_id': corpus_entry['thread_id'],
            })

        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2)

        return results