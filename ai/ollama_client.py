"""
Ollama Client - клієнт для роботи з локальною Llama моделлю через Ollama
ОНОВЛЕНО: Лаконічні відповіді з контекстом TES Skyrim
"""

import requests
import json
import logging
from typing import Dict, Optional
import time

class OllamaClient:
    """Клієнт для роботи з Ollama API з оновленими промптами для Skyrim"""

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

        # ОНОВЛЕНІ ПРОМПТИ для Skyrim з лаконічними відповідями
        self.prompts = {
            "translate": """Переклади це англійське речення українською мовою. 
Дай тільки переклад без додаткових пояснень та коментарів:

Речення: "{text}"

Переклад:""",

            "grammar": """Ти аналізуєш діалоги з гри The Elder Scrolls V: Skyrim. 
Дай лаконічну відповідь у такому форматі:

🇺🇦 ПЕРЕКЛАД: [точний переклад українською]

📚 ГРАМАТИКА: [коротке пояснення 1-2 речення про основні граматичні елементи]

Речення з Skyrim: "{text}"

ВАЖЛИВО: 
- Враховуй фантезійний контекст (драгони, магія, Nordic культура)
- Середньовічний стиль мовлення
- Ігрові терміни залишай англійською в дужках
- Будь лаконічним, максимум 3-4 рядки загалом

Відповідь:""",

            "custom": """Контекст: діалог з гри Skyrim "{text}"

Запит користувача: {prompt}

Відповідь українською (враховуй фантезійний контекст TES):"""
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
        Робить запит до Ollama API з оптимізованими параметрами для коротких відповідей

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
                        "temperature": 0.2,  # Менше креативності для стабільності
                        "top_p": 0.8,        # Більш фокусовані відповіді
                        "num_ctx": 2048,     # Контекст
                        "max_tokens": 150,   # ОБМЕЖЕННЯ: максимум 150 токенів для лаконічності
                        "stop": ["\n\n", "---", "Приклад:", "Додатково:"]  # Стоп-слова для коротких відповідей
                    }
                }

                self.logger.debug(f"Запит до Ollama (спроба {attempt + 1})")

                response = requests.post(
                    f"{self.base_url}/api/generate",
                    json=data,
                    timeout=30  # Зменшено з 60 до 30 секунд
                )

                if response.status_code == 200:
                    result = response.json()
                    generated_text = result.get("response", "").strip()

                    # ОБРІЗАННЯ: видаляємо зайвий текст після стоп-слів
                    generated_text = self._trim_response(generated_text)

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
                error_msg = "Таймаут запиту до AI (30 секунд)"
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

    def _trim_response(self, text: str) -> str:
        """
        Обрізає відповідь для лаконічності

        Args:
            text: Оригінальна відповідь

        Returns:
            Обрізана відповідь
        """
        # Видаляємо зайві абзаци після першого блоку
        lines = text.split('\n')

        # Шукаємо кінець основної відповіді
        main_content = []
        found_grammar = False

        for line in lines:
            line = line.strip()
            if not line:
                if found_grammar:
                    break  # Зупиняємось після граматичного блоку
                continue

            # Ігноруємо зайві пояснення
            if any(skip in line.lower() for skip in ["приклад:", "додатково:", "зауваження:", "примітка:", "детальніше:"]):
                break

            main_content.append(line)

            # Позначаємо що знайшли граматичний блок
            if "📚" in line or "граматика:" in line.lower():
                found_grammar = True

        result = '\n'.join(main_content)

        # Обмежуємо довжину
        if len(result) > 300:  # Максимум 300 символів
            sentences = result.split('. ')
            trimmed = []
            current_length = 0

            for sentence in sentences:
                if current_length + len(sentence) > 280:
                    break
                trimmed.append(sentence)
                current_length += len(sentence) + 2

            result = '. '.join(trimmed)
            if not result.endswith('.') and not result.endswith('!') and not result.endswith('?'):
                result += '.'

        return result

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
        Пояснює граматику англійського речення з контекстом Skyrim
        ОНОВЛЕНО: Лаконічний формат з перекладом

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
        result = self._make_request(prompt)

        # Додаткова обробка для забезпечення правильного формату
        if result["success"]:
            response_text = result["text"]

            # Перевіряємо чи є правильний формат
            if "🇺🇦" not in response_text and "📚" not in response_text:
                # Якщо формат неправильний, додаємо структуру
                lines = response_text.split('\n')
                if len(lines) >= 2:
                    translation = lines[0].strip()
                    grammar = ' '.join(lines[1:]).strip()

                    formatted_response = f"🇺🇦 ПЕРЕКЛАД: {translation}\n\n📚 ГРАМАТИКА: {grammar}"
                    result["text"] = formatted_response

        return result

    def custom_request(self, text: str, user_prompt: str) -> Dict[str, any]:
        """
        Обробляє кастомний запит користувача з контекстом Skyrim

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
        Тестує підключення до Ollama з Skyrim контекстом

        Returns:
            Результат тесту
        """
        if not self.is_available():
            return {
                "success": False,
                "message": f"Ollama недоступний або модель {self.model} не встановлена"
            }

        # Тестовий запит з Skyrim фразою
        test_result = self.explain_grammar("You're finally awake!")

        if test_result["success"]:
            return {
                "success": True,
                "message": f"Ollama працює з моделлю {self.model} для Skyrim контексту",
                "test_response": test_result["text"]
            }
        else:
            return {
                "success": False,
                "message": f"Помилка тестового запиту: {test_result['error']}"
            }


# Приклад використання з Skyrim фразами
if __name__ == "__main__":
    # Налаштування логування для тестування
    logging.basicConfig(level=logging.DEBUG)

    # Створення клієнта
    client = OllamaClient()

    # Тест підключення з Skyrim
    print("=== Тест підключення до Ollama з Skyrim ===")
    test_result = client.test_connection()
    print(f"Результат: {test_result}")

    if test_result["success"]:
        # Тест граматики з відомими Skyrim фразами
        print("\n=== Тест граматичного аналізу Skyrim фраз ===")

        skyrim_phrases = [
            "You're finally awake!",
            "I used to be an adventurer like you, then I took an arrow to the knee.",
            "Hey, you. You're finally awake.",
            "Damn you Stormcloaks. Skyrim was fine until you came along.",
            "Fus Ro Dah!"
        ]

        for phrase in skyrim_phrases:
            print(f"\n--- Фраза: {phrase} ---")
            grammar = client.explain_grammar(phrase)
            if grammar["success"]:
                print(f"✅ Відповідь:\n{grammar['text']}")
            else:
                print(f"❌ Помилка: {grammar['error']}")