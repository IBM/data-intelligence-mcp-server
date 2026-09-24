# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""Similarity utilities: Granite embeddings, cosine similarity (torch-based),
and BM25 (via bm25.py TokenizedBM25).

Three components are provided:

    GraniteEmbeddingClient   – async client for Granite embedding models.
                               Supports a remote API (granite_embedding_url) and
                               a local SentenceTransformer model as fallback.
                               Exposes a module-level singleton ``embedding_client``.

    CosineSimilarityService  – dense vector cosine similarity using torch.
                               Accepts single vectors or matrices (n × d).

    BM25SimilarityService    – sparse keyword BM25 ranking using TokenizedBM25
                               from bm25.py with a corpus-derived word vocabulary.
                               Falls back gracefully when torch/scipy are absent.

Similarity labels (shared):
    > 0.85  → "Near Exact Match"
    ≥ 0.70  → "Highly Relevant"
    ≥ 0.60  → "Maybe Relevant"
    < 0.60  → "Low Relevance"
"""

from __future__ import annotations

import re
from typing import Optional

from app.core.settings import settings
from app.shared.logging import LOGGER
from app.shared.utils.http_client import get_http_client


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def get_similarity_label(score: float) -> str:
    """Convert a similarity score in [0, 1] to a human-readable label."""
    if score > 0.85:
        return "Near Exact Match"
    elif score >= 0.70:
        return "Highly Relevant"
    elif score >= 0.60:
        return "Maybe Relevant"
    else:
        return "Low Relevance"


# ---------------------------------------------------------------------------
# Granite embedding client
# ---------------------------------------------------------------------------

class GraniteEmbeddingClient:
    """Async client for Granite embedding models.

    Mode is determined at construction time from settings:
    - ``api``   – if ``settings.granite_embedding_url`` is set, calls the
                  remote embeddings endpoint (OpenAI-compatible ``/embeddings``).
    - ``local`` – otherwise loads a local SentenceTransformer model
                  (``settings.granite_local_model``).

    Usage::

        # module-level singleton:
        from app.services.similarity_utils import embedding_client
        vec = await embedding_client.get_embedding("some text")
    """

    def __init__(self) -> None:
        self.mode = "api" if settings.granite_embedding_url else "local"
        self.local_model = None
        # Local model is loaded lazily on first use so that importing this
        # module never blocks or raises when sentence-transformers is absent.
        LOGGER.info("GraniteEmbeddingClient initialised in %s mode", self.mode)

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _ensure_local_model(self) -> None:
        """Load the local SentenceTransformer model on first use."""
        if self.local_model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
            model_name = settings.granite_local_model
            cache_dir = settings.granite_local_cache_dir
            LOGGER.info("Loading local Granite model: %s", model_name)
            self.local_model = SentenceTransformer(model_name, cache_folder=cache_dir)
            LOGGER.info("Local Granite model loaded successfully")
        except ImportError:
            LOGGER.error(
                "sentence-transformers is not installed. "
                "Install with: pip install sentence-transformers"
            )
            raise
        except Exception as e:
            LOGGER.error("Failed to load local Granite model: %s", e)
            raise

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_embedding(self, text: str) -> Optional[list[float]]:
        """Return the embedding vector for *text*, or ``None`` on failure.

        Args:
            text: The text to embed.

        Returns:
            list[float] embedding vector, or None if the call failed.
        """
        if self.mode == "api":
            return await self._get_api_embedding(text)
        return self._get_local_embedding(text)

    async def get_embeddings_batch(self, texts: list[str]) -> list[Optional[list[float]]]:
        """Return embedding vectors for a list of texts.

        Calls are made sequentially for the API mode; for local mode all
        texts are encoded in a single batch call.

        Args:
            texts: Texts to embed.

        Returns:
            list of embedding vectors (or None for any that failed).
        """
        if self.mode == "local":
            return self._get_local_embeddings_batch(texts)
        results = []
        for text in texts:
            results.append(await self._get_api_embedding(text))
        return results

    # ------------------------------------------------------------------
    # Backend implementations
    # ------------------------------------------------------------------

    async def _get_api_embedding(self, text: str) -> Optional[list[float]]:
        """Call the remote Granite embeddings API."""
        try:
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if settings.granite_embedding_api_key:
                headers["Authorization"] = f"Bearer {settings.granite_embedding_api_key}"

            payload = {"text": text, "model": settings.granite_embedding_model}

            async with get_http_client() as client:
                response = await client.post(
                    f"{settings.granite_embedding_url}/embeddings",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
                embedding = data["embedding"]
                LOGGER.debug("API embedding dimension: %d", len(embedding))
                return embedding
        except Exception as e:
            LOGGER.error("Granite API embedding failed: %s", e)
            return None

    def _get_local_embedding(self, text: str) -> Optional[list[float]]:
        """Encode a single text with the local SentenceTransformer model."""
        try:
            self._ensure_local_model()
            embedding = self.local_model.encode([text])[0]
            LOGGER.debug("Local embedding dimension: %d", len(embedding))
            return embedding.tolist()
        except Exception as e:
            LOGGER.error("Local Granite embedding failed: %s", e)
            return None

    def _get_local_embeddings_batch(self, texts: list[str]) -> list[Optional[list[float]]]:
        """Encode a batch of texts with the local SentenceTransformer model."""
        try:
            self._ensure_local_model()
            embeddings = self.local_model.encode(texts)
            return [e.tolist() for e in embeddings]
        except Exception as e:
            LOGGER.error("Local Granite batch embedding failed: %s", e)
            return [None] * len(texts)


# Module-level singleton – import and use directly:
#   from app.services.similarity_utils import embedding_client
# Guard: only instantiate when the required Granite settings are present on the
# Settings object.  BM25SimilarityService and CosineSimilarityService are always
# available regardless; the singleton is only needed for embedding-based callers.
try:
    embedding_client = GraniteEmbeddingClient()
except AttributeError:
    LOGGER.warning(
        "GraniteEmbeddingClient singleton skipped: Granite settings not configured "
        "in Settings (granite_embedding_url / granite_local_model missing). "
        "BM25SimilarityService and CosineSimilarityService are still available."
    )
    embedding_client = None


# ---------------------------------------------------------------------------
# Cosine similarity – torch backend
# ---------------------------------------------------------------------------

class CosineSimilarityService:
    """Cosine similarity over dense float vectors using torch.

    Supports:
    - pairwise:  score(vec1, vec2) → float
    - one-to-many: score_batch(query_vec, corpus_vecs) → list[float]
    - matrix:    score_matrix(X, Y) → 2-D tensor  (n × m)

    All inputs are accepted as plain Python lists or torch.Tensor objects.
    """

    @staticmethod
    def _to_tensor(vec):
        """Convert list or tensor to a 1-D or 2-D float32 tensor."""
        import torch
        if isinstance(vec, torch.Tensor):
            return vec.float()
        return torch.tensor(vec, dtype=torch.float32)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def score(vec1, vec2) -> float:
        """Cosine similarity between two 1-D vectors.

        Args:
            vec1: First embedding vector (list[float] or 1-D tensor).
            vec2: Second embedding vector (list[float] or 1-D tensor).

        Returns:
            float in [0.0, 1.0].
        """
        try:
            import torch
            t1 = CosineSimilarityService._to_tensor(vec1).unsqueeze(0)  # (1, d)
            t2 = CosineSimilarityService._to_tensor(vec2).unsqueeze(0)  # (1, d)
            sim = CosineSimilarityService.score_matrix(t1, t2)          # (1, 1)
            return float(sim[0, 0].clamp(0.0, 1.0))
        except Exception as e:
            LOGGER.error("CosineSimilarityService.score failed: %s", e)
            return 0.0

    @staticmethod
    def score_batch(query_vec, corpus_vecs) -> list[float]:
        """Cosine similarity between one query vector and many corpus vectors.

        Args:
            query_vec:   1-D vector (list[float] or tensor).
            corpus_vecs: List of 1-D vectors or a 2-D tensor (n × d).

        Returns:
            list[float] of length n, each value in [0.0, 1.0].
        """
        try:
            import torch
            q = CosineSimilarityService._to_tensor(query_vec).unsqueeze(0)   # (1, d)
            if isinstance(corpus_vecs, torch.Tensor):
                C = corpus_vecs.float()
                if C.dim() == 1:
                    C = C.unsqueeze(0)
            else:
                C = torch.stack([CosineSimilarityService._to_tensor(v) for v in corpus_vecs])  # (n, d)
            sim = CosineSimilarityService.score_matrix(q, C)   # (1, n)
            return sim[0].clamp(0.0, 1.0).tolist()
        except Exception as e:
            LOGGER.error("CosineSimilarityService.score_batch failed: %s", e)
            return [0.0] * (len(corpus_vecs) if hasattr(corpus_vecs, "__len__") else 0)

    @staticmethod
    def score_matrix(X, Y) -> "torch.Tensor":
        """Cosine similarity between every row of X and every row of Y.

        Args:
            X: Tensor or list of shape (n, d).
            Y: Tensor or list of shape (m, d).

        Returns:
            torch.Tensor of shape (n, m) with values in [-1, 1].
            (Caller may clamp to [0, 1] for embedding outputs.)
        """
        import torch
        if not isinstance(X, torch.Tensor):
            X = torch.tensor(X, dtype=torch.float32)
        if not isinstance(Y, torch.Tensor):
            Y = torch.tensor(Y, dtype=torch.float32)
        X = X.float()
        Y = Y.float()
        # L2-normalise rows; guard against zero vectors
        xnorm = X / (X.norm(dim=1, keepdim=True).clamp(min=1e-12))
        ynorm = Y / (Y.norm(dim=1, keepdim=True).clamp(min=1e-12))
        return xnorm @ ynorm.T

    @staticmethod
    def label(score: float) -> str:
        """Human-readable label for a cosine similarity score."""
        return get_similarity_label(score)


# ---------------------------------------------------------------------------
# BM25 – TokenizedBM25 backend with a corpus-derived word vocabulary
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list[str]:
    """Lowercase word tokenizer: split on any non-alphanumeric character."""
    return [t for t in re.split(r"[^a-zA-Z0-9]", text.lower()) if t]


class BM25SimilarityService:
    """BM25 ranking over a text corpus using TokenizedBM25 from bm25.py.

    A lightweight word vocabulary is built from the corpus at index time.
    Token ID 0 is reserved as padding; real words start at 1.

    Usage::

        svc = BM25SimilarityService()
        svc.index(["data quality rule", "business term glossary", "lineage graph"])
        scores = svc.score("glossary term")   # list[float], one per document
        ranked = svc.rank("glossary term")    # list[(doc, score)] sorted desc

    Falls back to a pure-Python BM25 implementation when torch/scipy are
    unavailable so the service remains functional in minimal environments.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75, device: str = "cpu") -> None:
        self.k1 = k1
        self.b = b
        self.device = device
        self._documents: list[str] = []
        self._vocab: dict[str, int] = {}   # word → token ID (1-based; 0 = pad)
        self._model = None                 # TokenizedBM25 instance (or None)
        self._torch_available = self._check_torch()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _check_torch() -> bool:
        try:
            import torch   # noqa: F401
            import scipy   # noqa: F401
            return True
        except ImportError:
            return False

    def _build_vocab(self, documents: list[str]) -> dict[str, int]:
        vocab: dict[str, int] = {}
        for doc in documents:
            for word in _tokenize(doc):
                if word not in vocab:
                    vocab[word] = len(vocab) + 1   # 0 reserved for padding
        return vocab

    def _encode(self, text: str) -> list[int]:
        """Encode text as a list of integer token IDs (unknowns → 0)."""
        return [self._vocab.get(w, 0) for w in _tokenize(text)] or [0]

    def _texts_to_tensor(self, texts: list[str]) -> "torch.Tensor":
        """Encode a list of texts into a padded 2-D int64 tensor."""
        import torch
        encoded = [self._encode(t) for t in texts]
        max_len = max(len(e) for e in encoded)
        padded = [e + [0] * (max_len - len(e)) for e in encoded]
        return torch.tensor(padded, dtype=torch.long)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def index(self, documents: list[str]) -> None:
        """Build the BM25 index from a list of text documents.

        Args:
            documents: Corpus to index.
        """
        self._documents = list(documents)
        self._vocab = self._build_vocab(self._documents)
        vocab_size = len(self._vocab) + 1   # +1 for padding slot 0

        if self._torch_available:
            try:
                from bm25 import TokenizedBM25
                corpus_tensor = self._texts_to_tensor(self._documents)
                self._model = TokenizedBM25(
                    k1=self.k1, b=self.b,
                    vocab_size=vocab_size,
                    device=self.device,
                )
                self._model.index(corpus_tensor)
                LOGGER.debug(
                    "BM25SimilarityService: indexed %d documents, vocab size %d",
                    len(self._documents), vocab_size,
                )
                return
            except Exception as e:
                LOGGER.warning("BM25 torch backend unavailable (%s); using fallback", e)
                self._torch_available = False

        LOGGER.info("BM25SimilarityService: using pure-Python fallback")

    def score(self, query: str) -> list[float]:
        """Score all indexed documents against a query.

        Args:
            query: Free-text query string.

        Returns:
            list[float] of length == number of indexed documents.
            Scores are non-negative; higher is more relevant.
            Returns normalised [0, 1] values for the torch backend and
            the pure-Python fallback alike.
        """
        if not self._documents:
            return []

        if self._torch_available and self._model is not None:
            return self._score_torch(query)
        return self._score_fallback(query)

    def score_batch(self, queries: list[str]) -> list[list[float]]:
        """Score all documents for each query in a batch.

        Args:
            queries: List of query strings.

        Returns:
            list of list[float], shape (len(queries), len(documents)).
        """
        if not self._documents:
            return [[] for _ in queries]

        if self._torch_available and self._model is not None:
            try:
                import torch
                q_tensor = self._texts_to_tensor(queries)
                raw = self._model.score_batch(q_tensor)   # (Q, D)
                return self._normalise_matrix(raw).tolist()
            except Exception as e:
                LOGGER.error("BM25 batch scoring failed: %s", e)

        return [self._score_fallback(q) for q in queries]

    def rank(self, query: str) -> list[tuple[str, float]]:
        """Return documents sorted by BM25 score descending.

        Args:
            query: Free-text query string.

        Returns:
            list of (document, score) tuples, highest score first.
        """
        scores = self.score(query)
        pairs = list(zip(self._documents, scores))
        pairs.sort(key=lambda x: x[1], reverse=True)
        return pairs

    @staticmethod
    def label(score: float) -> str:
        """Human-readable label for a BM25 similarity score in [0, 1]."""
        return get_similarity_label(score)

    # ------------------------------------------------------------------
    # Backend implementations
    # ------------------------------------------------------------------

    def _score_torch(self, query: str) -> list[float]:
        try:
            import torch
            q_tensor = self._texts_to_tensor([query])          # (1, seq)
            raw = self._model.score_batch(q_tensor).squeeze(0) # (D,)
            normalised = self._normalise_vector(raw)
            return normalised.tolist()
        except Exception as e:
            LOGGER.error("BM25 torch scoring failed: %s; falling back", e)
            return self._score_fallback(query)

    def _score_fallback(self, query: str) -> list[float]:
        """Pure-Python BM25 (Okapi BM25) — no torch/scipy needed."""
        import math
        query_tokens = _tokenize(query)
        N = len(self._documents)
        if N == 0 or not query_tokens:
            return [0.0] * N

        # Build per-document token frequency maps
        doc_tf: list[dict[str, int]] = []
        doc_len: list[int] = []
        for doc in self._documents:
            tokens = _tokenize(doc)
            freq: dict[str, int] = {}
            for t in tokens:
                freq[t] = freq.get(t, 0) + 1
            doc_tf.append(freq)
            doc_len.append(len(tokens))

        avgdl = sum(doc_len) / N

        # Document frequency per query token
        df: dict[str, int] = {}
        for token in query_tokens:
            df[token] = sum(1 for tf in doc_tf if token in tf)

        scores: list[float] = []
        for i, tf in enumerate(doc_tf):
            s = 0.0
            for token in query_tokens:
                f = tf.get(token, 0)
                if f == 0:
                    continue
                idf = math.log((N - df[token] + 0.5) / (df[token] + 0.5) + 1)
                num = f * (self.k1 + 1)
                den = f + self.k1 * (1 - self.b + self.b * doc_len[i] / avgdl)
                s += idf * num / den
            scores.append(s)

        return self._normalise_list(scores)

    # ------------------------------------------------------------------
    # Normalisation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_vector(t: "torch.Tensor") -> "torch.Tensor":
        """Min-max normalise a 1-D tensor to [0, 1]."""
        lo, hi = t.min(), t.max()
        if (hi - lo).abs() < 1e-12:
            return t.clamp(0.0, 1.0)
        return (t - lo) / (hi - lo)

    @staticmethod
    def _normalise_matrix(t: "torch.Tensor") -> "torch.Tensor":
        """Row-wise min-max normalise a 2-D tensor to [0, 1]."""
        lo = t.min(dim=1, keepdim=True).values
        hi = t.max(dim=1, keepdim=True).values
        denom = (hi - lo).clamp(min=1e-12)
        return (t - lo) / denom

    @staticmethod
    def _normalise_list(scores: list[float]) -> list[float]:
        """Min-max normalise a list of floats to [0, 1]."""
        if not scores:
            return scores
        lo, hi = min(scores), max(scores)
        if hi - lo < 1e-12:
            return [min(1.0, max(0.0, s)) for s in scores]
        return [(s - lo) / (hi - lo) for s in scores]
