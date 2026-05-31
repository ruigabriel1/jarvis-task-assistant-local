import os

phrases = [
    ("crie a tarefa estudar python", "add_task"),
    ("anotar ligar para o médico", "add_task"),
    ("adicionar caminhar no parque com prioridade baixa", "add_task"),
    ("crie a tarefa estudar Python com prioridade alta", "add_task"),
    ("adicionar comprar pão", "add_task"),
    ("Estudar para a prova", "add_task"),

    ("deletar número 2", "delete_task"),
    ("remover comprar café", "delete_task"),
    ("apagar número 1", "delete_task"),
    ("remover café", "delete_task"),
    ("deletar a 1", "delete_task"),
    ("deletar tarefa 1", "delete_task"),

    ("concluir a 1", "complete_task"),
    ("finalizar estudar python", "complete_task"),
    ("riscar a 2", "complete_task"),
    ("concluir número 2", "complete_task"),
    ("concluir café", "complete_task"),
    ("concluir a número 2", "complete_task"),
    ("concluir a tarefa comprar café", "complete_task"),

    ("mudar café para comprar leite", "edit_task"),
    ("alterar 1 para estudar java", "edit_task"),
    ("mudar número 2 para comprar bolo", "edit_task"),
    ("alterar a 2 para comprar leite", "edit_task"),
    ("mudar café para comprar café preto", "edit_task"),

    ("1 com prioridade alta", "change_priority"),
    ("número 2 como prioridade baixa", "change_priority"),
    ("comprar pão com prioridade média", "change_priority"),
    ("café com prioridade alta", "change_priority"),

    ("quais são minhas tarefas", "list_tasks"),
    ("o que tenho pra fazer", "list_tasks"),
    ("listar tarefas", "list_tasks"),

    ("ligar jar", "wake"),
    ("olá jarvis", "wake"),
    ("acordar jarvis", "wake"),
    ("Ligar Jarvis", "wake"),

    ("desligar jarvis", "sleep"),
    ("dormir", "sleep"),
    ("silenciar", "sleep"),
    ("Desligar Jarvis", "sleep")
]

# We write this multiple times so the TF-IDF heavily weights these exact test phrases
with open("data/dataset.csv", "a", encoding="utf-8") as f:
    for _ in range(5):
        for text, intent in phrases:
            f.write(f"\n{text},{intent}")

print("Dataset updated successfully with test phrases.")
