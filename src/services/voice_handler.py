import threading
import time
import json
import os
import urllib.request
import urllib.error
from scripts.entity_extractor import get_index, get_task_text

try:
    import keyboard
except ImportError:
    keyboard = None

from src.services.audio_transcriber import AudioTranscriber
from src.services.speech_synthesizer import SpeechSynthesizer
from src.services.intent_parser import IntentParser

class VoiceHandler:
    def __init__(self, task_manager, gui_callback=None, start_listening=True):
        self.task_manager = task_manager
        self.gui_callback = gui_callback
        self.active_mode = False
        
        import sys
        if getattr(sys, 'frozen', False):
            self.project_dir = os.path.dirname(sys.executable)
        else:
            self.project_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
        self.log_dir = os.path.join(self.project_dir, "logs")
        os.makedirs(self.log_dir, exist_ok=True)
        self.log_filepath = os.path.join(self.log_dir, "jarvis.log")
        self._log_lock = threading.Lock()
        
        try:
            with open(self.log_filepath, 'w', encoding='utf-8') as f:
                f.write(f"=== LOG DO JARVIS INICIADO EM {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
        except OSError:
            pass

        self.log("Inicializando VoiceHandler (Controller)...")
        
        # Modules
        self.speech_synthesizer = SpeechSynthesizer(self.log)
        self.intent_parser = IntentParser(self.log, self.project_dir)
        self.audio_transcriber = AudioTranscriber(
            self.log, self.project_dir, self.process_text, self.gui_callback
        )
        
        self.hotkey = "ctrl+shift+j"
        self._load_config()

        if start_listening:
            self.audio_transcriber.start_listening()

        self.hotkey_hook = None
        if start_listening and keyboard:
            try:
                self.hotkey_hook = keyboard.add_hotkey(self.hotkey, self.toggle_active)
                self.log(f"Hotkey global '{self.hotkey}' registrada com sucesso.")
            except Exception as e:
                self.log(f"Erro ao registrar hotkey global '{self.hotkey}': {e}")

    def _load_config(self):
        config_path = os.path.join(self.project_dir, "config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.hotkey = config.get("HOTKEY", "ctrl+shift+j")
            except (OSError, json.JSONDecodeError) as e:
                self.log(f"Erro ao ler config.json no VoiceHandler: {e}")

    def log(self, message):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with self._log_lock:
            try:
                with open(self.log_filepath, 'a', encoding='utf-8') as f:
                    f.write(f"[{timestamp}] {message}\n")
            except OSError:
                pass

    def get_sorted_tasks(self):
        tasks = self.task_manager.read_tasks()
        priority_order = {"Alta": 1, "Média": 2, "Baixa": 3}
        tasks.sort(key=lambda t: (
            t.get("completed", False), 
            priority_order.get(t.get("priority", "Média"), 2),
            t.get("id", 0)
        ))
        return tasks

    def _find_task_by_index_or_text(self, text, tasks_list):
        idx = get_index(text)
        sorted_tasks = list(tasks_list)
        sorted_tasks.sort(key=lambda t: (
            t.get("completed", False),
            t.get("sort_order", t.get("id", 0) * 10),
            t.get("id", 0)
        ))

        if idx is not None:
            list_idx = idx - 1
            if 0 <= list_idx < len(sorted_tasks):
                return sorted_tasks[list_idx]
        
        # Regras diretas numéricas
        if text.isdigit():
            list_idx = int(text) - 1
            if 0 <= list_idx < len(sorted_tasks):
                return sorted_tasks[list_idx]

        clean_target = get_task_text(text) if get_task_text(text) else text.strip()
        if clean_target:
            matches = [t for t in tasks_list if clean_target.lower() in t["text"].lower()]
            if matches:
                return matches[0]
        return None

    def process_text(self, text):
        parsed = self.intent_parser.parse(text, self.active_mode)
        intent = parsed.get("intent")
        
        if intent == "ignore":
            return
        
        if intent == "wake":
            if not self.active_mode:
                self.active_mode = True
                self.log("Jarvis ATIVADO.")
                self.speech_synthesizer.play_chime(True)
                if self.gui_callback: self.gui_callback("status_active")
            return
            
        if intent == "sleep":
            if self.active_mode:
                self.active_mode = False
                self.log("Jarvis DESATIVADO.")
                self.speech_synthesizer.play_chime(False)
                if self.gui_callback: self.gui_callback("status_inactive")
            return

        if not self.active_mode:
            return

        if intent == "add_error":
            self.speech_synthesizer.speak("O que deseja adicionar senhor?")
            return
        if intent == "complete_error":
            self.speech_synthesizer.speak("Qual tarefa deseja concluir senhor?")
            return
        if intent == "delete_error":
            self.speech_synthesizer.speak("Qual tarefa deseja remover senhor?")
            return
        if intent == "edit_error":
            self.speech_synthesizer.speak("Senhor, por favor indique a tarefa antiga e o novo texto usando 'para'.")
            return
        if intent == "priority_error":
            self.speech_synthesizer.speak("Senhor, não entendi qual prioridade aplicar.")
            return

        if intent == "add_task":
            content = parsed["content"]
            priority = parsed["priority"]
            
            def add_cb(tasks_list):
                new_id = max([t.get("id", 0) for t in tasks_list] + [0]) + 1
                tasks_list.append({"id": new_id, "text": content, "completed": False, "priority": priority})
                return tasks_list
                
            if self.task_manager.update_tasks(add_cb):
                self.log(f"Adicionada: {content}")
                if parsed.get("fallback"):
                    self.speech_synthesizer.speak(f"Adicionada: {content}.")
                else:
                    self.speech_synthesizer.speak(f"Adicionada: {content}, com prioridade {priority.lower()}.")
                if self.gui_callback: self.gui_callback("refresh")

        elif intent == "delete_task":
            target = parsed["target"]
            deleted_info = {"text": ""}
            
            def delete_cb(tasks_list):
                task = self._find_task_by_index_or_text(target, tasks_list)
                if task:
                    deleted_info["text"] = task["text"]
                    return [t for t in tasks_list if t["id"] != task["id"]]
                return None
                
            if self.task_manager.update_tasks(delete_cb):
                self.log(f"Removida: {deleted_info['text']}")
                self.speech_synthesizer.speak(f"Tarefa removida com sucesso: {deleted_info['text']}.")
                if self.gui_callback: self.gui_callback("refresh")
            else:
                self.speech_synthesizer.speak("Não encontrei a tarefa para remover.")

        elif intent == "complete_task":
            target = parsed["target"]
            completed_info = {"text": ""}
            
            def complete_cb(tasks_list):
                task = self._find_task_by_index_or_text(target, tasks_list)
                if task:
                    for t in tasks_list:
                        if t["id"] == task["id"]:
                            t["completed"] = True
                            completed_info["text"] = t["text"]
                            return tasks_list
                return None
                
            if self.task_manager.update_tasks(complete_cb):
                self.log(f"Concluída: {completed_info['text']}")
                self.speech_synthesizer.speak(f"Tarefa concluída: {completed_info['text']}.")
                if self.gui_callback: self.gui_callback("refresh")
            else:
                self.speech_synthesizer.speak("Não encontrei a tarefa para concluir.")

        elif intent == "edit_task":
            target = parsed["target"]
            new_content = parsed["new_content"]
            priority = parsed.get("priority")
            edit_info = {"old_text": "", "priority_msg": ""}
            
            def edit_cb(tasks_list):
                task = self._find_task_by_index_or_text(target, tasks_list)
                if task:
                    for t in tasks_list:
                        if t["id"] == task["id"]:
                            edit_info["old_text"] = t["text"]
                            t["text"] = new_content
                            if priority:
                                t["priority"] = priority
                                edit_info["priority_msg"] = f" e prioridade {priority.lower()}"
                            return tasks_list
                return None
                
            if self.task_manager.update_tasks(edit_cb):
                self.log(f"Alterada: {edit_info['old_text']} -> {new_content}")
                self.speech_synthesizer.speak(f"Tarefa alterada de '{edit_info['old_text']}' para '{new_content}'{edit_info['priority_msg']}.")
                if self.gui_callback: self.gui_callback("refresh")
            else:
                self.speech_synthesizer.speak("Não encontrei a tarefa para alterar.")

        elif intent == "change_priority":
            target = parsed["target"]
            priority = parsed["priority"]
            priority_info = {"text": ""}
            
            def priority_cb(tasks_list):
                task = self._find_task_by_index_or_text(target, tasks_list)
                if task:
                    for t in tasks_list:
                        if t["id"] == task["id"]:
                            t["priority"] = priority
                            priority_info["text"] = t["text"]
                            return tasks_list
                return None
                
            if self.task_manager.update_tasks(priority_cb):
                self.log(f"Prioridade alterada: {priority_info['text']} -> {priority}")
                self.speech_synthesizer.speak(f"Prioridade de '{priority_info['text']}' alterada para {priority.lower()}.")
                if self.gui_callback: self.gui_callback("refresh")
            else:
                self.speech_synthesizer.speak("Não encontrei a tarefa para alterar a prioridade.")

        elif intent == "list_tasks":
            tasks = self.task_manager.read_tasks()
            pending_tasks = [t for t in tasks if not t["completed"]]
            if not pending_tasks:
                self.speech_synthesizer.speak("Você não tem tarefas pendentes senhor.")
                return
            self.speech_synthesizer.speak(f"Você tem {len(pending_tasks)} tarefas pendentes.")
            for i, t in enumerate(pending_tasks[:5]):
                self.speech_synthesizer.speak(f"Tarefa {i+1}: {t['text']}, prioridade {t['priority'].lower()}.")
            if len(pending_tasks) > 5:
                self.speech_synthesizer.speak("E mais algumas outras na lista.")

    def handle_question(self, question):
        api_key = os.environ.get("GEMINI_API_KEY", "")
        config_path = os.path.join(self.project_dir, "config.json")
        if not api_key and os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    api_key = config.get("GEMINI_API_KEY", "")
            except (OSError, json.JSONDecodeError) as e:
                self.log(f"Erro ao ler config.json: {e}")

        if not api_key:
            self.log("GEMINI_API_KEY não configurada.")
            self.speech_synthesizer.speak("Desculpe, senhor. Preciso que configure minha chave da API Gemini no arquivo de configurações.")
            if self.gui_callback:
                self.gui_callback("api_key_missing")
            return

        self.speech_synthesizer.speak("Pesquisando...")
        
        def call_gemini():
            url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={api_key}"
            headers = {"Content-Type": "application/json"}
            data = {
                "contents": [{
                    "parts": [{
                        "text": f"Você é o Jarvis, o assistente pessoal inteligente do usuário. Responda à seguinte pergunta de forma concisa, direta e prestativa: {question}"
                    }]
                }]
            }
            try:
                req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
                with urllib.request.urlopen(req, timeout=10) as response:
                    res_data = json.loads(response.read().decode('utf-8'))
                    answer = res_data['candidates'][0]['content']['parts'][0]['text'].strip()
                    self.log(f"Resposta do Gemini: \"{answer}\"")
                    self.speech_synthesizer.speak(answer)
            except urllib.error.HTTPError as e:
                self.log(f"Erro HTTP do Gemini: {e.code} - {e.read().decode('utf-8', 'ignore')}")
                self.speech_synthesizer.speak("Desculpe, ocorreu um erro com a inteligência artificial.")
            except urllib.error.URLError as e:
                self.log(f"Erro de conexão Gemini: {e}")
                self.speech_synthesizer.speak("Desculpe, ocorreu um erro de rede com a inteligência artificial.")
            except Exception as e:
                self.log(f"Erro Gemini: {e}")
                self.speech_synthesizer.speak("Desculpe, não consegui processar a resposta.")

        threading.Thread(target=call_gemini, daemon=True).start()

    def toggle_active(self):
        self.active_mode = not self.active_mode
        self.log(f"Modo de voz alternado manualmente: {self.active_mode}")
        self.speech_synthesizer.play_chime(self.active_mode)
        if self.gui_callback:
            status_cmd = "status_active" if self.active_mode else "status_inactive"
            self.gui_callback(status_cmd)
        return self.active_mode

    def close(self):
        self.audio_transcriber.close()
        self.speech_synthesizer.close()
        if self.hotkey_hook and keyboard:
            try:
                keyboard.remove_hotkey(self.hotkey_hook)
                self.log("Hotkey global removida.")
            except Exception as e:
                self.log(f"Erro ao remover hotkey global: {e}")
        self.log("VoiceHandler encerrado.")
