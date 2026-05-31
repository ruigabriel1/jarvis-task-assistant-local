import unittest
import os
import joblib

class TestIntentModel(unittest.TestCase):
    """
    Testes para o classificador de intenções (ML).
    Verifica o carregamento, a precisão das classes com exemplos canônicos
    e o limiar de confiança (confidence threshold).
    """
    
    @classmethod
    def setUpClass(cls):
        # Define o caminho para o modelo
        cls.project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cls.model_path = os.path.join(cls.project_dir, "data", "intent_model.pkl")
        
    def test_01_model_loads_without_error(self):
        """Testa se o arquivo do modelo existe e pode ser carregado sem erros."""
        self.assertTrue(os.path.exists(self.model_path), "Arquivo intent_model.pkl não encontrado.")
        try:
            model = joblib.load(self.model_path)
            self.assertIsNotNone(model, "O modelo carregado não deveria ser None.")
        except Exception as e:
            self.fail(f"Erro ao carregar o modelo: {e}")

    def test_02_predictions_for_8_classes(self):
        """
        Testa as previsões para as 8 intenções, usando 3 exemplos canônicos para cada.
        """
        model = joblib.load(self.model_path)
        
        # Dicionário com os exemplos canônicos mapeados para as classes esperadas
        test_cases = {
            "add_task": [
                "adicionar comprar café",
                "crie a tarefa estudar python",
                "anotar ligar para o médico",
                "comprar pão" # Extra, mas usaremos os 3 primeiros
            ][:3],
            "delete_task": [
                "deletar número 2",
                "remover comprar café",
                "apagar número 1"
            ],
            "complete_task": [
                "concluir a 1",
                "finalizar estudar python",
                "riscar a 2"
            ],
            "edit_task": [
                "mudar café para comprar leite",
                "alterar 1 para estudar java",
                "mudar número 2 para comprar bolo"
            ],
            "change_priority": [
                "1 com prioridade alta",
                "número 2 como prioridade baixa",
                "comprar pão com prioridade média"
            ],
            "list_tasks": [
                "quais são minhas tarefas",
                "o que tenho pra fazer",
                "listar tarefas"
            ],
            "wake": [
                "ligar jar",
                "olá jarvis",
                "acordar jarvis"
            ],
            "sleep": [
                "desligar jarvis",
                "dormir",
                "silenciar"
            ]
        }
        
        # Para cada intenção, verifica se os 3 exemplos são classificados corretamente
        for expected_intent, phrases in test_cases.items():
            for phrase in phrases:
                with self.subTest(phrase=phrase, expected_intent=expected_intent):
                    proba = model.predict_proba([phrase])[0]
                    intent = model.classes_[proba.argmax()]
                    self.assertEqual(
                        intent, 
                        expected_intent, 
                        f"A frase '{phrase}' deveria ser '{expected_intent}', mas foi '{intent}'."
                    )

    def test_03_confidence_threshold(self):
        """
        Testa se o limiar de confiança (CONFIDENCE_THRESHOLD = 0.65) está sendo
        respeitado. Frases canônicas devem ter confiança acima do limiar,
        enquanto frases ambíguas deveriam idealmente ter menos ou mostrar como a confiança funciona.
        """
        model = joblib.load(self.model_path)
        confidence_threshold = 0.65
        
        # Testando uma frase muito clara para garantir que ultrapassa o threshold
        phrase_clear = "adicionar comprar leite"
        proba_clear = model.predict_proba([phrase_clear])[0]
        conf_clear = proba_clear.max()
        
        self.assertGreaterEqual(
            conf_clear, 
            confidence_threshold,
            f"A confiança para a frase clara '{phrase_clear}' foi {conf_clear:.2f}, "
            f"esperado ser >= {confidence_threshold}."
        )

if __name__ == "__main__":
    unittest.main()
