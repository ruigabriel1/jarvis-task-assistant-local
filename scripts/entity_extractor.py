import re

# Dicionário para converter números por extenso em valores inteiros
WORD_TO_NUM = {
    "um":1,"uma":1,"dois":2,"duas":2,"três":3,"tres":3,
    "quatro":4,"cinco":5,"seis":6,"sete":7,"oito":8,"nove":9,"dez":10
}

# Mapa para normalizar os níveis de prioridade
PRIORITY_MAP = {
    "alta":"Alta","alto":"Alta","média":"Média","media":"Média","baixa":"Baixa"
}

# Verbos de ação comuns utilizados no início de frases
ALL_VERBS = [
    "adicionar", "crie a tarefa", "crie", "criar", "anotar", "adicione", "insira", "inserir",
    "concluir", "finalizar", "marcar como concluída", "marcar como concluida", "riscar", "completar",
    "remover", "deletar", "excluir", "apagar",
    "alterar", "atualizar", "mudar", "editar", "corrigir"
]

PREFIXES = [
    "a tarefa ", "o id ", "do id ", "de id ", "número ", "numero ", "nº ", "no ", 
    "tarefa ", "tarefas ", "a ", "o ", "as ", "os ", "uma tarefa ", "o compromisso ", "o compromisso de "
]

def get_index(text):
    """Retorna um número extraído do texto, útil para identificar o ID/Índice da tarefa."""
    # Busca um número digitado
    m = re.search(r'\b(\d+)\b', text)
    if m: return int(m.group(1))
    
    # Se não encontrar dígitos, busca o número escrito por extenso
    for w, n in WORD_TO_NUM.items():
        if re.search(r'\b'+w+r'\b', text.lower()): return n
    return None

def get_task_text(text):
    """Extrai o texto real da tarefa removendo verbos iniciais e declarações de prioridade."""
    t = text
    # Verifica e remove o verbo de ação do início do texto
    for v in sorted(ALL_VERBS, key=len, reverse=True):
        if t.lower().startswith(v):
            t = t[len(v):].strip(); break
            
    # Remove prefixos comuns
    for p in sorted(PREFIXES, key=len, reverse=True):
        if t.lower().startswith(p):
            t = t[len(p):].strip(); break

    # Remove citações sobre a prioridade de dentro do texto da tarefa
    return re.sub(r'com prioridade \w+|prioridade \w+', '', t, flags=re.IGNORECASE).strip()

def get_priority(text):
    """Identifica e retorna o nível de prioridade especificado na frase."""
    m = re.search(r'prioridade\s+(\w+)', text, re.IGNORECASE)
    return PRIORITY_MAP.get(m.group(1).lower()) if m else None

def get_edit_parts(text):
    """Separa o texto de edição em duas partes: de / para."""
    for sep in [" para ", " pra "]:
        i = text.lower().find(sep)
        if i != -1: return text[:i].strip(), text[i+len(sep):].strip()
    return None
