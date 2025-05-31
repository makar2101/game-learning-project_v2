"""
AI Manager - головний менеджер для роботи з AI
ОНОВЛЕНО: Підтримка лаконічних відповідей та Skyrim контексту
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

from ai.ollama_client import OllamaClient

class AIManager:
    """Головний менеджер AI сервісів з підтримкою Skyrim контексту"""

    def __init__(self, config_file: str = "config/ai_config.json"):
        """
        Ініціалізація AI менеджера

        Args:
            config_file: Шлях до конфігураційного файлу
        """
        self.config_file = Path(config_file)
        self.logger = logging.getLogger(__name__)

        # Завантажуємо конфігурацію
        self.config = self._load_config()

        # Ініціалізуємо Ollama клієнт
        self.ollama_client = None
        self._initialize_ollama()

        # Статистика використання з новими типами
        self.usage_stats = {
            "translations": 0,
            "grammar_explanations": 0,
            "skyrim_analyses": 0,  # НОВИЙ: специфічні аналізи Skyrim
            "custom_requests": 0,
            "errors": 0,
            "avg_response_length": 0.0,  # НОВИЙ: середня довжина відповідей
            "last_request": None
        }

    def _load_config(self) -> Dict:
        """Завантажує конфігурацію AI"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                self.logger.info("Конфігурація AI завантажена")
                return config
            else:
                # Створюємо конфігурацію за замовчуванням з Skyrim параметрами
                default_config = self._create_default_config()
                self._save_config(default_config)
                return default_config

        except Exception as e:
            self.logger.error(f"Помилка завантаження конфігурації: {e}")
            return self._create_default_config()

    def _create_default_config(self) -> Dict:
        """Створює конфігурацію за замовчуванням з Skyrim налаштуваннями"""
        return {
            "ollama": {
                "enabled": True,
                "model": "llama3.1:8b",
                "base_url": "http://localhost:11434",
                "timeout": 30,  # ЗМЕНШЕНО з 60 до 30 для швидших відповідей
                "max_retries": 3,
                "temperature": 0.2  # ЗМЕНШЕНО для більш стабільних відповідей
            },
            "skyrim_context": {  # НОВИЙ: Skyrim специфічні налаштування
                "enable_fantasy_terms": True,
                "enable_nordic_context": True,
                "max_response_length": 300,
                "preferred_format": "concise"  # лаконічний формат
            },
            "response_formatting": {  # НОВИЙ: налаштування форматування
                "include_translation": True,
                "include_emojis": True,
                "max_grammar_explanation": 100,  # максимум 100 символів для граматики
                "auto_trim": True
            },
            "auto_check_updates": True,
            "preferred_language": "uk",
            "cache_responses": True,
            "version": "2.0"
        }

    def _save_config(self, config: Dict):
        """Зберігає конфігурацію"""
        try:
            # Створюємо папку config якщо її немає
            self.config_file.parent.mkdir(parents=True, exist_ok=True)

            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            self.logger.info("Конфігурація AI збережена")

        except Exception as e:
            self.logger.error(f"Помилка збереження конфігурації: {e}")

    def _initialize_ollama(self):
        """Ініціалізує Ollama клієнт"""
        try:
            if self.config["ollama"]["enabled"]:
                self.ollama_client = OllamaClient(
                    model=self.config["ollama"]["model"],
                    base_url=self.config["ollama"]["base_url"]
                )

                # Перевіряємо доступність
                if self.ollama_client.is_available():
                    self.logger.info(f"Ollama клієнт ініціалізований: {self.config['ollama']['model']}")
                    self.logger.info("✨ Skyrim контекст активовано для Fantasy RPG діалогів")
                else:
                    self.logger.warning("Ollama клієнт недоступний")
            else:
                self.logger.info("Ollama вимкнений в конфігурації")

        except Exception as e:
            self.logger.error(f"Помилка ініціалізації Ollama: {e}")
            self.ollama_client = None

    def is_available(self) -> bool:
        """
        Перевіряє чи доступний AI

        Returns:
            True якщо AI працює
        """
        return self.ollama_client and self.ollama_client.is_available()

    def get_status(self) -> Dict:
        """
        Отримує статус AI менеджера з Skyrim інформацією

        Returns:
            Словник зі статусом
        """
        return {
            "available": self.is_available(),
            "model": self.config["ollama"]["model"],
            "client": "ollama" if self.ollama_client else None,
            "skyrim_context": self.config.get("skyrim_context", {}).get("enable_fantasy_terms", False),
            "response_format": self.config.get("response_formatting", {}).get("preferred_format", "standard"),
            "usage_stats": self.usage_stats.copy(),
            "last_check": datetime.now().isoformat()
        }

    def translate_text(self, text: str) -> Dict:
        """
        Перекладає текст українською з врахуванням Skyrim контексту

        Args:
            text: Англійський текст

        Returns:
            {"success": bool, "result": str, "error": str, "cached": bool}
        """
        if not self.is_available():
            return {
                "success": False,
                "result": "",
                "error": "AI недоступний. Перевірте чи запущений Ollama",
                "cached": False
            }

        try:
            self.logger.debug(f"Переклад тексту: {text[:50]}...")

            result = self.ollama_client.translate(text)

            if result["success"]:
                self.usage_stats["translations"] += 1
                self.usage_stats["last_request"] = datetime.now().isoformat()
                self._update_avg_response_length(result["text"])

                return {
                    "success": True,
                    "result": result["text"],
                    "error": None,
                    "cached": False
                }
            else:
                self.usage_stats["errors"] += 1
                return {
                    "success": False,
                    "result": "",
                    "error": result["error"],
                    "cached": False
                }

        except Exception as e:
            self.usage_stats["errors"] += 1
            error_msg = f"Помилка перекладу: {str(e)}"
            self.logger.error(error_msg)

            return {
                "success": False,
                "result": "",
                "error": error_msg,
                "cached": False
            }

    def explain_grammar(self, text: str) -> Dict:
        """
        Пояснює граматику речення з врахуванням Skyrim контексту
        ОНОВЛЕНО: Лаконічний формат з перекладом

        Args:
            text: Англійське речення

        Returns:
            {"success": bool, "result": str, "error": str, "cached": bool, "is_skyrim": bool}
        """
        if not self.is_available():
            return {
                "success": False,
                "result": "",
                "error": "AI недоступний. Перевірте чи запущений Ollama",
                "cached": False,
                "is_skyrim": False
            }

        try:
            self.logger.debug(f"Граматичний аналіз: {text[:50]}...")

            # Визначаємо чи це Skyrim фраза
            is_skyrim_phrase = self._detect_skyrim_context(text)

            result = self.ollama_client.explain_grammar(text)

            if result["success"]:
                # Додаткова обробка для забезпечення лаконічності
                processed_result = self._post_process_grammar_response(result["text"])

                self.usage_stats["grammar_explanations"] += 1
                if is_skyrim_phrase:
                    self.usage_stats["skyrim_analyses"] += 1

                self.usage_stats["last_request"] = datetime.now().isoformat()
                self._update_avg_response_length(processed_result)

                return {
                    "success": True,
                    "result": processed_result,
                    "error": None,
                    "cached": False,
                    "is_skyrim": is_skyrim_phrase
                }
            else:
                self.usage_stats["errors"] += 1
                return {
                    "success": False,
                    "result": "",
                    "error": result["error"],
                    "cached": False,
                    "is_skyrim": is_skyrim_phrase
                }

        except Exception as e:
            self.usage_stats["errors"] += 1
            error_msg = f"Помилка граматичного аналізу: {str(e)}"
            self.logger.error(error_msg)

            return {
                "success": False,
                "result": "",
                "error": error_msg,
                "cached": False,
                "is_skyrim": False
            }

    def _detect_skyrim_context(self, text: str) -> bool:
        """
        Визначає чи містить текст Skyrim специфічні елементи

        Args:
            text: Текст для аналізу

        Returns:
            True якщо це Skyrim контекст
        """
        skyrim_keywords = [
            # Відомі фрази
            "finally awake", "arrow to the knee", "fus ro dah", "dragonborn",
            "stormcloaks", "imperial", "whiterun", "solitude", "riften",
            # Ігрові терміни
            "septim", "jarl", "thane", "shout", "thu'um", "greybeard",
            "companion", "thieves guild", "dark brotherhood", "college of winterhold",
            # Персонажі
            "ulfric", "tullius", "delphine", "esbern", "lydia", "faendal",
            # Раси
            "nord", "imperial", "redguard", "breton", "dunmer", "altmer",
            "bosmer", "orsimer", "khajiit", "argonian",
            # Локації
            "skyrim", "tamriel", "sovngarde", "blackreach", "dwemer"
        ]

        text_lower = text.lower()
        return any(keyword in text_lower for keyword in skyrim_keywords)

    def _post_process_grammar_response(self, response: str) -> str:
        """
        Пост-обробка граматичної відповіді для забезпечення лаконічності

        Args:
            response: Оригінальна відповідь

        Returns:
            Оброблена відповідь
        """
        max_length = self.config.get("response_formatting", {}).get("max_response_length", 300)

        # Якщо відповідь коротша за ліміт, повертаємо як є
        if len(response) <= max_length:
            return response

        # Обрізаємо до максимальної довжини, зберігаючи структуру
        lines = response.split('\n')
        result_lines = []
        current_length = 0

        for line in lines:
            if current_length + len(line) > max_length:
                break
            result_lines.append(line)
            current_length += len(line) + 1

        result = '\n'.join(result_lines)

        # Додаємо крапку в кінці якщо потрібно
        if result and not result.rstrip().endswith(('.', '!', '?')):
            result = result.rstrip() + '.'

        return result

    def _update_avg_response_length(self, response: str):
        """Оновлює середню довжину відповідей"""
        current_avg = self.usage_stats["avg_response_length"]
        total_requests = (self.usage_stats["translations"] +
                         self.usage_stats["grammar_explanations"] +
                         self.usage_stats["custom_requests"])

        if total_requests > 0:
            self.usage_stats["avg_response_length"] = (
                (current_avg * (total_requests - 1) + len(response)) / total_requests
            )

    def custom_request(self, text: str, prompt: str) -> Dict:
        """
        Обробляє кастомний запит користувача з врахуванням Skyrim контексту

        Args:
            text: Контекст - англійське речення
            prompt: Запит користувача

        Returns:
            {"success": bool, "result": str, "error": str, "cached": bool}
        """
        if not self.is_available():
            return {
                "success": False,
                "result": "",
                "error": "AI недоступний. Перевірте чи запущений Ollama",
                "cached": False
            }

        try:
            self.logger.debug(f"Кастомний запит: {prompt[:50]}...")

            result = self.ollama_client.custom_request(text, prompt)

            if result["success"]:
                self.usage_stats["custom_requests"] += 1
                self.usage_stats["last_request"] = datetime.now().isoformat()
                self._update_avg_response_length(result["text"])

                return {
                    "success": True,
                    "result": result["text"],
                    "error": None,
                    "cached": False
                }
            else:
                self.usage_stats["errors"] += 1
                return {
                    "success": False,
                    "result": "",
                    "error": result["error"],
                    "cached": False
                }

        except Exception as e:
            self.usage_stats["errors"] += 1
            error_msg = f"Помилка кастомного запиту: {str(e)}"
            self.logger.error(error_msg)

            return {
                "success": False,
                "result": "",
                "error": error_msg,
                "cached": False
            }

    def test_ai(self) -> Dict:
        """
        Тестує роботу AI з Skyrim фразою

        Returns:
            Результат тестування
        """
        if not self.ollama_client:
            return {
                "success": False,
                "message": "Ollama клієнт не ініціалізований"
            }

        return self.ollama_client.test_connection()

    def get_skyrim_analysis_stats(self) -> Dict:
        """
        НОВИЙ: Отримує статистику аналізів Skyrim

        Returns:
            Статистика Skyrim аналізів
        """
        total_analyses = self.usage_stats["grammar_explanations"]
        skyrim_analyses = self.usage_stats["skyrim_analyses"]

        return {
            "total_grammar_analyses": total_analyses,
            "skyrim_specific_analyses": skyrim_analyses,
            "skyrim_percentage": round((skyrim_analyses / total_analyses * 100), 1) if total_analyses > 0 else 0,
            "avg_response_length": round(self.usage_stats["avg_response_length"], 1),
            "is_optimized_for_skyrim": self.config.get("skyrim_context", {}).get("enable_fantasy_terms", False)
        }

    def update_config(self, new_config: Dict):
        """
        Оновлює конфігурацію AI

        Args:
            new_config: Нова конфігурація
        """
        try:
            self.config.update(new_config)
            self._save_config(self.config)

            # Переініціалізуємо Ollama якщо потрібно
            if "ollama" in new_config:
                self._initialize_ollama()

            self.logger.info("Конфігурація AI оновлена")

        except Exception as e:
            self.logger.error(f"Помилка оновлення конфігурації: {e}")

    def get_config(self) -> Dict:
        """Повертає поточну конфігурацію"""
        return self.config.copy()

    def reset_usage_stats(self):
        """Скидає статистику використання"""
        self.usage_stats = {
            "translations": 0,
            "grammar_explanations": 0,
            "skyrim_analyses": 0,
            "custom_requests": 0,
            "errors": 0,
            "avg_response_length": 0.0,
            "last_request": None
        }
        self.logger.info("Статистика використання скинута")

    def optimize_for_skyrim(self):
        """
        НОВИЙ: Оптимізує налаштування спеціально для Skyrim
        """
        skyrim_optimization = {
            "ollama": {
                "temperature": 0.15,  # Ще менше креативності для стабільності
                "timeout": 25  # Швидші відповіді
            },
            "skyrim_context": {
                "enable_fantasy_terms": True,
                "enable_nordic_context": True,
                "max_response_length": 250,  # Коротші відповіді
                "preferred_format": "ultra_concise"
            },
            "response_formatting": {
                "include_translation": True,
                "include_emojis": True,
                "max_grammar_explanation": 80,  # Ще коротші пояснення
                "auto_trim": True
            }
        }

        self.update_config(skyrim_optimization)
        self.logger.info("🐉 AI оптимізовано для The Elder Scrolls V: Skyrim")


