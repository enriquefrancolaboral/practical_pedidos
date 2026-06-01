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

def alerta_sonora():
    """Reproduce una alerta sonora exactamente igual a gui.py"""
    try:
        def bell(freq, dur=0.6, vol=0.45):
            t = np.linspace(0, dur, int(SR * dur), False)
            env = np.exp(-4 * t / dur)
            return vol * env * (np.sin(2*np.pi*freq*t) + 0.3*np.sin(2*np.pi*freq*2*t))
        
        wave = np.concatenate([bell(880, 0.5), np.zeros(int(SR*0.08)), bell(1318, 0.7)])
        
        # Forzar dispositivo por defecto y esperar
        sd.default.device = None  # Usar el dispositivo por defecto del sistema
        sd.play(wave.astype(np.float32), SR)
        sd.wait()  # Esperar a que termine completamente
    except Exception as e:
        print(f"Error en alerta_sonora: {e}")

async def _descargar_y_reproducir_tts(texto):
    """Descarga y reproduce texto a voz (async)"""
    try:
        communicate = edge_tts.Communicate(texto, VOZ_TOMAS)
        buffer = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buffer.write(chunk["data"])
        buffer.seek(0)
        decoded = miniaudio.decode(buffer.read(), output_format=miniaudio.SampleFormat.SIGNED16)
        samples = np.frombuffer(decoded.samples, dtype=np.int16).astype(np.float32) / 2**15
        if decoded.nchannels == 2:
            samples = samples.reshape((-1, 2))
        sd.play(samples, decoded.sample_rate)
        sd.wait()
    except Exception as e:
        print(f"Error en TTS: {e}")

def reproducir_texto(texto):
    """Reproduce texto en voz (ejecuta en hilo separado con su propio event loop)"""
    def run():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_descargar_y_reproducir_tts(texto))
            loop.close()
        except Exception as e:
            print(f"Error en reproducir_texto: {e}")
    
    threading.Thread(target=run, daemon=True).start()