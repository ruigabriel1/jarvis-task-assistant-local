import re

# Lê o log do Jarvis para encontrar todas as frases captadas
with open("logs/jarvis.log", encoding="utf-8") as f:
    lines = f.readlines()

# Extrai o texto contido entre aspas nas linhas com "Processando frase"
phrases = [re.search(r'Processando frase.*?"(.+)"', l).group(1)
           for l in lines if "Processando frase" in l]

# Salva as frases extraídas num arquivo para posterior etiquetagem manual
with open("data/dataset_unlabeled.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(phrases))

print(f"{len(phrases)} phrases exported for labeling.")
