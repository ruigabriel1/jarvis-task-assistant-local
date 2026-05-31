import pandas as pd, joblib
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

# Lê o arquivo CSV contendo os dados de treinamento
df = pd.read_csv("data/dataset.csv")

# Extrai os textos em minúsculo e suas respectivas intenções
X, y = df["text"].str.lower().tolist(), df["intent"].tolist()

# Divide os dados em conjuntos de treino e teste, mantendo a proporção de cada intenção
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)

# Cria um pipeline que transforma o texto em features (TF-IDF) e treina um modelo de regressão logística
model = Pipeline([
    ("tfidf", TfidfVectorizer(ngram_range=(1, 2))),
    ("clf",   LogisticRegression(max_iter=1000, C=5.0))
])

# Treina o modelo com os dados de treino
model.fit(X_train, y_train)

# Avalia o modelo e imprime as métricas usando os dados de teste
print(classification_report(y_test, model.predict(X_test)))

# Salva o modelo treinado em um arquivo para ser carregado pelo assistente
joblib.dump(model, "data/intent_model.pkl")
