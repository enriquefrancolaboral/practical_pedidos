# presentation/componentes/audio.py
import edge_tts
import asyncio
import tempfile
import os
import ctypes
import threading
import time
import winsound

VOZ_TOMAS = "es-AR-TomasNeural"

# Lock global: garantiza que nunca haya dos audios simultáneos
_audio_lock = threading.Lock()


def alerta_sonora():
    """Reproduce alerta sonora bloqueante sin numpy/sounddevice."""
    with _audio_lock:
        try:
            # Frecuencia en Hz, Duración en ms
            winsound.Beep(880, 250)
            time.sleep(0.08)
            winsound.Beep(1318, 350)
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
