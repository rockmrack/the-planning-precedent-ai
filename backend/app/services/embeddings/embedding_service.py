"""
Embedding Service for Planning Documents
Handles text chunking, embedding generation, and vector storage

Uses OpenAI's text-embedding-3-large for high-quality semantic search
across planning decisions and legal terminology.
"""

import asyncio
import hashlib
import re
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass

import tiktoken
from openai import AsyncOpenAI
import structlog

from app.core.config import settings
from app.models.planning import DocumentChunk

logger = structlog.get_logger(__name__)


@dataclass
class TextChunk:
    """A chunk of text ready for embedding"""
    text: str
    token_count: int
    chunk_index: int
    metadata: Dict[str, Any]


class EmbeddingService:
    """
    Service for generating embeddings from planning documents.

    Features:
    - Intelligent text chunking that respects document structure
    - Semantic preservation of planning-specific content
    - Batch processing for efficiency
    - Caching to avoid redundant API calls
    """

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_embedding_model
        self.dimensions = settings.embedding_dimensions

        # Tokeniser for the embedding model
        self.tokeniser = tiktoken.get_encoding("cl100k_base")

        # Chunk settings
        self.chunk_size = settings.chunk_size
        self.chunk_overlap = settings.chunk_overlap
        self.max_chunks = settings.max_chunks_per_document

        # Simple in-memory cache for embeddings
        self._cache: Dict[str, List[float]] = {}

    async def generate_embedding(
        self,
        text: str,
        use_cache: bool = True
    ) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed
            use_cache: Whether to use cached embeddings

        Returns:
            List of floats representing the embedding vector
        """
        if not text or not text.strip():
            raise ValueError("Cannot generate embedding for empty text")

        # Check cache
        cache_key = self._get_cache_key(text)
        if use_cache and cache_key in self._cache:
            logger.debug("embedding_cache_hit", key=cache_key[:16])
            return self._cache[cache_key]

        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=text,
                dimensions=self.dimensions
            )

            embedding = response.data[0].embedding

            # Cache the result
            if use_cache:
                self._cache[cache_key] = embedding

            logger.debug(
                "embedding_generated",
                model=self.model,
                dimensions=len(embedding)
            )

            return embedding

        except Exception as e:
            logger.error("embedding_generation_failed", error=str(e))
            raise

    async def generate_embeddings_batch(
        self,
        texts: List[str],
        batch_size: int = 100
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batches.

        Args:
            texts: List of texts to embed
            batch_size: Maximum texts per API call

        Returns:
            List of embedding vectors
        """
        embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            # Filter out empty texts
            valid_batch = [(j, t) for j, t in enumerate(batch) if t and t.strip()]

            if not valid_batch:
                # Add empty embeddings for empty texts
                embeddings.extend([[] for _ in batch])
                continue

            try:
                response = await self.client.embeddings.create(
                    model=self.model,
                    input=[t for _, t in valid_batch],
                    dimensions=self.dimensions
                )

                # Map embeddings back to original positions
                batch_embeddings = [[] for _ in batch]
                for idx, (original_idx, _) in enumerate(valid_batch):
                    batch_embeddings[original_idx] = response.data[idx].embedding

                embeddings.extend(batch_embeddings)

                logger.info(
                    "batch_embeddings_generated",
                    batch_num=i // batch_size + 1,
                    count=len(valid_batch)
                )

            except Exception as e:
                logger.error("batch_embedding_failed", error=str(e))
                # Return empty embeddings for failed batch
                embeddings.extend([[] for _ in batch])

            # Rate limiting
            await asyncio.sleep(0.1)

        return embeddings

    def chunk_document(
        self,
        text: str,
        preserve_sections: bool = True
    ) -> List[TextChunk]:
        """
        Split a document into chunks suitable for embedding.

        Args:
            text: Full document text
            preserve_sections: Try to keep section boundaries intact

        Returns:
            List of TextChunk objects
        """
        if not text or not text.strip():
            return []

        # Clean the text
        text = self._preprocess_text(text)

        # Split into sections first if requested
        if preserve_sections:
            sections = self._split_into_sections(text)
        else:
            sections = [text]

        chunks = []
        chunk_index = 0

        for section_idx, section in enumerate(sections):
            section_chunks = self._chunk_section(
                section,
                start_index=chunk_index,
                section_number=section_idx
            )
            chunks.extend(section_chunks)
            chunk_index += len(section_chunks)

            if chunk_index >= self.max_chunks:
                logger.warning(
                    "max_chunks_reached",
                    max=self.max_chunks,
                    text_length=len(text)
                )
                break

        logger.info(
            "document_chunked",
            total_chunks=len(chunks),
            total_tokens=sum(c.token_count for c in chunks)
        )

        return chunks

    def _preprocess_text(self, text: str) -> str:
        """Clean and normalise text before chunking"""
        # Remove excessive whitespace
        text = re.sub(r"\s+", " ", text)

        # Fix common formatting issues
        text = re.sub(r"([.!?])\s*([A-Z])", r"\1\n\n\2", text)

        # Ensure paragraph breaks
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

    def _split_into_sections(self, text: str) -> List[str]:
        """Split text into logical sections based on headings"""
        # Common section patterns in planning documents
        section_patterns = [
            r"\n(?=[A-Z][A-Z\s]+\n)",  # ALL CAPS headings
            r"\n(?=\d+\.\s+[A-Z])",  # Numbered sections
            r"\n(?=(?:Proposal|Assessment|Conclusion|Recommendation|Conditions))",
        ]

        # Try each pattern
        for pattern in section_patterns:
            sections = re.split(pattern, text)
            if len(sections) > 1:
                # Filter out very small sections
                sections = [s for s in sections if len(s.strip()) > 100]
                if sections:
                    return sections

        # If no sections found, return as single section
        return [text]

    def _chunk_section(
        self,
        text: str,
        start_index: int = 0,
        section_number: int = 0
    ) -> List[TextChunk]:
        """Chunk a section using token-aware splitting"""
        chunks = []
        current_chunk = []
        current_tokens = 0

        # Split into sentences
        sentences = self._split_sentences(text)

        for sentence in sentences:
            sentence_tokens = len(self.tokeniser.encode(sentence))

            # If single sentence is too long, split it
            if sentence_tokens > self.chunk_size:
                # First, add current chunk if not empty
                if current_chunk:
                    chunk_text = " ".join(current_chunk)
                    chunks.append(TextChunk(
                        text=chunk_text,
                        token_count=current_tokens,
                        chunk_index=start_index + len(chunks),
                        metadata={
                            "section": section_number,
                            "type": "regular"
                        }
                    ))
                    current_chunk = []
                    current_tokens = 0

                # Split long sentence into smaller parts
                sub_chunks = self._split_long_text(sentence)
                for sub in sub_chunks:
                    sub_tokens = len(self.tokeniser.encode(sub))
                    chunks.append(TextChunk(
                        text=sub,
                        token_count=sub_tokens,
                        chunk_index=start_index + len(chunks),
                        metadata={
                            "section": section_number,
                            "type": "split_sentence"
                        }
                    ))
                continue

            # Check if adding this sentence exceeds chunk size
            if current_tokens + sentence_tokens > self.chunk_size:
                # Save current chunk
                if current_chunk:
                    chunk_text = " ".join(current_chunk)
                    chunks.append(TextChunk(
                        text=chunk_text,
                        token_count=current_tokens,
                        chunk_index=start_index + len(chunks),
                        metadata={
                            "section": section_number,
                            "type": "regular"
                        }
                    ))

                # Start new chunk with overlap
                overlap_sentences = self._get_overlap_sentences(
                    current_chunk,
                    self.chunk_overlap
                )
                current_chunk = overlap_sentences + [sentence]
                current_tokens = sum(
                    len(self.tokeniser.encode(s)) for s in current_chunk
                )
            else:
                current_chunk.append(sentence)
                current_tokens += sentence_tokens

        # Don't forget the last chunk
        if current_chunk:
            chunk_text = " ".join(current_chunk)
            chunks.append(TextChunk(
                text=chunk_text,
                token_count=current_tokens,
                chunk_index=start_index + len(chunks),
                metadata={
                    "section": section_number,
                    "type": "regular"
                }
            ))

        return chunks

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        # Simple sentence splitting - can be improved with spacy/nltk
        sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text)
        return [s.strip() for s in sentences if s.strip()]

    def _split_long_text(self, text: str) -> List[str]:
        """Split text that's too long for a single chunk"""
        words = text.split()
        chunks = []
        current = []
        current_tokens = 0

        for word in words:
            word_tokens = len(self.tokeniser.encode(word))
            if current_tokens + word_tokens > self.chunk_size - 50:
                if current:
                    chunks.append(" ".join(current))
                current = [word]
                current_tokens = word_tokens
            else:
                current.append(word)
                current_tokens += word_tokens

        if current:
            chunks.append(" ".join(current))

        return chunks

    def _get_overlap_sentences(
        self,
        sentences: List[str],
        target_tokens: int
    ) -> List[str]:
        """Get sentences for overlap from the end of a chunk"""
        overlap = []
        tokens = 0

        for sentence in reversed(sentences):
            sentence_tokens = len(self.tokeniser.encode(sentence))
            if tokens + sentence_tokens <= target_tokens:
                overlap.insert(0, sentence)
                tokens += sentence_tokens
            else:
                break

        return overlap

    def _get_cache_key(self, text: str) -> str:
        """Generate a cache key for text using SHA256 (secure hash)"""
        return hashlib.sha256(text.encode()).hexdigest()

    async def embed_chunks(
        self,
        chunks: List[TextChunk]
    ) -> List[DocumentChunk]:
        """
        Generate embeddings for all chunks and return DocumentChunk objects.

        Args:
            chunks: List of TextChunk objects

        Returns:
            List of DocumentChunk objects with embeddings
        """
        texts = [chunk.text for chunk in chunks]
        embeddings = await self.generate_embeddings_batch(texts)

        document_chunks = []
        for chunk, embedding in zip(chunks, embeddings):
            doc_chunk = DocumentChunk(
                decision_id=0,  # Will be set when saving
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                token_count=chunk.token_count,
                embedding=embedding if embedding else None,
                metadata=chunk.metadata
            )
            document_chunks.append(doc_chunk)

        return document_chunks

    def count_tokens(self, text: str) -> int:
        """Count tokens in a text"""
        return len(self.tokeniser.encode(text))

    def truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """Truncate text to a maximum number of tokens"""
        tokens = self.tokeniser.encode(text)
        if len(tokens) <= max_tokens:
            return text
        return self.tokeniser.decode(tokens[:max_tokens])
