from __future__ import annotations

import queue
import threading
from typing import Iterable

from pro_speak import speak_text


class SegmentSpeaker:
    def __init__(self, voice: str = "niwat"):
        self._voice = voice
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._stop_event = threading.Event()
        self._busy_event = threading.Event()
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._started = False
        self._lock = threading.Lock()

    def start(self) -> None:
        if not self._started:
            self._worker.start()
            self._started = True

    def set_voice(self, voice: str) -> None:
        with self._lock:
            self._voice = voice or "niwat"

    def enqueue(self, text: str) -> None:
        cleaned = (text or "").strip()
        if not cleaned:
            return
        self.start()
        self._busy_event.set()
        self._queue.put(cleaned)

    def extend(self, segments: Iterable[str]) -> None:
        for segment in segments:
            self.enqueue(segment)

    def finish(self) -> None:
        self.start()
        self._queue.put(None)

    def cancel(self) -> None:
        self._stop_event.set()
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        self._queue.put(None)

    def join(self, timeout: float | None = None) -> None:
        if self._started:
            self._worker.join(timeout=timeout)

    def is_busy(self) -> bool:
        return self._busy_event.is_set()

    def stop_event(self) -> threading.Event:
        return self._stop_event

    def _run(self) -> None:
        try:
            while True:
                segment = self._queue.get()
                if segment is None:
                    return
                with self._lock:
                    voice = self._voice
                try:
                    speak_text(segment, voice, stop_event=self._stop_event)
                except Exception:
                    self._busy_event.clear()
                    return
                if self._queue.empty():
                    self._busy_event.clear()
                if self._stop_event.is_set():
                    self._busy_event.clear()
                    return
        finally:
            self._busy_event.clear()
