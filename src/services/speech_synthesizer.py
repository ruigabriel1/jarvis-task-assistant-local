import threading
import os
import time
import queue
import pyttsx3
import pythoncom
import asyncio
import tempfile

try:
    import edge_tts
    HAS_EDGE_TTS = True
except ImportError:
    HAS_EDGE_TTS = False

_PREWARM_PHRASES = [
    "Como posso te ajudar senhor?",
    "Desligando.",
    "Pesquisando...",
    "Não encontrei essa tarefa.",
    "Não encontrei a tarefa.",
    "Você não tem tarefas pendentes senhor.",
    "O que deseja adicionar senhor?",
    "Qual tarefa deseja concluir senhor?",
    "Qual tarefa deseja remover senhor?",
    "Senhor, por favor indique a tarefa antiga e o novo texto usando 'para'.",
    "Desculpe, senhor. Preciso que configure minha chave da API Gemini no arquivo de configurações.",
]

class SpeechSynthesizer:
    def __init__(self, logger):
        self.logger = logger
        self.running = True
        self.edge_voice = "pt-BR-AntonioNeural"
        self._tts_cache = {}
        self._tts_cache_dir = os.path.join(tempfile.gettempdir(), "jarvis_tts_cache")
        os.makedirs(self._tts_cache_dir, exist_ok=True)

        self.speech_queue = queue.Queue()
        self.speaker_thread = threading.Thread(target=self._speech_worker, daemon=True)
        self.speaker_thread.start()

        if HAS_EDGE_TTS:
            threading.Thread(target=self._prewarm_tts_cache, daemon=True).start()

    def _play_audio(self, filepath):
        if os.name == 'nt':
            import ctypes
            size = 256
            buffer = ctypes.create_unicode_buffer(size)
            ctypes.windll.kernel32.GetShortPathNameW(filepath, buffer, size)
            short_path = buffer.value or filepath
            
            alias = f"jarvis_play_{int(time.time() * 1000)}"
            winmm = ctypes.windll.winmm
            try:
                winmm.mciSendStringW(f'close {alias}', None, 0, 0)
                res = winmm.mciSendStringW(f'open "{short_path}" type mpegvideo alias {alias}', None, 0, 0)
                if res != 0:
                    raise RuntimeError(f"MCI open error: {res}")
                res = winmm.mciSendStringW(f'play {alias} wait', None, 0, 0)
                if res != 0:
                    raise RuntimeError(f"MCI play error: {res}")
            finally:
                winmm.mciSendStringW(f'close {alias}', None, 0, 0)
        else:
            import subprocess
            if hasattr(os, 'uname'):
                sysname = os.uname().sysname
            else:
                sysname = ''
            
            if sysname == 'Darwin':
                subprocess.run(['afplay', filepath], check=True)
            else:
                for player in ['mpg123', 'mpv', 'play']:
                    try:
                        subprocess.run([player, filepath], check=True)
                        break
                    except FileNotFoundError:
                        continue

    def _tts_cache_path(self, text):
        safe_hash = abs(hash(text)) & 0xFFFFFFFF
        return os.path.join(self._tts_cache_dir, f"{safe_hash}.mp3")

    def _prewarm_tts_cache(self):
        if not HAS_EDGE_TTS:
            return
        self.logger("Iniciando pré-aquecimento do cache TTS...")
        for phrase in _PREWARM_PHRASES:
            if not self.running:
                break
            cache_file = self._tts_cache_path(phrase)
            if os.path.exists(cache_file) and os.path.getsize(cache_file) > 0:
                self._tts_cache[phrase] = cache_file
                continue
            try:
                async def gen(p=phrase, f=cache_file):
                    comm = edge_tts.Communicate(p, self.edge_voice)
                    await comm.save(f)
                asyncio.run(gen())
                if os.path.exists(cache_file) and os.path.getsize(cache_file) > 0:
                    self._tts_cache[phrase] = cache_file
                    self.logger(f"Cache TTS gerado: '{phrase[:40]}...' " if len(phrase) > 40 else f"Cache TTS gerado: '{phrase}'")
            except Exception as e:
                self.logger(f"Aviso: falha ao pré-gerar cache TTS para '{phrase[:30]}': {e}")
        self.logger("Pré-aquecimento do cache TTS concluído.")

    def _speak_edge_tts(self, text):
        cache_file = self._tts_cache_path(text)
        if text in self._tts_cache and os.path.exists(cache_file) and os.path.getsize(cache_file) > 0:
            try:
                self._play_audio(cache_file)
                return True
            except Exception as e:
                self.logger(f"Aviso: falha ao tocar áudio em cache: {e}")

        try:
            async def generate():
                communicate = edge_tts.Communicate(text, self.edge_voice)
                await communicate.save(cache_file)

            asyncio.run(generate())

            if os.path.exists(cache_file) and os.path.getsize(cache_file) > 0:
                self._tts_cache[text] = cache_file
                self._play_audio(cache_file)
                return True
            return False
        except Exception as e:
            self.logger(f"Falha ao gerar/tocar áudio edge-tts: {e}")
            return False

    def _speech_worker(self):
        pythoncom.CoInitialize()
        try:
            pyttsx3_engine = pyttsx3.init()
            pyttsx3_engine.setProperty('rate', 175)
            voices = pyttsx3_engine.getProperty('voices')
            for voice in voices:
                if any(x in voice.id.upper() for x in ['PT', 'PORTUGUESE', 'BRAZIL']):
                    pyttsx3_engine.setProperty('voice', voice.id)
                    break
        except Exception as e:
            self.logger(f"ERRO no pyttsx3: {e}")
            pyttsx3_engine = None

        while self.running:
            try:
                text = self.speech_queue.get(timeout=1.0)
                if not text:
                    self.speech_queue.task_done()
                    continue
                
                success = False
                if HAS_EDGE_TTS:
                    try:
                        success = self._speak_edge_tts(text)
                    except Exception as e:
                        self.logger(f"Erro durante execução do edge-tts: {e}")
                        success = False
                
                if not success:
                    if pyttsx3_engine:
                        try:
                            pyttsx3_engine.say(text)
                            pyttsx3_engine.runAndWait()
                        except Exception as e:
                            self.logger(f"ERRO no pyttsx3 fallback: {e}")
                    else:
                        self.logger("Nenhum sintetizador de voz disponível.")
                
                self.speech_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                self.logger(f"ERRO TTS: {e}")
        pythoncom.CoUninitialize()

    def speak(self, text):
        self.speech_queue.put(text)

    def play_chime(self, active):
        if active:
            self.speak("Como posso te ajudar senhor?")
        else:
            self.speak("Desligando.")

    def close(self):
        self.running = False
