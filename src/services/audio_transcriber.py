import threading
import speech_recognition as sr
import json
import os

class AudioTranscriber:
    def __init__(self, logger, project_dir, text_callback, gui_callback=None):
        self.logger = logger
        self.project_dir = project_dir
        self.text_callback = text_callback
        self.gui_callback = gui_callback
        
        self.recognizer = sr.Recognizer()
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.5
        
        self.mic_available = False
        self.stop_listening_fn = None
        
        self.speech_engine = "google"
        self.whisper_model_name = "tiny"
        self.whisper_device = "auto"
        self.whisper_compute_type = "auto"
        self.whisper_model = None
        self.whisper_loading = False
        self.whisper_loaded = False
        
        self._load_config()

    def _load_config(self):
        config_path = os.path.join(self.project_dir, "config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.speech_engine = config.get("speech_engine", "auto")
                    self.whisper_model_name = config.get("whisper_model", "tiny")
                    self.whisper_device = config.get("whisper_device", "auto")
                    self.whisper_compute_type = config.get("whisper_compute_type", "auto")
            except Exception as e:
                self.logger(f"Erro ao ler config.json no AudioTranscriber: {e}")

    def _resolve_whisper_params(self):
        device = self.whisper_device
        compute_type = self.whisper_compute_type

        if device == "auto":
            try:
                import torch
                if torch.cuda.is_available():
                    device = "cuda"
                    self.logger("GPU com suporte CUDA detectada para Whisper.")
                else:
                    device = "cpu"
                    self.logger("GPU não detectada. Utilizando CPU para Whisper.")
            except ImportError:
                device = "cpu"
                self.logger("PyTorch não importado. Utilizando CPU para Whisper.")

        if compute_type == "auto":
            if device == "cuda":
                compute_type = "float16"
            else:
                compute_type = "int8"

        return device, compute_type

    def _init_whisper_backend(self):
        self.logger("Iniciando carregamento do motor faster-whisper em segundo plano...")
        try:
            from faster_whisper import WhisperModel
            import numpy as np
            
            device, compute_type = self._resolve_whisper_params()
            
            self.logger(f"Carregando modelo '{self.whisper_model_name}' (device={device}, compute_type={compute_type})...")
            self.whisper_model = WhisperModel(
                self.whisper_model_name,
                device=device,
                compute_type=compute_type
            )
            self.whisper_loaded = True
            self.whisper_loading = False
            self.logger(f"Motor faster-whisper carregado com sucesso. Modelo: {self.whisper_model_name}")
        except ImportError as e:
            self.whisper_loading = False
            self.logger(f"faster-whisper ou dependência não instalada. Erro: {e}")
        except Exception as e:
            self.whisper_loading = False
            self.logger(f"Erro ao inicializar o modelo faster-whisper '{self.whisper_model_name}': {e}")

    def start_listening(self):
        if self.speech_engine in ["faster-whisper", "auto"]:
            self.whisper_loading = True
            threading.Thread(target=self._init_whisper_backend, daemon=True).start()

        try:
            self.microphone = sr.Microphone()
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.8)
            self.mic_available = True
            self.logger("Microfone padrão inicializado e calibrado.")
            self.stop_listening_fn = self.recognizer.listen_in_background(
                self.microphone, 
                self.audio_callback,
                phrase_time_limit=4
            )
            self.logger("Escuta contínua de fundo ativada.")
        except Exception as e:
            self.logger(f"ERRO ao inicializar microfone: {e}")

    def _transcribe(self, audio):
        use_whisper = False
        if self.speech_engine == "faster-whisper":
            if self.whisper_loaded:
                use_whisper = True
            else:
                self.logger("Whisper configurado mas ainda não carregado ou falhou. Tentando Google...")
        elif self.speech_engine == "auto":
            if self.whisper_loaded:
                use_whisper = True

        if use_whisper:
            try:
                self.logger("Transcrevendo com motor offline (faster-whisper)...")
                import numpy as np
                raw_data = audio.get_raw_data(convert_rate=16000, convert_width=2)
                audio_np = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32) / 32768.0
                
                segments, info = self.whisper_model.transcribe(
                    audio_np,
                    beam_size=5,
                    language="pt"
                )
                
                text = "".join(segment.text for segment in segments).strip()
                return text
            except Exception as e:
                self.logger(f"Erro na transcrição do faster-whisper: {e}. Tentando fallback online...")

        self.logger("Transcrevendo com motor online (Google)...")
        return self.recognizer.recognize_google(audio, language="pt-BR").strip()

    def audio_callback(self, recognizer, audio):
        try:
            text = self._transcribe(audio)
            if not text:
                self.logger("Áudio não reconhecido (retornou vazio).")
                return
            self.logger(f"Reconhecido: \"{text}\"")
            if self.text_callback:
                self.text_callback(text)
        except sr.UnknownValueError:
            self.logger("Áudio não reconhecido.")
        except sr.RequestError as e:
            self.logger(f"Erro de conexão do Google: {e}")
            if self.gui_callback:
                self.gui_callback("connection_error")
        except Exception as e:
            self.logger(f"ERRO inesperado na escuta: {e}")

    def close(self):
        if self.stop_listening_fn:
            self.stop_listening_fn(wait_for_stop=False)
