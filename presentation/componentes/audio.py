# presentation/componentes/audio.py
import edge_tts
import asyncio
import tempfile
import os
import ctypes
import threading
import winsound
import struct
import math

VOZ_TOMAS = "es-AR-TomasNeural"

_audio_lock = threading.Lock()


def _generar_wav_secuencia(tonos: list, sample_rate: int = 44100) -> bytes:
    """
    Genera una secuencia de tonos como un único buffer WAV.
    tonos: [(frecuencia_hz, duracion_ms, silencio_post_ms), ...]
    """
    all_samples = bytearray()
    fade_samples = int(sample_rate * 0.012)  # 12 ms fade in/out

    for freq, dur_ms, silence_ms in tonos:
        n = int(sample_rate * dur_ms / 1000)
        for i in range(n):
            fade = 1.0
            if i < fade_samples:
                fade = i / fade_samples
            elif i > n - fade_samples:
                fade = (n - i) / fade_samples
            s = int(32767 * 0.8 * fade * math.sin(2 * math.pi * freq * i / sample_rate))
            all_samples.extend(struct.pack('<h', max(-32768, min(32767, s))))
        # silencio entre tonos
        all_samples.extend(b'\x00\x00' * int(sample_rate * silence_ms / 1000))

    data_size = len(all_samples)
    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF', 36 + data_size, b'WAVE',
        b'fmt ', 16, 1, 1,
        sample_rate, sample_rate * 2, 2, 16,
        b'data', data_size,
    )
    return header + bytes(all_samples)


# Pre-generar el WAV de alerta una sola vez al importar el módulo
_WAV_ALERTA = _generar_wav_secuencia([
    (880,  250, 80),   # primer tono + 80 ms de silencio
    (1318, 350, 0),    # segundo tono
])


def alerta_sonora():
    """Reproduce la alerta sonora completa en una única llamada bloqueante."""
    with _audio_lock:
        try:
            winsound.PlaySound(_WAV_ALERTA, winsound.SND_MEMORY)
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
        # FIX #5: eliminación del archivo siempre en finally, incluso si MCI falla
        if os.path.exists(path):
            try:
                os.unlink(path)
            except Exception:
                pass


def reproducir_texto(texto: str):
    """Reproduce TTS bloqueando el lock global. Debe llamarse desde un hilo no-UI."""
    with _audio_lock:
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_tts_bloqueante(texto))
        except Exception as e:
            print(f"Error en reproducir_texto: {e}")
        finally:
            # FIX #5: cierre garantizado del event loop incluso ante excepciones
            if loop is not None and not loop.is_closed():
                loop.close()
