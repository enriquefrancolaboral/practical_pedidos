import numpy as np
import sounddevice as sd
import edge_tts
import asyncio
import io
import miniaudio
import threading
import warnings

warnings.filterwarnings("ignore", category=UserWarning)

SR = 44100
VOZ_TOMAS = "es-AR-TomasNeural"

# Lock global: garantiza que nunca haya dos audios simultáneos
_audio_lock = threading.Lock()


def alerta_sonora():
    """Reproduce alerta sonora bloqueante. Adquiere el lock global de audio."""
    with _audio_lock:
        try:
            def bell(freq, dur=0.6, vol=0.45):
                t = np.linspace(0, dur, int(SR * dur), False)
                env = np.exp(-4 * t / dur)
                return vol * env * (np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(2 * np.pi * freq * 2 * t))

            wave = np.concatenate([bell(880, 0.5), np.zeros(int(SR * 0.08)), bell(1318, 0.7)])
            sd.default.device = None
            sd.play(wave.astype(np.float32), SR)
            sd.wait()
        except Exception as e:
            print(f"Error en alerta_sonora: {e}")


async def _tts_bloqueante(texto: str):
    """Descarga y reproduce TTS de forma bloqueante (async interno)."""
    communicate = edge_tts.Communicate(texto, VOZ_TOMAS)
    buffer = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buffer.write(chunk["data"])
    buffer.seek(0)
    decoded = miniaudio.decode(buffer.read(), output_format=miniaudio.SampleFormat.SIGNED16)
    samples = np.frombuffer(decoded.samples, dtype=np.int16).astype(np.float32) / 2 ** 15
    if decoded.nchannels == 2:
        samples = samples.reshape((-1, 2))
    sd.play(samples, decoded.sample_rate)
    sd.wait()


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
