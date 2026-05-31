import os
import joblib
import re
from scripts.entity_extractor import get_task_text, get_priority, get_edit_parts

class IntentParser:
    CONFIDENCE_THRESHOLD = 0.65

    def __init__(self, logger, project_dir):
        self.logger = logger
        self.project_dir = project_dir
        try:
            self._intent_model = joblib.load(
                os.path.join(self.project_dir, "data", "intent_model.pkl")
            )
            self.logger("Modelo de intents ML carregado.")
        except FileNotFoundError:
            self._intent_model = None
            self.logger("AVISO: intent_model.pkl não encontrado. Usando regras (fallback).")

    def _word_to_digit(self, text):
        mapping = {
            "um": "1", "uma": "1", "primeiro": "1", "primeira": "1",
            "dois": "2", "duas": "2", "segundo": "2", "segunda": "2",
            "três": "3", "tres": "3", "terceiro": "3", "terceira": "3",
            "quatro": "4", "quarto": "4", "quarta": "4",
            "cinco": "5", "quinto": "5", "quinta": "5",
            "seis": "6", "sexto": "6", "sexta": "6",
            "sete": "7", "sétimo": "7", "setimo": "7",
            "oito": "8", "oitavo": "8",
            "nove": "9", "nono": "9", "nona": "9",
            "dez": "10", "décimo": "10", "decimo": "10",
        }
        return mapping.get(text.strip().lower(), text)

    def parse(self, text, active_mode):
        if self._intent_model is None:
            return self._process_phrase_rules(text, active_mode)

        phrase = text.lower().strip()
        self.logger(f'Processando frase (ML): "{phrase}"')

        proba = self._intent_model.predict_proba([phrase])[0]
        intent = self._intent_model.classes_[proba.argmax()]
        conf = proba.max()
        self.logger(f"Intent: {intent} ({conf:.2f})")

        if conf < self.CONFIDENCE_THRESHOLD:
            self.logger("Confiança insuficiente. Repassando para processamento por regras (fallback).")
            return self._process_phrase_rules(text, active_mode)

        if intent == "wake":
            return {"intent": "wake"}
        if intent == "sleep":
            return {"intent": "sleep"}

        if not active_mode:
            return {"intent": "ignore"}

        if intent == "add_task":
            content = get_task_text(text)
            priority = get_priority(text) or "Média"
            return {"intent": "add_task", "content": content, "priority": priority}

        if intent == "delete_task":
            return {"intent": "delete_task", "target": text}

        if intent == "complete_task":
            return {"intent": "complete_task", "target": text}

        if intent == "edit_task":
            parts = get_edit_parts(text)
            if not parts:
                return {"intent": "edit_error"}
            old_part, new_part = parts
            priority = get_priority(new_part)
            new_content = get_task_text(new_part)
            return {"intent": "edit_task", "target": old_part, "new_content": new_content, "priority": priority}

        if intent == "change_priority":
            priority = get_priority(text)
            if not priority:
                return {"intent": "priority_error"}
            return {"intent": "change_priority", "target": text, "priority": priority}

        if intent == "list_tasks":
            return {"intent": "list_tasks"}

        return {"intent": "unknown"}

    def _process_phrase_rules(self, text, active_mode):
        phrase = text.lower().strip()
        self.logger(f"Processando frase (Regras): \"{phrase}\"")

        clean_phrase = phrase.replace(",", " ").replace(".", " ").replace("?", " ").replace("!", " ")
        words = clean_phrase.split()

        wake_words = ["ligar", "ativar", "olá", "ola", "acordar", "iniciar", "alô", "alo", "escutar", "chamar"]
        sleep_words = ["desligar", "desativar", "dormir", "parar", "silenciar", "tchau", "adeus", "repouso"]
        jarvis_variations = ["jarvis", "jarv", "jar", "arvis", "xarvis", "chaves", "jarbas", "javis", "gerente", "jard", "jardi", "jardis", "gard", "gardis"]
        
        has_jarvis = any(j in words for j in jarvis_variations) or any(j in phrase for j in ["jarvis", "jarv", "arvis", "javis"])
        has_sleep = any(w in words for w in sleep_words)
        has_wake = any(w in words for w in wake_words) and not has_sleep

        if has_wake and has_jarvis:
            return {"intent": "wake"}

        if has_sleep and has_jarvis:
            return {"intent": "sleep"}

        if not active_mode:
            return {"intent": "ignore"}

        cmd_text = text
        for jv in jarvis_variations:
            pat = re.compile(r'^\s*' + re.escape(jv) + r'[\s,.:]*', re.IGNORECASE)
            cmd_text = pat.sub('', cmd_text).strip()
        cmd_phrase = cmd_text.lower()

        id_prefixes = ["a tarefa ", "o id ", "do id ", "de id ", "número ", "numero ", "nº ", "no ", "tarefa ", "tarefas ", "a ", "o ", "as ", "os "]
        id_prefixes.sort(key=len, reverse=True)

        # ADD TASK
        add_keywords = ["adicionar", "crie", "criar", "anotar", "adicione", "insira", "inserir"]
        if any(cmd_phrase.startswith(kw) for kw in add_keywords):
            content = cmd_text
            for kw in add_keywords:
                if content.lower().startswith(kw):
                    content = content[len(kw):].strip()
                    break
            
            for prefix in ["a tarefa ", "tarefa ", "uma tarefa ", "o compromisso ", "o compromisso de "]:
                if content.lower().startswith(prefix):
                    content = content[len(prefix):].strip()
                    break
            
            if not content:
                return {"intent": "add_error"}

            priority = "Média"
            lower_content = content.lower()
            if "prioridade alta" in lower_content:
                priority = "Alta"
                content = re.sub(r'com prioridade alta|prioridade alta', '', content, flags=re.IGNORECASE).strip()
            elif "prioridade média" in lower_content or "prioridade media" in lower_content:
                priority = "Média"
                content = re.sub(r'com prioridade média|com prioridade media|prioridade média|prioridade media', '', content, flags=re.IGNORECASE).strip()
            elif "prioridade baixa" in lower_content:
                priority = "Baixa"
                content = re.sub(r'com prioridade baixa|prioridade baixa', '', content, flags=re.IGNORECASE).strip()
            
            if content.lower().endswith(" com"):
                content = content[:-4].strip()

            return {"intent": "add_task", "content": content, "priority": priority}

        # COMPLETE TASK
        complete_keywords = ["concluir", "finalizar", "marcar como concluída", "marcar como concluida", "riscar", "completar"]
        if any(cmd_phrase.startswith(kw) for kw in complete_keywords):
            target = cmd_text
            for kw in complete_keywords:
                if target.lower().startswith(kw):
                    target = target[len(kw):].strip()
                    break
            
            if not target:
                return {"intent": "complete_error"}

            clean_target = target.lower().strip()
            while True:
                matched = False
                for id_pref in id_prefixes:
                    if clean_target.startswith(id_pref):
                        clean_target = clean_target[len(id_pref):].strip()
                        matched = True
                        break
                if not matched:
                    break

            clean_target = self._word_to_digit(clean_target)
            return {"intent": "complete_task", "target": clean_target}

        # DELETE TASK
        delete_keywords = ["remover", "deletar", "excluir", "apagar"]
        if any(cmd_phrase.startswith(kw) for kw in delete_keywords):
            target = cmd_text
            for kw in delete_keywords:
                if target.lower().startswith(kw):
                    target = target[len(kw):].strip()
                    break

            if not target:
                return {"intent": "delete_error"}

            clean_target = target.lower().strip()
            while True:
                matched = False
                for id_pref in id_prefixes:
                    if clean_target.startswith(id_pref):
                        clean_target = clean_target[len(id_pref):].strip()
                        matched = True
                        break
                if not matched:
                    break

            clean_target = self._word_to_digit(clean_target)
            return {"intent": "delete_task", "target": clean_target}

        # EDIT TASK
        edit_keywords = ["alterar", "atualizar", "mudar", "editar", "corrigir"]
        if any(cmd_phrase.startswith(kw) for kw in edit_keywords):
            target = cmd_text
            for kw in edit_keywords:
                if target.lower().startswith(kw):
                    target = target[len(kw):].strip()
                    break
            
            lower_target = target.lower()
            sep_idx = -1
            sep_len = 0
            for sep in [" para ", " pra "]:
                idx = lower_target.find(sep)
                if idx != -1:
                    sep_idx = idx
                    sep_len = len(sep)
                    break
            
            if sep_idx == -1:
                return {"intent": "edit_error"}

            search_term = target[:sep_idx].strip()
            new_content = target[sep_idx + sep_len:].strip()

            priority = None
            lower_new = new_content.lower()
            if "prioridade alta" in lower_new:
                priority = "Alta"
                new_content = re.sub(r'com prioridade alta|prioridade alta', '', new_content, flags=re.IGNORECASE).strip()
            elif "prioridade média" in lower_new or "prioridade media" in lower_new:
                priority = "Média"
                new_content = re.sub(r'com prioridade média|com prioridade media|prioridade média|prioridade media', '', new_content, flags=re.IGNORECASE).strip()
            elif "prioridade baixa" in lower_new:
                priority = "Baixa"
                new_content = re.sub(r'com prioridade baixa|prioridade baixa', '', new_content, flags=re.IGNORECASE).strip()
            
            if new_content.lower().endswith(" com"):
                new_content = new_content[:-4].strip()

            clean_search = search_term.lower().strip()
            while True:
                matched = False
                for id_pref in id_prefixes:
                    if clean_search.startswith(id_pref):
                        clean_search = clean_search[len(id_pref):].strip()
                        matched = True
                        break
                if not matched:
                    break

            clean_search = self._word_to_digit(clean_search)
            return {"intent": "edit_task", "target": clean_search, "new_content": new_content, "priority": priority}

        # CHANGE PRIORITY
        p_keywords = [" como prioridade ", " com prioridade "]
        p_idx = -1
        p_len = 0
        for p_kw in p_keywords:
            idx = phrase.find(p_kw)
            if idx != -1:
                p_idx = idx
                p_len = len(p_kw)
                break
        
        if p_idx != -1:
            search_term = text[:p_idx].strip()
            priority_val = text[p_idx + p_len:].strip().lower()
            
            for jv in jarvis_variations:
                pat = re.compile(r'^\s*' + re.escape(jv) + r'[\s,.:]*', re.IGNORECASE)
                search_term = pat.sub('', search_term).strip()

            clean_search = search_term.lower().strip()
            while True:
                matched = False
                for id_pref in id_prefixes:
                    if clean_search.startswith(id_pref):
                        clean_search = clean_search[len(id_pref):].strip()
                        matched = True
                        break
                if not matched:
                    break

            mapped_priority = None
            if "alta" in priority_val:
                mapped_priority = "Alta"
            elif "média" in priority_val or "media" in priority_val:
                mapped_priority = "Média"
            elif "baixa" in priority_val:
                mapped_priority = "Baixa"
            
            clean_search = self._word_to_digit(clean_search)
            if mapped_priority:
                return {"intent": "change_priority", "target": clean_search, "priority": mapped_priority}

        # LIST TASKS
        list_keywords = [
            "quais são minhas tarefas", "quais sao minhas tarefas",
            "listar tarefas", "listar minhas tarefas",
            "o que eu tenho para fazer", "o que eu tenho pra fazer", "o que eu tenho que fazer",
            "ver tarefas", "mostrar tarefas",
            "quais são minhas", "quais sao minhas",
            "minhas tarefas", "lista de tarefas", "liste as tarefas",
        ]
        if any(kw in cmd_phrase for kw in list_keywords):
            return {"intent": "list_tasks"}

        return {"intent": "unknown"}
