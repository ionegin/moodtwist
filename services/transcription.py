from groq import Groq
from config import GROQ_API_KEY

# Инициализируем клиент только если есть ключ
client = None
if GROQ_API_KEY:
    client = Groq(api_key=GROQ_API_KEY)

import asyncio

async def transcribe_voice(file_path: str):
    if not client:
        raise ValueError("GROQ_API_KEY не установлен")
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _transcribe_sync, file_path)

def _transcribe_sync(file_path: str):
    with open(file_path, "rb") as f:
        transcription = client.audio.transcriptions.create(
            file=(file_path, f.read()),
            model="whisper-large-v3",
            response_format="text",
            language="ru"
        )
    return transcription