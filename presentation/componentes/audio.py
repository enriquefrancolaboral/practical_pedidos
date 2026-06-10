# presentation/componentes/audio.py
import edge_tts
import asyncio
import tempfile
import os
import ctypes
import threading
import time
import winsound
import struct
import math

VOZ_TOMAS = "es-AR-TomasNeural"

_audio_lock = threading.Lock()


def _generar_wav(frecuencia: float, duracion_ms: int,
                  volumen: float = 0.8, sample_rate: int = 44100) -> bytes:
    """Genera un tono sinusoidal como WAV en memoria (con fade in/out para evitar clicks)."""
    num_samples = int(sample_rate * duracion_ms / 1000)
    fade_samples = int(sample_rate * 0.012)  # 12 ms de fade

    raw = bytearray()
    for i in range(num_samples):
        fade = 1.0
        if i < fade_samples:
            fade = i / fade_samples
        elif i > num_samples - fade_samples:
            fade = (num_samples - i) / fade_samples
        sample = int(32767 * volumen * fade *
                     math.sin(2 * math.pi * frecuencia * i / sample_rate))
        raw.extend(struct.pack('<h', max(-32768, min(32767, sample))))

    data_size = len(raw)
    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF', 36 + data_size, b'WAVE',
        b'fmt ', 16,
        1,            # PCM
        1,            # mono
        sample_rate,
        sample_rate * 2,
        2,
        16,
        b'data', data_size,
    )
    return header + bytes(raw)


def alerta_sonora():
    """Reproduce alerta sonora bloqueante usando WAV en memoria (confiable)."""
    with _audio_lock:
        try:
            beep1 = _generar_wav(880,  250)
            winsound.PlaySound(beep1, winsound.SND_MEMORY)
            time.sleep(0.08)
            beep2 = _generar_wav(1318, 350)
            winsound.PlaySound(beep2, winsound.SND_MEMORY)
        except Exception as e:
            print(f"Error en alerta_sonora: {e}")


async def _tts_bloqueante(texto: str):
    """Descarga y reproduce TTS de forma bloqueante usando Windows MCI."""
    path = os.path.join(tempfile.gettempdir(), 'pedidos_tts.mp3')
    try:
        communicate = edge_tts.Communicate(texto, VOZ_TOMAS)
        await communicate.save(path)

        winmm = ctypes.windll.winmm
        winmm.mciSendStringA(f'open "{path}" type mpegvideo alias ttsplay'.encode('utf-8'), None, 0, 0)
        winmm.mciSendStringA(b'play ttsplay wait', None, 0, 0)
        winmm.mciSendStringA(b'close ttsplay', None, 0, 0)
    except Exception as e:
        print(f"Error en _tts_bloqueante: {e}")
    finally:
        if os.path.exists(path):
            try:
                os.unlink(path)
            except Exception:
                pass


def reproducir_texto(texto: str):
    """Reproduce TTS bloqueando el lock global. Debe llamarse desde un hilo no-UI."""
    with _audio_lock:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_tts_bloqueante(texto))
            loop.close()
        except Exception as e:
            print(f"Error en reproducir_texto: {e}")
