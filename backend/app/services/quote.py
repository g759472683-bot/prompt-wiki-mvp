from __future__ import annotations

import re


def find_quote(text: str, quote: str) -> tuple[str | None, int, int]:
    """Locate a quote in a block.

    Contract requires verbatim matching; PDF extraction often introduces line
    breaks, so a whitespace-normalized pass is kept as a fallback and reported
    explicitly as match_type="normalized".
    """
    quote = quote.strip()
    if not quote:
        return None, -1, -1

    start = text.find(quote)
    if start >= 0:
        return "exact", start, start + len(quote)

    tokens = [token for token in re.split(r"\s+", quote) if token]
    if not tokens:
        return None, -1, -1
    pattern = r"\s+".join(re.escape(token) for token in tokens)
    match = re.search(pattern, text)
    if match:
        return "normalized", match.start(), match.end()
    return None, -1, -1
