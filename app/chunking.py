"""Text chunking kept dependency-free so it can be unit tested in isolation."""


def chunk(text: str, size: int = 800, overlap: int = 100) -> list[str]:
    if size <= overlap:
        raise ValueError("size must be greater than overlap")
    text = text.strip()
    if not text:
        return []
    step = size - overlap
    return [text[i:i + size] for i in range(0, len(text), step) if text[i:i + size].strip()]
