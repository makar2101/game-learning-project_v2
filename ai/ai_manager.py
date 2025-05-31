"""
AI Manager - головний менеджер для роботи з AI
Керує Ollama клієнтом та налаштуваннями AI
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

from ai.ollama_client import OllamaClient

class AIManager:
    """Головний менеджер AI сервісів"""
    
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
        
        # Статистика використання
        self.usage_stats = {
            "translations": 0,
            "grammar_explanations": 0,
            "custom_requests": 0,
            "errors": 0,
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
                # Створюємо конфігурацію за замовчуванням
                default_config = self._create_default_config()
                self._save_config(default_config)
                return default_config
                
        except Exception as e:
            self.logger.error(f"Помилка завантаження конфігурації: {e}")
            return self._create_default_config()
    
    def _create_default_config(self) -> Dict:
        """Створює конфігурацію за замовчуванням"""
        return {
            "ollama": {
                "enabled": True,
                "model": "llama3.1:8b",
                "base_url": "http://localhost:11434",
                "timeout": 60,
                "max_retries": 3,
                "temperature": 0.3
            },
            "auto_check_updates": True,
            "preferred_language": "uk",
            "cache_responses": True,
            "version": "1.0"
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
        Отримує статус AI менеджера
        
        Returns:
            Словник зі статусом
        """
        return {
            "available": self.is_available(),
            "model": self.config["ollama"]["model"],
            "client": "ollama" if self.ollama_client else None,
            "usage_stats": self.usage_stats.copy(),
            "last_check": datetime.now().isoformat()
        }
    
    def translate_text(self, text: str) -> Dict:
        """
        Перекладає текст українською
        
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
        Пояснює граматику речення
        
        Args:
            text: Англійське речення
            
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
            self.logger.debug(f"Граматичний аналіз: {text[:50]}...")
            
            result = self.ollama_client.explain_grammar(text)
            
            if result["success"]:
                self.usage_stats["grammar_explanations"] += 1
                self.usage_stats["last_request"] = datetime.now().isoformat()
                
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
            error_msg = f"Помилка граматичного аналізу: {str(e)}"
            self.logger.error(error_msg)
            
            return {
                "success": False,
                "result": "",
                "error": error_msg,
                "cached": False
            }
    
    def custom_request(self, text: str, prompt: str) -> Dict:
        """
        Обробляє кастомний запит
        
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
        Тестує роботу AI
        
        Returns:
            Результат тестування
        """
        if not self.ollama_client:
            return {
                "success": False,
                "message": "Ollama клієнт не ініціалізований"
            }
        
        return self.ollama_client.test_connection()
    
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
            "custom_requests": 0,
            "errors": 0,
            "last_request": None
        }
        self.logger.info("Статистика використання скинута")

# Приклад використання
if __name__ == "__main__":
    # Налаштування логування
    logging.basicConfig(level=logging.DEBUG)
    
    # Створення AI менеджера
    ai_manager = AIManager()
    
    # Перевірка статусу
    print("=== Статус AI ===")
    status = ai_manager.get_status()
    print(json.dumps(status, indent=2, ensure_ascii=False))
    
    if ai_manager.is_available():
        # Тест перекладу
        print("\n=== Тест перекладу ===")
        translation = ai_manager.translate_text("Hello, I love playing games")
        print(f"Результат: {translation}")
        
        # Тест граматики
        print("\n=== Тест граматики ===")
        grammar = ai_manager.explain_grammar("I will be studying English")
        print(f"Результат: {grammar}")
        
        # Тест кастомного запиту
        print("\n=== Тест кастомного запиту ===")
        custom = ai_manager.custom_request("Hello world", "Поясни слово 'world'")
        print(f"Результат: {custom}")
        
        # Фінальний статус
        print("\n=== Фінальний статус ===")
        final_status = ai_manager.get_status()
        print(json.dumps(final_status, indent=2, ensure_ascii=False))
    
    else:
        print("❌ AI недоступний. Перевірте чи запущений Ollama")