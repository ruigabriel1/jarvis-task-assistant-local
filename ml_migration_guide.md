# ML Migration Guide — Jarvis Task Assistant

> Written in English for token efficiency and AI readability.

---

## Subagent Instructions

This section tells an AI orchestrator how to assign work across subagents when implementing this migration.

---

### ORCHESTRATOR

**Role:** Coordinates all subagents. Reads this file first. Assigns tasks in order. Validates outputs before proceeding to next phase.

**Rules:**
- Never write code directly. Delegate to the appropriate subagent.
- Run AGENT_TEST after every code change.
- If tests fail, send the error back to the subagent that made the change.
- Do not proceed to the next migration phase until all tests pass.

**Sequence:**
```
Phase 2: AGENT_DOCS → AGENT_DB → AGENT_CODE → AGENT_TEST
Phase 3: AGENT_CODE (shadow mode) → AGENT_TEST
Phase 4: AGENT_CODE (ML primary) → AGENT_TEST
Phase 5: AGENT_CODE (remove rules) → AGENT_TEST
```

---

### AGENT_CODE

**Files:** `voice_handler.py`, `app.pyw`

**Scope:** All logic inside `process_phrase()`, `__init__()` model loading, and the `_ml_*` action methods.

**Do:**
- Implement the model loading block in `__init__()` (Step 4).
- Replace `process_phrase()` with the ML version.
- Implement each `_ml_add`, `_ml_delete`, `_ml_complete`, `_ml_edit`, `_ml_priority`, `_ml_list` method using `entity_extractor.py` functions.
- Keep `_process_phrase_rules()` as a renamed copy of the old method — do NOT delete it.
- All GUI calls must use `self.after(0, callback)` — do not call GUI methods directly from threads.

**Do NOT:**
- Touch `task_manager.py` — that is AGENT_DB's domain.
- Remove existing TTS cache, `_log_lock`, or `pause_threshold` settings.

---

### AGENT_DB

**Files:** `task_manager.py`, `data/dataset.csv`

**Scope:** Database schema, migrations, and labeled training dataset.

**Do:**
- Validate that `sort_order` column exists (migration already in place — do not duplicate).
- Create `data/dataset.csv` with at least 200 labeled rows per intent class (8 classes).
- Export real phrases from `logs/jarvis.log` using `scripts/export_logs_to_dataset.py` to seed the dataset.

**Do NOT:**
- Modify `read_tasks()` or `write_tasks()` unless schema changes require it.
- Delete or truncate `data/tasks.json.bak` or `data/tasks.db`.

---

### AGENT_TEST

**Files:** `tests/test_voice_handler.py`, `tests/test_intent_model.py` (to create)

**Scope:** Unittest suite — runs after every code change.

**Do:**
- After any AGENT_CODE change: run `python -m unittest tests/` and report pass/fail counts.
- Create `tests/test_intent_model.py` with tests covering: model loads without error, each of the 8 intents is predicted correctly for 3 canonical examples, confidence threshold rejects ambiguous input.
- If any of the original 24 tests regress, report to ORCHESTRATOR immediately.

**Do NOT:**
- Modify `voice_handler.py` to make tests pass — report the failure instead.

---

### AGENT_DOCS

**Files:** `README.md`, `walkthrough.md`, `scripts/train_model.py`, `scripts/entity_extractor.py`, `scripts/export_logs_to_dataset.py`

**Scope:** Supporting scripts and documentation.

**Do:**
- Create the three scripts under `scripts/` exactly as shown in Steps 2, 3, and 5 of this guide.
- Update `README.md` to add a "ML Model" section listing: how to train, where model is saved, fallback behavior.
- Keep `walkthrough.md` focused on end-user usage — do not add ML internals there.

**Do NOT:**
- Modify any Python logic in `voice_handler.py` or `task_manager.py`.

---

## Goal

Replace the rule-based `process_phrase()` in `voice_handler.py` with a trained intent classifier + entity extractor. Google Speech API stays. Only the post-transcription logic changes.

## Architecture

```
BEFORE: audio → Google STT → text → process_phrase() [regex/rules] → action
AFTER:  audio → Google STT → text → IntentClassifier → EntityExtractor → action
```

---

## Step 1 — Build the Dataset

Create `data/dataset.csv`:

```csv
text,intent
"adicionar comprar café",add_task
"deletar número 2",delete_task
"concluir a 1",complete_task
"mudar café para comprar leite",edit_task
"número 3 com prioridade alta",change_priority
"quais são minhas tarefas",list_tasks
"ligar jar",wake
"desligar jarvis",sleep
"comprar pão",add_task
```

**Intent classes:**

| Intent | Examples |
|---|---|
| `add_task` | "adicionar X", "crie X", "anotar X", bare nouns like "comprar pão" |
| `delete_task` | "deletar N", "remover X", "apagar número N" |
| `complete_task` | "concluir N", "finalizar X", "riscar a N" |
| `edit_task` | "mudar X para Y", "alterar N para Y" |
| `change_priority` | "X com prioridade alta", "número N como prioridade baixa" |
| `list_tasks` | "quais são minhas tarefas", "o que tenho pra fazer" |
| `wake` | "ligar jar", "olá jarvis", "acordar jarvis" |
| `sleep` | "desligar jarvis", "dormir", "silenciar" |

**Target:** 200–500 labeled examples per class. Use real phrases from `logs/jarvis.log` (lines containing `"Processando frase"`).

---

## Step 2 — Train

Install: `pip install scikit-learn pandas joblib`

Create `scripts/train_model.py`:

