"""Text metrics tool retained from the original personal assistant."""

import re


def text_analyzer(text: str) -> dict:
    """Count characters, words, and sentences in supplied text."""
    return {
        "characters": len(text),
        "words": len(re.findall(r"\b[\w'-]+\b", text)),
        "sentences": len([part for part in re.split(r"[.!?]+", text) if part.strip()]),
    }
