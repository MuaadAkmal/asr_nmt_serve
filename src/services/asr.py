"""ASR (Automatic Speech Recognition) service using Whisper and Omni models."""

import os
import tempfile
import threading
from dataclasses import dataclass
from typing import Optional

import torch

from src.config import get_settings

settings = get_settings()


@dataclass
class ASRResult:
    """Result from ASR processing."""

    text: str
    detected_language: Optional[str]
    language_probability: Optional[float]
    model_used: str
    segments: Optional[list[dict]] = None


class WhisperASR:
    """OpenAI Whisper ASR model wrapper."""

    _instance = None
    _lock = threading.Lock()
    _model = None

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def _load_model(self):
        """Lazy load the Whisper model."""
        if self._model is None:
            import whisper

            device = settings.whisper_device
            if device == "cuda" and not torch.cuda.is_available():
                device = "cpu"

            self._model = whisper.load_model(
                settings.whisper_model_size,
                device=device,
            )
        return self._model

    def transcribe(
        self,
        audio_data: bytes,
        language: Optional[str] = None,
        task: str = "transcribe",
    ) -> ASRResult:
        """
        Transcribe audio using Whisper.

        Args:
            audio_data: Raw audio bytes
            language: Source language code (None for auto-detect)
            task: "transcribe" or "translate" (translate to English)

        Returns:
            ASRResult with transcription
        """
        model = self._load_model()

        # Write audio to temp file (Whisper needs file path)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_data)
            temp_path = f.name

        try:
            # Build transcribe options
            options = {
                "task": task,
                "verbose": False,
            }

            if language:
                # Map our language codes to Whisper's
                lang_map = {
                    "en": "english",
                    "hi": "hindi",
                    "kn": "kannada",
                    "mr": "marathi",
                    "te": "telugu",
                    "ml": "malayalam",
                    "ta": "tamil",
                }
                options["language"] = lang_map.get(language, language)

            result = model.transcribe(temp_path, **options)

            return ASRResult(
                text=result["text"].strip(),
                detected_language=result.get("language"),
                language_probability=result.get("language_probability"),
                model_used="whisper",
                segments=[
                    {
                        "start": seg["start"],
                        "end": seg["end"],
                        "text": seg["text"],
                    }
                    for seg in result.get("segments", [])
                ],
            )

        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def detect_language(self, audio_data: bytes) -> tuple[str, float]:
        """
        Detect language from audio.

        Returns:
            Tuple of (language_code, probability)
        """
        model = self._load_model()

        # Write to temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_data)
            temp_path = f.name

        try:
            import whisper

            # Load audio and pad/trim to 30 seconds
            audio = whisper.load_audio(temp_path)
            audio = whisper.pad_or_trim(audio)

            # Make log-Mel spectrogram
            mel = whisper.log_mel_spectrogram(audio).to(model.device)

            # Detect language
            _, probs = model.detect_language(mel)
            detected_lang = max(probs, key=probs.get)

            return detected_lang, probs[detected_lang]

        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


class OmniASR:
    """
    FB Omni / Seamless ASR for rare languages.
    This is a placeholder - implement based on your specific Omni setup.
    """

    _instance = None
    _lock = threading.Lock()
    _model = None

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def _load_model(self):
        """Load the Omni model."""
        if self._model is None:
            # TODO: Implement actual Omni model loading
            # Example for seamless_communication:
            # from seamless_communication.models.inference import Translator
            # self._model = Translator("seamlessM4T_large", ...)
            pass
        return self._model

    def transcribe(
        self,
        audio_data: bytes,
        language: Optional[str] = None,
    ) -> ASRResult:
        """
        Transcribe audio using Omni/Seamless model.

        This is a placeholder implementation.
        Replace with actual Omni/Seamless integration.
        """
        # TODO: Implement actual Omni transcription
        # For now, return a placeholder

        # Example implementation:
        # model = self._load_model()
        # with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        #     f.write(audio_data)
        #     temp_path = f.name
        # try:
        #     result = model.transcribe(temp_path, src_lang=language)
        #     return ASRResult(text=result.text, ...)
        # finally:
        #     os.unlink(temp_path)

        raise NotImplementedError(
            "Omni ASR not yet implemented. Please add your Omni/Seamless integration."
        )


class ASRService:
    """Main ASR service that routes to appropriate model."""

    def __init__(self):
        self.whisper = WhisperASR()
        self.omni = OmniASR()
        self._semaphore_whisper = threading.Semaphore(settings.whisper_concurrency)
        self._semaphore_omni = threading.Semaphore(settings.omni_concurrency)

    def transcribe(
        self,
        audio_data: bytes,
        language: Optional[str] = None,
        force_model: Optional[str] = None,
    ) -> ASRResult:
        """
        Transcribe audio, automatically selecting the best model.

        Args:
            audio_data: Raw audio bytes
            language: Source language (None for auto-detect)
            force_model: Force specific model ("whisper" or "omni")

        Returns:
            ASRResult
        """
        # Determine which model to use
        use_whisper = True

        if force_model == "omni":
            use_whisper = False
        elif force_model == "whisper":
            use_whisper = True
        elif language:
            # Use Whisper for primary languages
            use_whisper = language.lower() in settings.primary_languages

        if use_whisper:
            with self._semaphore_whisper:
                return self.whisper.transcribe(audio_data, language)
        else:
            with self._semaphore_omni:
                return self.omni.transcribe(audio_data, language)

    def transcribe_with_detection(
        self,
        audio_data: bytes,
    ) -> ASRResult:
        """
        Transcribe with automatic language detection.
        Falls back to Omni if detected language is not in primary set.
        """
        with self._semaphore_whisper:
            # First, detect language
            detected_lang, prob = self.whisper.detect_language(audio_data)

            # Map Whisper language codes to our codes
            lang_map = {
                "english": "en",
                "hindi": "hi",
                "kannada": "kn",
                "marathi": "mr",
                "telugu": "te",
                "malayalam": "ml",
                "tamil": "ta",
            }
            normalized_lang = lang_map.get(detected_lang, detected_lang)

            # If primary language, use Whisper
            if normalized_lang in settings.primary_languages:
                result = self.whisper.transcribe(audio_data, normalized_lang)
                result.detected_language = normalized_lang
                return result

        # Fall back to Omni for rare languages
        with self._semaphore_omni:
            try:
                result = self.omni.transcribe(audio_data, normalized_lang)
                result.detected_language = normalized_lang
                return result
            except NotImplementedError:
                # If Omni not available, still use Whisper
                with self._semaphore_whisper:
                    result = self.whisper.transcribe(audio_data, None)
                    result.detected_language = normalized_lang
                    return result


# Singleton instance
asr_service = ASRService()
