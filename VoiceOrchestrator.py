import os
from io import BytesIO
import aiofiles
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs.play import play
from fishaudio import AsyncFishAudio
from fishaudio.utils import play, save
import subprocess
import logging

logger = logging.getLogger(__name__)

load_dotenv()

elevenlabs = ElevenLabs(
  api_key=os.getenv("ELEVENLABS")
)

fishaudio = AsyncFishAudio(
  api_key=os.getenv("FISHAUDIO")
)

class STT:
  def __init__(self, audio_path):
    self.audio_path = audio_path

  async def ElevenLabsSTT(self):
    async with aiofiles.open(self.audio_path, "rb") as f:
      audio_bytes = await f.read()

    audio_data = BytesIO(audio_bytes)

    transcription = elevenlabs.speech_to_text.convert(
      file=audio_data,
      model_id="scribe_v2",
      tag_audio_events=True,
      language_code="eng",
      diarize=True,
    )

    return transcription.text

  async def FishAudioSTT(self):
    async with aiofiles.open(self.audio_path, "rb") as f:
      audio = await f.read()

      result = await fishaudio.asr.transcribe(
        audio=audio,
        language="en",
      )

      return result.text

  async def transcribe(self):
    try:
      transcription = await self.ElevenLabsSTT()
    except Exception:
      logger.exception("ElevenLabs transcription failed")
      transcription =  await self.FishAudioSTT()
    except Exception:
      logger.exception("ElevenLabs transcription failed")
    return transcription
        
class TTS():
  def __init__(self, user_id, voice_id, LLMresponce):
    self.user_id = user_id
    self.text = LLMresponce
    self.voice_id = voice_id
    # self.tts_semaphore = asyncio.Semaphore(3)

    self.user_dir = Path("audio_db") / str(self.user_id)
    self.user_dir.mkdir(parents=True, exist_ok=True)

    file = [
      int(f.stem.replace("voice_note", ""))
      for f in self.user_dir.glob("voice_note*.ogg")
    ]
    self.fileNum = max(file, default=0) + 1

  async def FishAudioTTS(self):
    audio_path = self.user_dir / f"voice_note{self.fileNum}.ogg"
    audio = await fishaudio.tts.convert(
      text=self.text,
      reference_id="802e3bc2b27e49c2995d23ef70e6ac89"
    )
        
    save(audio, str(audio_path))
    return audio_path

  def ElevenLabsTTS(self):
    voices = {
      "iv01": "r9DosIwaFvTjhC7gp1d2",
      "iv02": "eSsKYR3BasKvhJghjsCX",
      "iv03": "Obry8zWnqii5oX5Qsllx",
      "iv04": "2vbhUP8zyKg4dEZaTWGn",
      "iv05": "NIkIuJZ8oQMuKZqwKtnm",
      "iv06": "49GHemjSs7Dp4fi77m6O",
      "iv07": "bIHbv24MWmeRgasZH58o",
      "iv08": "nzFihrBIvB34imQBuxub",
      "iv09": "7YaUDeaStRuoYg3FKsmU",
      "iv10": "k56mKR2rds72oUAqTsob",
      "iv11": "cgSgspJ2msm6clMCkdW9",
      "iv12": "0muxiGNHAVvmM1qWRtyV",
      "iv13": "1vwA0eYRcS7JdkJiCIwH",
      "iv14": "GBJyJih8mGoasC7OSR50",
      "iv15": "d5QfMetkf8n1aenR1dOq",
      "iv16": "C8uRRxxNZH0vRqJbVFJy"
    }

    audio_path = self.user_dir / f"voice_note{self.fileNum}.opus"
    audio = elevenlabs.text_to_speech.convert(
      text=self.text,
      voice_id=voices.get(self.voice_id, "iv02"),
      model_id="eleven_v3",
      output_format="opus_48000_128"
    )
    with open(audio_path, "wb") as f:
      for chunk in audio:
        if chunk:
          f.write(chunk)

    ogg_path = audio_path.with_suffix(".ogg")

    subprocess.run(
      [
        "ffmpeg",
        "-y",
        "-i", str(audio_path),
        "-c:a", "copy",
        str(ogg_path)
      ],
      stdout=subprocess.DEVNULL,
      stderr=subprocess.PIPE,
      check=True
    )
    audio_path.unlink()
    return ogg_path
    
  async def Piper(self):
    audio_path = self.user_dir / f"voice_note{self.fileNum}.wav"
    subprocess.run(
      [
        "piper",
        "--model", "en_US-amy-medium",
        "--output_file", audio_path,
      ],
      input=self.text.encode("utf-8"),
    )
    return audio_path

  async def VoicePath(self):
    try:
      #  async with self.tts_semaphore:
      #      path = await asyncio.to_thread(self.ElevenLabsTTS)
      path = await asyncio.to_thread(self.ElevenLabsTTS)
    except Exception as e:
      print(f"ElevenLabs failed: {e}")
      path = await self.FishAudioTTS()
    except Exception as e:
      print(f"FishAudio failed: {e}")
      path = await self.Piper()
    return path
