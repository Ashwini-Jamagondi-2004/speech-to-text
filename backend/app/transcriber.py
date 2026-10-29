"""Thin wrapper around faster-whisper (open source, runs fully self-hosted on CPU)."""
import os
import threading
from typing import Optional, Tuple

import numpy as np

SAMPLE_RATE = 16000
MODEL_SIZE = os.getenv("WHISPER_MODEL", "base")  # tiny | base | small | medium | large-v3
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")

_model = None
_lock = threading.Lock()

# A romanised Hindi+English prompt nudges Whisper to write Hinglish in Latin script
HINGLISH_PROMPT = "Namaste, kaise ho? Main theek hoon. Aaj meeting hai, let's start the project discussion."


def load_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel(MODEL_SIZE, device="cpu", compute_type=COMPUTE_TYPE)
    return _model


def transcribe(audio: np.ndarray, mode: str = "auto") -> Tuple[str, Optional[str]]:
    """audio: float32 mono @16kHz in [-1, 1].  mode: auto | en | hi | hinglish"""
    language, prompt = None, None
    if mode in ("en", "hi"):
        language = mode
    elif mode == "hinglish":
        language, prompt = "hi", HINGLISH_PROMPT
    elif mode == "auto":
        prompt = HINGLISH_PROMPT

    model = load_model()
    with _lock:  # one inference at a time on a small CPU box
        segments, info = model.transcribe(
            audio,
            language=language,
            beam_size=1,
            vad_filter=True,
            initial_prompt=prompt,
            condition_on_previous_text=False,
        )
        text = " ".join(s.text.strip() for s in segments).strip()
    return text, info.language
