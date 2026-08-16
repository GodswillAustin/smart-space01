import os
import asyncio
from io import BytesIO
import aiofiles
from pathlib import Path
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs.play import play
from fishaudio import AsyncFishAudio
from fishaudio.utils import play, save
import subprocess

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

            return transcription

        except Exception as e:
            print(f"ElevenLabs failed: {e}")

            return await self.FishAudioSTT()
        
class TTS():
    def __init__(self, user_id, LLMresponce):
        self.user_id = user_id
        self.text = LLMresponce

        self.user_dir = Path(f"AudioClips/{self.user_id}")
        file = [
            int(f.stem.replace("AudioClip", ""))
            for f in self.user_dir.glob("AudioClip*.ogg")
        ]
        self.fileNum = max(file, default=0) + 1

    async def FishAudioTTS(self):
        audio_path = self.user_dir / f"AudioClip{self.fileNum}.ogg"
        audio = await fishaudio.tts.convert(
            text=self.text,
            reference_id="802e3bc2b27e49c2995d23ef70e6ac89"
        )
        
        save(audio, str(audio_path))

        return audio_path

    def ElevenLabsTTS(self):
        audio_path = self.user_dir / f"AudioClip{self.fileNum}.mp3"
        audio = elevenlabs.text_to_speech.convert(
            text=self.text,
            voice_id="cgSgspJ2msm6clMCkdW9",
            model_id="eleven_v3",
            output_format="mp3_44100_128",
        )

        voices = {
            "male":{
                "muyiwa": "r9DosIwaFvTjhC7gp1d2",
                "liam": "TX3LPaxmHKxFdv7VOQHJ",
                "will": "bIHbv24MWmeRgasZH58o",
                "george": "JBFqnCBsd6RMkjVDRZzb"
            },
            "female": {
                "tobi": "D9xwB6HNBJ9h4YvQFWuE",
                "rho": "v411uyEKbaj63pTJHHbK",
                "jessica": "cgSgspJ2msm6clMCkdW9",
                "matilda": "XrExE9yKIg1WjnnlVkGX",
            }
        }
                

        with open(audio_path, "wb") as f:
            for chunk in audio:
                if chunk:
                    f.write(chunk)
        return audio_path
    
    def Piper(self):
        audio_path = self.user_dir / f"AudioClip{self.fileNum}.wav"
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
            path = self.ElevenLabsTTS()
            
            return path, 'Audio'

        except Exception as e:
            print(f"ElevenLabs failed: {e}")
            path = await self.FishAudioTTS()

            return path, 'voice'
        
        except Exception as e:
            print(f"FishAudio failed: {e}")
            path = await self.Piper()

            return path, 'voice'