```python
import pandas as pd, joblib
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

df = pd.read_csv("data/dataset.csv")
X, y = df["text"].str.lower().tolist(), df["intent"].tolist()
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)

model = Pipeline([
    ("tfidf", TfidfVectorizer(ngram_range=(1, 2))),
    ("clf",   LogisticRegression(max_iter=1000, C=5.0))
])
model.fit(X_train, y_train)
print(classification_report(y_test, model.predict(X_test)))
joblib.dump(model, "data/intent_model.pkl")
```

Run: `python scripts/train_model.py`

**Minimum acceptable metrics:** accuracy > 90%, per-class precision/recall > 85%.

---

## Step 3 — Entity Extractor

Create `scripts/entity_extractor.py`:

```python
import re

WORD_TO_NUM = {
    "um":1,"uma":1,"dois":2,"duas":2,"três":3,"tres":3,
    "quatro":4,"cinco":5,"seis":6,"sete":7,"oito":8,"nove":9,"dez":10
}
PRIORITY_MAP = {
    "alta":"Alta","alto":"Alta","média":"Média","media":"Média","baixa":"Baixa"
}
ADD_VERBS = ["adicionar","crie a tarefa","crie","criar","anotar","adicione","insira","inserir"]

def get_index(text):
    m = re.search(r'\b(\d+)\b', text)
    if m: return int(m.group(1))
    for w, n in WORD_TO_NUM.items():
        if re.search(r'\b'+w+r'\b', text.lower()): return n
    return None

def get_task_text(text):
    t = text
    for v in sorted(ADD_VERBS, key=len, reverse=True):
        if t.lower().startswith(v):
            t = t[len(v):].strip(); break
    return re.sub(r'com prioridade \w+|prioridade \w+', '', t, flags=re.IGNORECASE).strip()

def get_priority(text):
    m = re.search(r'prioridade\s+(\w+)', text, re.IGNORECASE)
    return PRIORITY_MAP.get(m.group(1).lower()) if m else None

def get_edit_parts(text):
    for sep in [" para ", " pra "]:
        i = text.lower().find(sep)
        if i != -1: return text[:i].strip(), text[i+len(sep):].strip()
    return None
```

---

## Step 4 — Replace `process_phrase`

In `voice_handler.py`, load the model in `__init__`:

```python
import joblib

# inside __init__, after existing setup:
try:
    self._intent_model = joblib.load(
        os.path.join(self.project_dir, "data/intent_model.pkl")
    )
    self.log("Intent model loaded.")
except FileNotFoundError:
    self._intent_model = None
    self.log("WARNING: intent_model.pkl not found. Falling back to rules.")
```

Replace `process_phrase` with:

```python
CONFIDENCE_THRESHOLD = 0.65

def process_phrase(self, text):
    if self._intent_model is None:
        return self._process_phrase_rules(text)   # keep old method as fallback

    phrase = text.lower().strip()
    self.log(f'Processando frase (ML): "{phrase}"')

    proba  = self._intent_model.predict_proba([phrase])[0]
    intent = self._intent_model.classes_[proba.argmax()]
    conf   = proba.max()
    self.log(f"Intent: {intent} ({conf:.2f})")

    if conf < CONFIDENCE_THRESHOLD:
        self.log("Confiança insuficiente. Ignorando.")
        return

    # Wake / sleep handled before active_mode check
    if intent == "wake":
        if not self.active_mode:
            self.active_mode = True
            self.play_chime(True)
            if self.gui_callback: self.gui_callback("status_active")
        return

    if intent == "sleep":
        if self.active_mode:
            self.active_mode = False
            self.play_chime(False)
            if self.gui_callback: self.gui_callback("status_inactive")
        return

    if not self.active_mode:
        return

    dispatch = {
        "add_task":        self._ml_add,
        "delete_task":     self._ml_delete,
        "complete_task":   self._ml_complete,
        "edit_task":       self._ml_edit,
        "change_priority": self._ml_priority,
        "list_tasks":      self._ml_list,
    }
    handler = dispatch.get(intent)
    if handler: handler(text)
```

Implement each `_ml_*` method using `entity_extractor` functions and the existing `task_manager.update_tasks()` pattern (same logic as current callbacks, but sourced from extractor instead of regex in-place).

---

## Step 5 — Retrain Workflow

```bash
# 1. Export new phrases from logs
python scripts/export_logs_to_dataset.py   # see below

# 2. Manually label new rows in data/dataset.csv

# 3. Retrain
python scripts/train_model.py

# 4. Regression test
python -m unittest tests/

# 5. Deploy
copy data\intent_model.pkl data\intent_model_backup.pkl
```

Log exporter (`scripts/export_logs_to_dataset.py`):

```python
import re
with open("logs/jarvis.log", encoding="utf-8") as f:
    lines = f.readlines()
phrases = [re.search(r'Processando frase.*?"(.+)"', l).group(1)
           for l in lines if "Processando frase" in l]
with open("data/dataset_unlabeled.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(phrases))
print(f"{len(phrases)} phrases exported for labeling.")
```

---

## Migration Phases

```
Phase 1 (now)     → rules only (current)
Phase 2           → collect + label 300+ examples from logs
Phase 3           → run ML in shadow mode (log predictions, don't act)
Phase 4           → ML primary, rules as fallback if conf < 0.65
Phase 5           → ML only, remove rule system
```

---

## Files to Create

```
data/
  dataset.csv              ← labeled training data
  intent_model.pkl         ← trained model (generated)
  intent_model_backup.pkl  ← previous version

scripts/
  train_model.py
  entity_extractor.py
  export_logs_to_dataset.py

tests/
  test_intent_model.py     ← unit tests for ML classifier
```
