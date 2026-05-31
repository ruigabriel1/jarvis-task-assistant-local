# 🎙️ Jarvis Task Assistant

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![GUI Framework](https://img.shields.io/badge/UI-CustomTkinter-darkblue.svg)](https://github.com/TomSchimansky/CustomTkinter)
[![Speech Recognition](https://img.shields.io/badge/Speech-SpeechRecognition-green.svg)](https://pypi.org/project/SpeechRecognition/)
[![AI Engine](https://img.shields.io/badge/AI-Gemini%201.5%20Flash-cyan.svg)](https://ai.google.dev/)
[![License](https://img.shields.io/badge/license-MIT-lightgrey.svg)](https://choosealicense.com/licenses/mit/)

O **Jarvis Task Assistant** é um aplicativo desktop de anotações e gerenciamento de tarefas minimalista e super-rápido, projetado para funcionar como um widget de alta performance no estilo "Post-it". Ele combina uma interface gráfica moderna e escura (CustomTkinter) com um **assistente de voz nativo** que utiliza modelos locais de inteligência artificial (Faster-Whisper) e Machine Learning customizado.

---

## 🌟 O Que o Jarvis Pode Fazer? (Comandos)

O Jarvis atua como o seu bloco de notas inteligente. Por enquanto, ele é capaz de gerenciar a sua lista de tarefas diretamente pelo microfone.

Aqui estão os principais comandos suportados:

1. **Ativar o assistente:**
   - Diga: *"Ligar Jarvis"*, *"Olá Jarvis"*, *"Acordar Jarvis"* ou pressione o atalho `Ctrl+Shift+J`.
2. **Adicionar Tarefas:**
   - Diga: *"Adicionar comprar café com prioridade alta"*
   - Diga: *"Criar tarefa: revisar código"*
3. **Concluir Tarefas (pelo número ou nome):**
   - Diga: *"Concluir a tarefa número 2"*
   - Diga: *"Finalizar comprar café"*
4. **Remover Tarefas:**
   - Diga: *"Apagar a tarefa 3"*
   - Diga: *"Remover revisar código"*
5. **Alterar e Editar Tarefas:**
   - Diga: *"Alterar a tarefa X para Y com prioridade média"*
6. **Desativar o assistente:**
   - Diga: *"Desligar Jarvis"*, *"Silenciar"* ou clique no indicador luminoso.

---

## 🚀 Como Usar (Passo a Passo)

Siga os passos abaixo para começar a utilizar o assistente no seu computador:

### 1. Pré-requisitos
Certifique-se de ter o Python instalado e configurado no PATH do Windows. Instale as dependências executando o comando a seguir no terminal/PowerShell:
```bash
pip install customtkinter speechrecognition pyttsx3 pyaudio pythoncom pandas scikit-learn faster-whisper edge_tts joblib
```
> **Nota:** No Windows, o `pyaudio` é necessário para captura de microfone. Se falhar, instale usando o `pip install pipwin` seguido de `pipwin install pyaudio`.

### 2. Configurar a Chave de API
Crie um arquivo chamado `config.json` na raiz do projeto (mesmo nível da pasta `src/`) e adicione:
```json
{
  "GEMINI_API_KEY": "SUA_API_KEY_AQUI",
  "HOTKEY": "ctrl+shift+j",
  "speech_engine": "auto"
}
```

### 3. Iniciar o Assistente
Você pode iniciar o Jarvis de duas maneiras:
- Dê duplo clique no arquivo **`scripts/start-jarvis.bat`**.
- Ou rode o executável direto no terminal: `python src/ui/app.pyw`

O aplicativo abrirá em segundo plano silenciosamente (como um bloco de notas fixado na tela). 
- **Verde/Azul:** Assistente escutando.
- **Cinza:** Assistente dormindo.

---

## 🧠 Como Treinar a Inteligência (Machine Learning)

O Jarvis não depende de regras engessadas (IF/ELSE) para entender o que você diz; ele utiliza um modelo de Machine Learning (`intent_model.pkl`) treinado com PLN (TF-IDF e Regressão Logística). Isso significa que você pode ensiná-lo novas formas de falar!

**Para treinar o seu Jarvis:**

1. **Gere dados a partir do seu uso diário:**
   Sempre que você usa o Jarvis, as frases ditas são gravadas nos logs (`logs/jarvis.log`). Para extraí-las para o formato de treinamento, rode no terminal:
   ```bash
   python scripts/export_logs_to_dataset.py
   ```
   *Isso atualizará o arquivo base `data/dataset.csv`.*

2. **Rotule os novos dados:**
   Abra o arquivo `data/dataset.csv`. Você verá as frases extraídas. Classifique a coluna `intent` para cada frase nova com uma das intenções suportadas:
   `wake`, `sleep`, `add_task`, `delete_task`, `complete_task`, `edit_task`, `change_priority` ou `list_tasks`.

3. **Treine o Novo Modelo:**
   Com o seu dataset enriquecido com suas gírias e sotaque, recompile o "cérebro" do Jarvis:
   ```bash
   python scripts/train_model.py
   ```
   *O novo modelo será salvo como `data/intent_model.pkl` e carregado instantaneamente no próximo boot.*

---

## 📂 Estrutura da Arquitetura Profissional

O projeto conta com um isolamento de camadas (MVC e Serviços) limpo e modular:

```text
jarvis-task-assistant/
├── src/
│   ├── core/                  # Persistência de Dados e Banco (task_manager.py)
│   ├── services/              # Motor Lógico e de Inteligência
│   │   ├── audio_transcriber.py   # Lida com o Microfone e Speech-to-Text
│   │   ├── speech_synthesizer.py  # Lida com a Fala do bot (Edge-TTS)
│   │   ├── intent_parser.py       # Ponto de ML e Inferência
│   │   └── voice_handler.py       # Controlador orquestrador do ecossistema
│   └── ui/                    # Front-end (app.pyw)
├── data/                      # Banco SQLite (tasks.db) e Modelo (intent_model.pkl)
├── logs/                      # Log de execução (jarvis.log)
├── scripts/                   # Scripts utilitários de ML e Batch
├── tests/                     # Testes Unitários
├── config.json                # Configurações globais e chaves
└── README.md                  # Documentação principal
```

---

## 🛡️ Solução de Problemas (Troubleshooting)

* **Não Escuta:** Verifique em *Configurações do Windows > Privacidade > Microfone* se o acesso de desktop está liberado.
* **Corrupção de Áudio na Fala:** O sistema agora usa uma arquitetura de *Queue* isolada, garantindo estabilidade no Text-to-Speech nativo e Edge-TTS.
* **Falha de Inicialização do Modelo Offline (Faster-Whisper):** O aplicativo possui *fallback* integrado. Se faltar RAM de vídeo para o processamento offline ou a GPU não suportar, o Whisper delegará a função perfeitamente para o Google API Online.

### 🧪 Testes Unitários
Rode offline: `python -m unittest tests/test_voice_handler.py`