# Приклад використання з Skyrim контекстом
if __name__ == "__main__":
    # Налаштування логування
    logging.basicConfig(level=logging.DEBUG)

    # Створення AI менеджера
    ai_manager = AIManager()

    # Оптимізація для Skyrim
    ai_manager.optimize_for_skyrim()

    # Перевірка статусу
    print("=== Статус AI з Skyrim контекстом ===")
    status = ai_manager.get_status()
    print(json.dumps(status, indent=2, ensure_ascii=False))

    if ai_manager.is_available():
        # Тест з відомими Skyrim фразами
        skyrim_test_phrases = [
            "You're finally awake!",
            "I used to be an adventurer like you, then I took an arrow to the knee.",
            "Damn you Stormcloaks. Skyrim was fine until you came along.",
            "Hey, you. You're finally awake.",
            "Fus Ro Dah!"
        ]

        print("\n=== Тест лаконічних граматичних пояснень ===")
        for phrase in skyrim_test_phrases:
            print(f"\n🎮 Фраза: {phrase}")
            grammar = ai_manager.explain_grammar(phrase)

            if grammar["success"]:
                print(f"✅ Відповідь ({len(grammar['result'])} символів):")
                print(f"{grammar['result']}")
                print(f"🎯 Skyrim контекст: {'Так' if grammar['is_skyrim'] else 'Ні'}")
            else:
                print(f"❌ Помилка: {grammar['error']}")

        # Статистика Skyrim аналізів
        print("\n=== Статистика Skyrim аналізів ===")
        skyrim_stats = ai_manager.get_skyrim_analysis_stats()
        print(json.dumps(skyrim_stats, indent=2, ensure_ascii=False))

    else:
        print("❌ AI недоступний. Перевірте чи запущений Ollama")