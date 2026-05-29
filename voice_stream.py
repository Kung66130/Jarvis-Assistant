from __future__ import annotations

import re


SENTENCE_BOUNDARIES = ".!?。！？\n"
SOFT_BOUNDARIES = ",;:，、 "


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _find_split_index(text: str, max_chars: int) -> int:
    if len(text) <= max_chars:
        return len(text)

    for index in range(max_chars, 0, -1):
        if text[index - 1] in SENTENCE_BOUNDARIES + SOFT_BOUNDARIES:
            return index
    return max_chars


def split_for_speech(text: str, max_chars: int = 90) -> list[str]:
    remaining = _normalize_whitespace(text)
    if not remaining:
        return []

    segments: list[str] = []
    while remaining:
        boundary_index = None
        for index, char in enumerate(remaining[:max_chars], start=1):
            if char in SENTENCE_BOUNDARIES:
                boundary_index = index

        split_index = boundary_index or _find_split_index(remaining, max_chars)
        segment = remaining[:split_index].strip()
        if segment:
            segments.append(segment)
        remaining = remaining[split_index:].strip()

    return segments


class StreamingSegmentBuffer:
    def __init__(self, max_chars: int = 90):
        self.max_chars = max_chars
        self._buffer = ""

    def push(self, fragment: str) -> list[str]:
        self._buffer += fragment or ""
        emitted: list[str] = []

        while True:
            candidate = _normalize_whitespace(self._buffer)
            if not candidate:
                self._buffer = ""
                break

            sentence_index = None
            for index, char in enumerate(candidate, start=1):
                if char in SENTENCE_BOUNDARIES:
                    sentence_index = index
                    break

            if sentence_index is not None:
                emitted.append(candidate[:sentence_index].strip())
                self._buffer = candidate[sentence_index:].lstrip()
                continue

            if len(candidate) > self.max_chars:
                split_index = _find_split_index(candidate, self.max_chars)
                emitted.append(candidate[:split_index].strip())
                self._buffer = candidate[split_index:].lstrip()
                continue

            self._buffer = candidate
            break

        return [segment for segment in emitted if segment]

    def flush(self) -> str | None:
        remainder = _normalize_whitespace(self._buffer)
        self._buffer = ""
        return remainder or None
