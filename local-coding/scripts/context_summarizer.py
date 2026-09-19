"""Client-side context summarization for Bonsai-2 100K context management.

When conversation exceeds max context, this function compresses old context
by having the model summarize it, preserving key points while freeing
context window space.

Usage:
    from context_summarizer import truncate_context
    
    conversation = truncate_context(conversation, max_tokens=100000, keep_recent=4000, model=llm)
"""

import logging
import re

logger = logging.getLogger(__name__)


def _count_tokens(text: str) -> int:
    """Rough token estimation: ~4 chars per token."""
    return max(1, len(text) // 4)


def _split_into_chunks(text: str, max_chars: int = 8000) -> list:
    """Split text into chunks not exceeding max_chars."""
    if _count_tokens(text) <= max_chars // 4:
        return [text]
    
    chunks = []
    sentences = re.split(r'[.!?] +', text)
    chunk = ""
    for sentence in sentences:
        test = (chunk + ". " + sentence if chunk else sentence).strip()
        if _count_tokens(test) <= max_chars // 4:
            chunk = test
        else:
            if chunk:
                chunks.append(chunk)
            chunk = sentence
    if chunk:
        chunks.append(chunk)
    return chunks


def truncate_context(
    conversation: str,
    max_tokens: int = 100000,
    keep_recent: int = 4000,
    model=None,
    model_name: str = "unknown"
) -> str:
    """Truncate conversation to max_tokens using summarization of old context.
    
    Args:
        conversation: Full conversation text
        max_tokens: Maximum total tokens allowed
        keep_recent: Recent tokens to preserve verbatim
        model: Optional LLM instance for summarization (if None, just truncate)
        model_name: Name for logging purposes
    
    Returns:
        Truncated conversation within max_tokens
    """
    max_chars = max_tokens * 4
    keep_chars = keep_recent * 4
    
    if _count_tokens(conversation) <= max_tokens:
        return conversation
    
    logger.info(
        f"Context exceeds {max_tokens} tokens ({_count_tokens(conversation)} actual). "
        f"Truncating with {keep_recent} recent keep."
    )
    
    # Separate recent portion
    recent_text = conversation[-keep_chars:] if len(conversation) > keep_chars else ""
    old_text = conversation[:-keep_chars] if len(conversation) > keep_chars else ""
    
    if not old_text:
        # Just keep recent, drop everything else
        result = recent_text
        logger.info(f"Dropped {_count_tokens(old_text)} tokens of old context, keeping {_count_tokens(recent_text)} recent")
        return result
    
    # Summarize old context in chunks
    chunks = _split_into_chunks(old_text, max_chars=8000)
    summarized_parts = []
    
    for i, chunk in enumerate(chunks):
        # Use model summarization if available, otherwise extractive summary
        if model is not None:
            try:
                summary = model(
                    f"Summarize this text concisely, keeping all key information, names, dates, and decisions. "
                    f"Text: {chunk}",
                    temperature=0,
                    max_tokens=512
                )
                if summary and isinstance(summary, str) and len(summary.strip()) > 10:
                    summarized_parts.append(summary.strip())
                    continue
            except Exception as e:
                logger.warning(f"Model summarization failed for chunk {i}: {e}")
        
        # Fallback: extractive summary - take first and last sentences + key mids
        sentences = re.split(r'[.!?]+', chunk)
        sentences = [s.strip() for s in sentences if s.strip()]
        if len(sentences) <= 2:
            summarized_parts.append(chunk)
        else:
            # Keep first, last, and every ~3rd middle sentence
            kept = [sentences[0], sentences[-1]]
            for j in range(1, len(sentences) - 1):
                if j % 3 == 0:
                    kept.append(sentences[j])
            summarized_parts.append('. '.join(kept) + '.')
    
    summarized_old = ' '.join(summarized_parts)
    
    # Combine: summarized old + recent
    result = summarized_old + ' ' + recent_text if summarized_old else recent_text
    
    actual_tokens = _count_tokens(result)
    dropped_tokens = _count_tokens(old_text) - _count_tokens(summarized_old) if summarized_old else _count_tokens(old_text)
    
    logger.info(
        f"Context truncated: dropped {dropped_tokens} tokens, "
        f"kept {actual_tokens} tokens (summarized {len(chunks)} old chunks, "
        f"kept {_count_tokens(recent_text)} recent)"
    )
    
    return result


# Convenience function for standalone use
if __name__ == "__main__":
    import sys
    
    conv = sys.argv[1] if len(sys.argv) > 1 else """User: Hello how are you
Assistant: I'm doing well, thank you for asking! How can I help you today?
User: I'm working on a project about machine learning and I was wondering if you could help me understand the basics
Assistant: Machine learning is a field of computer science that gives computers the ability to learn without being explicitly programmed...
User: That's helpful. Can you also tell me about neural networks?
Assistant: Neural networks are computing systems inspired by the biological neural networks that constitute animal brains.
User: Great, and what about deep learning?
Assistant: Deep learning is a subset of machine learning that uses neural networks with many layers (hence "deep")."""
    
    result = truncate_context(conv, max_tokens=100000, keep_recent=4000)
    print(f"Input tokens: {__import__('re').len(conv) // 4}")
    print(f"Output tokens: {__import__('re').len(result) // 4}")
    print(f"Preserved recent:\n{result[-2000:]}")