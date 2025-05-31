"""
Ollama Client - клієнт для роботи з локальною Llama моделлю через Ollama
Відповідає за переклади, граматичні пояснення та кастомні запити
"""

import requests
import json
import logging
from typing import Dict, Optional
import time

class OllamaClient:
    """Клієнт для роботи з Ollama API"""
    
    def __init__(self, 
                 model: str = "llama3.1:8b", 
                 base_url: str = "http://localhost:11434"):
        """
        Ініціалізація Ollama клієнта
        
        Args:
            model: Назва моделі (llama3.1:8b)
            base_url: URL Ollama сервера
        """
        self.model = model
        self.base_url = base_url
        self.logger = logging.getLogger(__name__)
        
        # Налаштування для різних типів запитів
        self.prompts = {
            "translate": """Переклади це англійське речення українською мовою. 
Дай тільки переклад без додаткових пояснень та коментарів:

Речення: "{text}"

Переклад:""",
            
            "grammar": """Проаналізуй це англійське речення з граматичної точки зору. 
Поясни українською мовою основні граматичні елементи:

- Які часи дієслів використані
- Важливі граматичні конструкції
- Складні слова чи вирази
- Корисні поради для запам'ятовування

Речення: "{text}"

Граматичний аналіз:""",
            
            "custom": """Контекст: англійське речення "{text}"

Запит користувача: {prompt}

Відповідь українською мовою:"""
        }
    
    def is_available(self) -> bool:
        """
        Перевіряє чи доступний Ollama сервер
        
        Returns:
            True якщо Ollama працює
        """
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                # Перевіряємо чи є потрібна модель
                models = response.json().get("models", [])
                model_names = [model.get("name", "") for model in models]
                return any(self.model in name for name in model_names)
            return False
        except Exception as e:
            self.logger.debug(f"Ollama недоступний: {e}")
            return False
    
    def _make_request(self, prompt: str, max_retries: int = 3) -> Dict[str, any]:
        """
        Робить запит до Ollama API
        
        Args:
            prompt: Текст промпту
            max_retries: Максимальна кількість спроб
            
        Returns:
            Словник з результатом: {"success": bool, "text": str, "error": str}
        """
        for attempt in range(max_retries):
            try:
                data = {
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,  # Менше креативності для перекладів
                        "top_p": 0.9,
                        "num_ctx": 2048
                    }
                }
                
                self.logger.debug(f"Запит до Ollama (спроба {attempt + 1})")
                
                response = requests.post(
                    f"{self.base_url}/api/generate",
                    json=data,
                    timeout=60  # 1 хвилина таймаут
                )
                
                if response.status_code == 200:
                    result = response.json()
                    generated_text = result.get("response", "").strip()
                    
                    if generated_text:
                        return {
                            "success": True,
                            "text": generated_text,
                            "error": None
                        }
                    else:
                        return {
                            "success": False,
                            "text": "",
                            "error": "Порожня відповідь від AI"
                        }
                else:
                    error_msg = f"HTTP {response.status_code}: {response.text}"
                    self.logger.warning(f"Помилка Ollama: {error_msg}")
                    
                    if attempt == max_retries - 1:
                        return {
                            "success": False,
                            "text": "",
                            "error": error_msg
                        }
                    
                    # Чекаємо перед повторною спробою
                    time.sleep(2 ** attempt)
                    
            except requests.exceptions.Timeout:
                error_msg = "Таймаут запиту до AI (60 секунд)"
                self.logger.warning(error_msg)
                
                if attempt == max_retries - 1:
                    return {
                        "success": False,
                        "text": "",
                        "error": error_msg
                    }
                
                time.sleep(2 ** attempt)
                
            except Exception as e:
                error_msg = f"Помилка запиту: {str(e)}"
                self.logger.error(error_msg)
                
                if attempt == max_retries - 1:
                    return {
                        "success": False,
                        "text": "",
                        "error": error_msg
                    }
                
                time.sleep(2 ** attempt)
        
        return {
            "success": False,
            "text": "",
            "error": "Вичерпано всі спроби"
        }
    
    def translate(self, text: str) -> Dict[str, any]:
        """
        Перекладає англійський текст українською
        
        Args:
            text: Англійський текст для перекладу
            
        Returns:
            {"success": bool, "text": str, "error": str}
        """
        if not text.strip():
            return {
                "success": False,
                "text": "",
                "error": "Порожній текст для перекладу"
            }
        
        prompt = self.prompts["translate"].format(text=text.strip())
        return self._make_request(prompt)
    
    def explain_grammar(self, text: str) -> Dict[str, any]:
        """
        Пояснює граматику англійського речення
        
        Args:
            text: Англійське речення для аналізу
            
        Returns:
            {"success": bool, "text": str, "error": str}
        """
        if not text.strip():
            return {
                "success": False,
                "text": "",
                "error": "Порожній текст для аналізу"
            }
        
        prompt = self.prompts["grammar"].format(text=text.strip())
        return self._make_request(prompt)
    
    def custom_request(self, text: str, user_prompt: str) -> Dict[str, any]:
        """
        Обробляє кастомний запит користувача
        
        Args:
            text: Контекст - англійське речення
            user_prompt: Запит користувача
            
        Returns:
            {"success": bool, "text": str, "error": str}
        """
        if not text.strip() or not user_prompt.strip():
            return {
                "success": False,
                "text": "",
                "error": "Порожній текст або запит"
            }
        
        prompt = self.prompts["custom"].format(
            text=text.strip(), 
            prompt=user_prompt.strip()
        )
        return self._make_request(prompt)
    
    def get_model_info(self) -> Dict[str, any]:
        """
        Отримує інформацію про модель
        
        Returns:
            Словник з інформацією про модель
        """
        try:
            response = requests.get(f"{self.base_url}/api/show", 
                                  json={"name": self.model}, 
                                  timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"Помилка отримання інформації: {response.status_code}"}
                
        except Exception as e:
            return {"error": f"Помилка: {str(e)}"}
    
    def test_connection(self) -> Dict[str, any]:
        """
        Тестує підключення до Ollama
        
        Returns:
            Результат тесту
        """
        if not self.is_available():
            return {
                "success": False,
                "message": f"Ollama недоступний або модель {self.model} не встановлена"
            }
        
        # Тестовий запит
        test_result = self.translate("Hello world")
        
        if test_result["success"]:
            return {
                "success": True,
                "message": f"Ollama працює з моделлю {self.model}",
                "test_translation": test_result["text"]
            }
        else:
            return {
                "success": False,
                "message": f"Помилка тестового запиту: {test_result['error']}"
            }

# Приклад використання
if __name__ == "__main__":
    # Налаштування логування для тестування
    logging.basicConfig(level=logging.DEBUG)
    
    # Створення клієнта
    client = OllamaClient()
    
    # Тест підключення
    print("=== Тест підключення до Ollama ===")
    test_result = client.test_connection()
    print(f"Результат: {test_result}")
    
    if test_result["success"]:
        # Тест перекладу
        print("\n=== Тест перекладу ===")
        translation = client.translate("I love playing video games")
        print(f"Переклад: {translation}")
        
        # Тест граматики
        print("\n=== Тест граматичного аналізу ===")
        grammar = client.explain_grammar("I will be going to the store")
        print(f"Граматика: {grammar}")
        
        # Тест кастомного запиту
        print("\n=== Тест кастомного запиту ===")
        custom = client.custom_request("Hello world", "Поясни слово Hello")
        print(f"Кастомний запит: {custom}")