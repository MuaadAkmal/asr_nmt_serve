"""Script to test the ASR service."""

import asyncio
import sys

sys.path.insert(0, ".")


def test_whisper():
    """Test Whisper ASR."""
    from src.services.asr import asr_service

    # Create a simple test audio (you'd replace with real audio)
    print("Testing Whisper ASR...")
    print("Note: You need to provide actual audio data for real testing")

    # Example: Read a test audio file
    # with open("test_audio.wav", "rb") as f:
    #     audio_data = f.read()
    # result = asr_service.transcribe(audio_data, language="en")
    # print(f"Transcription: {result.text}")
    # print(f"Detected language: {result.detected_language}")
    # print(f"Model used: {result.model_used}")

    print("Whisper service initialized successfully!")


def test_nmt():
    """Test NMT service."""
    from src.services.nmt import nmt_service

    print("Testing NMT service...")
    print("Supported language pairs:", nmt_service.get_supported_pairs()[:5], "...")

    # Note: Actual translation requires model implementation
    print("NMT service initialized successfully!")


if __name__ == "__main__":
    test_whisper()
    test_nmt()
