"""
Enhanced AI Manager - покращений менеджер AI з фокусом на вивчення мови
Додає детальні граматичні пояснення, контекстуальний аналіз та адаптивні поради
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime

from ai.ollama_client import OllamaClient


class LanguageLearningAI:
    """Спеціалізований AI для вивчення англійської мови"""

    def __init__(self, ollama_client: OllamaClient):
        self.ollama_client = ollama_client
        self.logger = logging.getLogger(__name__)

        # Шаблони для різних типів аналізу
        self.analysis_prompts = {
            "comprehensive_analysis": """Проаналізуй це англійське речення для українського студента, який вивчає мову:

РЕЧЕННЯ: "{text}"
КОНТЕКСТ: {context}

Дай детальний аналіз українською мовою, включаючи:

1. ПЕРЕКЛАД:
- Точний переклад
- Альтернативні варіанти перекладу
- Культурні особливості (якщо є)

2. ГРАМАТИЧНИЙ АНАЛІЗ:
- Час дієслова та його особливості
- Структура речення
- Складні граматичні конструкції
- Порядок слів та його значення

3. ЛЕКСИЧНИЙ АНАЛІЗ:
- Ключові слова та їх значення
- Ідіоми, фразові дієслова
- Синоніми та антоніми
- Рівень складності слів

4. ФОНЕТИЧНІ ОСОБЛИВОСТІ:
- Складні для вимови звуки
- Наголос у словах
- Інтонація речення

5. ПОРАДИ ДЛЯ ЗАПАМ'ЯТОВУВАННЯ:
- Мнемонічні прийоми
- Асоціації з українською мовою
- Практичні вправи
- Схожі конструкції

6. РІВЕНЬ СКЛАДНОСТІ: {difficulty_level}

Відповідай структуровано та детально, фокусуючись на практичному застосуванні для вивчення мови.""",

            "contextual_explanation": """Поясни це англійське речення в контексті відео/розмови:

РЕЧЕННЯ: "{text}"
ПОПЕРЕДНЄ РЕЧЕННЯ: "{previous_text}"
НАСТУПНЕ РЕЧЕННЯ: "{next_text}"
ВІДЕО КОНТЕКСТ: {video_context}

Поясни українською:

1. ЗНАЧЕННЯ В КОНТЕКСТІ:
- Як це речення пов'язане з попереднім та наступним
- Роль у загальному діалозі/нарації
- Емоційне забарвлення

2. ДИСКУРСИВНІ МАРКЕРИ:
- Слова-зв'язки та їх функція
- Логічні переходи між ідеями

3. СТИЛІСТИЧНІ ОСОБЛИВОСТІ:
- Формальний/неформальний стиль
- Розмовні вирази
- Специфічна лексика (сленг, термінологія)

4. КОМУНІКАТИВНА ФУНКЦІЯ:
- Мета висловлювання (запитання, твердження, прохання)
- Імпліцитні значення

Фокусуйся на розумінні природної англійської мови та розвитку комунікативних навичок.""",

            "error_correction": """Проаналізуй потенційні помилки, які може зробити український студент з цим реченням:

РЕЧЕННЯ: "{text}"

Поясни українською:

1. ТИПОВІ ПОМИЛКИ:
- Граматичні помилки через вплив української мови
- Неправильний порядок слів
- Помилки у виборі часів дієслова
- Лексичні помилки (false friends)

2. ПРАВИЛЬНЕ ВИКОРИСТАННЯ:
- Покрокове пояснення граматики
- Чому саме так, а не інакше
- Винятки з правил

3. СХОЖІ КОНСТРУКЦІЇ:
- Інші приклади з такою ж граматикою
- Варіації цього речення
- Як змінювати для різних ситуацій

4. ПРАКТИЧНІ ВПРАВИ:
- Заповни пропуски
- Перефразування
- Переклад з української

Допоможи уникнути типових помилок та закріпити правильне розуміння.""",

            "vocabulary_builder": """Розбери лексику цього речення для розширення словникового запасу:

РЕЧЕННЯ: "{text}"

Дай детальний аналіз українською:

1. КЛЮЧОВІ СЛОВА:
- Основне значення кожного важливого слова
- Етимологія (походження слова)
- Частота використання в англійській мові

2. СЛОВОТВІР:
- Префікси та суфікси
- Спорідненні слова (word families)
- Як утворювати нові форми

3. КОЛОКАЦІЇ:
- З якими словами часто вживається
- Стійкі словосполучення
- Природні комбінації слів

4. СИНОНІМИ ТА АНТОНІМИ:
- Близькі за значенням слова
- Різниця у відтінках значення
- Протилежні поняття

5. ПРАКТИЧНЕ ВИКОРИСТАННЯ:
- Приклади в різних контекстах
- Формальне vs неформальне вживання
- Регіональні варіанти (британський/американський)

6. ЗАПАМ'ЯТОВУВАННЯ:
- Візуальні асоціації
- Звукові асоціації
- Контекстуальні зв'язки

Допоможи ефективно розширити активний словниковий запас.""",

            "pronunciation_guide": """Дай детальну фонетичну інструкцію для цього речення:

РЕЧЕННЯ: "{text}"

Поясни українською:

1. ФОНЕТИЧНА ТРАНСКРИПЦІЯ:
- IPA транскрипція для кожного слова
- Спрощена транскрипція українськими літерами
- Наголос у кожному слові

2. СКЛАДНІ ЗВУКИ:
- Звуки, яких немає в українській мові
- Як правильно їх вимовляти
- Типові помилки українців

3. ІНТОНАЦІЯ:
- Мелодика речення
- Логічний наголос
- Емоційне забарвлення

4. РИТМ ТА ТЕМП:
- Як поділити на ритмічні групи
- Де робити паузи
- Швидкість вимови

5. ПРАКТИЧНІ ПОРАДИ:
- Вправи для розробки артикуляції
- Як тренувати складні звуки
- Техніки імітації носіїв мови

Допоможи досягти чистої та природної вимови."""
        }

    def get_comprehensive_analysis(self, text: str, context: Dict = None) -> Dict:
        """Отримує всебічний аналіз речення для вивчення мови"""
        try:
            # Підготовка контексту
            context_info = self._prepare_context(context or {})
            difficulty = self._estimate_difficulty(text)

            prompt = self.analysis_prompts["comprehensive_analysis"].format(
                text=text,
                context=context_info,
                difficulty_level=difficulty
            )

            result = self.ollama_client._make_request(prompt)

            if result["success"]:
                # Парсимо структуровану відповідь
                parsed_response = self._parse_comprehensive_response(result["text"])

                return {
                    "success": True,
                    "analysis": parsed_response,
                    "difficulty_level": difficulty,
                    "analysis_type": "comprehensive",
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "success": False,
                    "error": result["error"],
                    "analysis_type": "comprehensive"
                }

        except Exception as e:
            self.logger.error(f"Помилка всебічного аналізу: {e}")
            return {
                "success": False,
                "error": str(e),
                "analysis_type": "comprehensive"
            }

    def get_contextual_explanation(self, text: str, context: Dict) -> Dict:
        """Отримує контекстуальне пояснення речення"""
        try:
            context_info = {
                "previous_text": context.get("previous_sentence", ""),
                "next_text": context.get("next_sentence", ""),
                "video_context": context.get("video_description", "відео контент")
            }

            prompt = self.analysis_prompts["contextual_explanation"].format(
                text=text,
                **context_info
            )

            result = self.ollama_client._make_request(prompt)

            return {
                "success": result["success"],
                "explanation": result.get("text", ""),
                "error": result.get("error"),
                "analysis_type": "contextual"
            }

        except Exception as e:
            self.logger.error(f"Помилка контекстуального пояснення: {e}")
            return {
                "success": False,
                "error": str(e),
                "analysis_type": "contextual"
            }

    def get_error_correction_guide(self, text: str) -> Dict:
        """Отримує інструкцію з уникнення помилок"""
        try:
            prompt = self.analysis_prompts["error_correction"].format(text=text)
            result = self.ollama_client._make_request(prompt)

            return {
                "success": result["success"],
                "guide": result.get("text", ""),
                "error": result.get("error"),
                "analysis_type": "error_correction"
            }

        except Exception as e:
            self.logger.error(f"Помилка інструкції з корекції: {e}")
            return {
                "success": False,
                "error": str(e),
                "analysis_type": "error_correction"
            }

    def get_vocabulary_analysis(self, text: str) -> Dict:
        """Отримує детальний аналіз лексики"""
        try:
            prompt = self.analysis_prompts["vocabulary_builder"].format(text=text)
            result = self.ollama_client._make_request(prompt)

            # Додаткова обробка для виділення ключових слів
            key_words = self._extract_key_words(text)

            return {
                "success": result["success"],
                "vocabulary_analysis": result.get("text", ""),
                "key_words": key_words,
                "error": result.get("error"),
                "analysis_type": "vocabulary"
            }

        except Exception as e:
            self.logger.error(f"Помилка аналізу лексики: {e}")
            return {
                "success": False,
                "error": str(e),
                "analysis_type": "vocabulary"
            }

    def get_pronunciation_guide(self, text: str) -> Dict:
        """Отримує детальну інструкцію з вимови"""
        try:
            prompt = self.analysis_prompts["pronunciation_guide"].format(text=text)
            result = self.ollama_client._make_request(prompt)

            # Додаємо базову фонетичну інформацію
            phonetic_info = self._get_basic_phonetics(text)

            return {
                "success": result["success"],
                "pronunciation_guide": result.get("text", ""),
                "phonetic_info": phonetic_info,
                "error": result.get("error"),
                "analysis_type": "pronunciation"
            }

        except Exception as e:
            self.logger.error(f"Помилка інструкції з вимови: {e}")
            return {
                "success": False,
                "error": str(e),
                "analysis_type": "pronunciation"
            }

    def _prepare_context(self, context: Dict) -> str:
        """Підготовує контекстну інформацію"""
        context_parts = []

        if context.get("video_title"):
            context_parts.append(f"Відео: {context['video_title']}")

        if context.get("scene_description"):
            context_parts.append(f"Сцена: {context['scene_description']}")

        if context.get("speaker_info"):
            context_parts.append(f"Мовець: {context['speaker_info']}")

        if context.get("difficulty_level"):
            context_parts.append(f"Рівень: {context['difficulty_level']}")

        return "; ".join(context_parts) if context_parts else "загальний контекст"

    def _estimate_difficulty(self, text: str) -> str:
        """Оцінює складність тексту"""
        # Простий алгоритм оцінки складності
        words = text.split()

        # Фактори складності
        long_words = len([w for w in words if len(w) > 8])
        complex_punctuation = len(re.findall(r'[;:()"]', text))
        avg_word_length = sum(len(w) for w in words) / len(words) if words else 0

        # Розрахунок балу складності
        difficulty_score = (
            long_words * 2 +
            complex_punctuation * 1.5 +
            (avg_word_length - 4) * 2 if avg_word_length > 4 else 0
        )

        if difficulty_score < 3:
            return "Beginner (Початковий)"
        elif difficulty_score < 8:
            return "Intermediate (Середній)"
        else:
            return "Advanced (Просунутий)"

    def _parse_comprehensive_response(self, response: str) -> Dict:
        """Парсить структуровану відповідь всебічного аналізу"""
        # Спрощений парсер - в реальності можна зробити більш складний
        sections = {
            "translation": "",
            "grammar": "",
            "vocabulary": "",
            "phonetics": "",
            "memorization_tips": "",
            "full_text": response
        }

        # Пошук секцій в тексті
        section_patterns = {
            "translation": r"1\.\s*ПЕРЕКЛАД:(.*?)(?=2\.|$)",
            "grammar": r"2\.\s*ГРАМАТИЧНИЙ АНАЛІЗ:(.*?)(?=3\.|$)",
            "vocabulary": r"3\.\s*ЛЕКСИЧНИЙ АНАЛІЗ:(.*?)(?=4\.|$)",
            "phonetics": r"4\.\s*ФОНЕТИЧНІ ОСОБЛИВОСТІ:(.*?)(?=5\.|$)",
            "memorization_tips": r"5\.\s*ПОРАДИ ДЛЯ ЗАПАМ'ЯТОВУВАННЯ:(.*?)(?=6\.|$)"
        }

        for section, pattern in section_patterns.items():
            match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
            if match:
                sections[section] = match.group(1).strip()

        return sections

    def _extract_key_words(self, text: str) -> List[Dict]:
        """Виділяє ключові слова з тексту"""
        # Спрощений екстрактор ключових слів
        words = re.findall(r'\b[a-zA-Z]+\b', text.lower())

        # Фільтруємо сервісні слова
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at',
                      'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were'}

        key_words = []
        for word in words:
            if word not in stop_words and len(word) > 3:
                key_words.append({
                    'word': word,
                    'length': len(word),
                    'complexity': 'high' if len(word) > 7 else 'medium' if len(word) > 5 else 'low'
                })

        return key_words[:10]  # Повертаємо топ-10

    def _get_basic_phonetics(self, text: str) -> Dict:
        """Отримує базову фонетичну інформацію"""
        # Спрощена фонетична інформація
        difficult_sounds = []
        words = text.split()

        # Пошук складних звуків для українців
        sound_patterns = {
            'th': r'\bth\w*',
            'w': r'\bw\w*',
            'r': r'\w*r\w*',
            'ng': r'\w*ng\b'
        }

        for sound, pattern in sound_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                difficult_sounds.append(sound)

        return {
            'difficult_sounds': difficult_sounds,
            'word_count': len(words),
            'estimated_duration': len(words) * 0.6  # Приблизно 0.6 сек на слово
        }


class EnhancedAIManager:
    """Покращений AI менеджер з фокусом на вивчення мови"""

    def __init__(self, config_file: str = "config/ai_config.json"):
        """Ініціалізація покращеного AI менеджера"""
        self.config_file = Path(config_file)
        self.logger = logging.getLogger(__name__)

        # Завантажуємо конфігурацію
        self.config = self._load_config()

        # Ініціалізуємо клієнтів
        self.ollama_client = None
        self.language_ai = None
        self._initialize_clients()

        # Розширена статистика
        self.usage_stats = {
            "comprehensive_analyses": 0,
            "contextual_explanations": 0,
            "error_corrections": 0,
            "vocabulary_analyses": 0,
            "pronunciation_guides": 0,
            "total_requests": 0,
            "errors": 0,
            "last_request": None,
            "average_response_time": 0.0
        }

    def _load_config(self) -> Dict:
        """Завантажує розширену конфігурацію"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                return config
            else:
                default_config = self._create_enhanced_config()
                self._save_config(default_config)
                return default_config
        except Exception as e:
            self.logger.error(f"Помилка завантаження конфігурації: {e}")
            return self._create_enhanced_config()

    def _create_enhanced_config(self) -> Dict:
        """Створює розширену конфігурацію"""
        return {
            "ollama": {
                "enabled": True,
                "model": "llama3.1:8b",
                "base_url": "http://localhost:11434",
                "timeout": 90,
                "max_retries": 3,
                "temperature": 0.2  # Нижча температура для більш точних відповідей
            },
            "language_learning": {
                "user_level": "intermediate",
                "native_language": "ukrainian",
                "target_language": "english",
                "focus_areas": ["grammar", "vocabulary", "pronunciation", "context"],
                "explanation_style": "detailed",
                "include_examples": True,
                "cultural_context": True
            },
            "analysis_settings": {
                "comprehensive_analysis": True,
                "contextual_explanation": True,
                "error_correction": True,
                "vocabulary_building": True,
                "pronunciation_guide": True,
                "adaptive_difficulty": True
            },
            "cache_settings": {
                "cache_responses": True,
                "cache_duration_hours": 24,
                "max_cache_size_mb": 100
            },
            "version": "2.0"
        }

    def _save_config(self, config: Dict):
        """Зберігає конфігурацію"""
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Помилка збереження конфігурації: {e}")

    def _initialize_clients(self):
        """Ініціалізує AI клієнтів"""
        try:
            if self.config["ollama"]["enabled"]:
                self.ollama_client = OllamaClient(
                    model=self.config["ollama"]["model"],
                    base_url=self.config["ollama"]["base_url"]
                )

                if self.ollama_client.is_available():
                    self.language_ai = LanguageLearningAI(self.ollama_client)
                    self.logger.info("Покращений AI клієнт ініціалізований")
                else:
                    self.logger.warning("Ollama недоступний")

        except Exception as e:
            self.logger.error(f"Помилка ініціалізації AI клієнтів: {e}")

    def is_available(self) -> bool:
        """Перевіряє доступність AI"""
        return self.language_ai is not None and self.ollama_client.is_available()

    def analyze_sentence_comprehensive(self, text: str, context: Dict = None) -> Dict:
        """Всебічний аналіз речення для вивчення мови"""
        if not self.is_available():
            return self._unavailable_response("comprehensive_analysis")

        try:
            import time
            start_time = time.time()

            result = self.language_ai.get_comprehensive_analysis(text, context)

            response_time = time.time() - start_time
            self._update_stats("comprehensive_analyses", response_time, result["success"])

            return result

        except Exception as e:
            self._update_stats("comprehensive_analyses", 0, False)
            return {
                "success": False,
                "error": str(e),
                "analysis_type": "comprehensive"
            }

    def explain_in_context(self, text: str, context: Dict) -> Dict:
        """Контекстуальне пояснення речення"""
        if not self.is_available():
            return self._unavailable_response("contextual_explanation")

        try:
            import time
            start_time = time.time()

            result = self.language_ai.get_contextual_explanation(text, context)

            response_time = time.time() - start_time
            self._update_stats("contextual_explanations", response_time, result["success"])

            return result

        except Exception as e:
            self._update_stats("contextual_explanations", 0, False)
            return {
                "success": False,
                "error": str(e),
                "analysis_type": "contextual"
            }

    def get_error_correction_guide(self, text: str) -> Dict:
        """Інструкція з уникнення помилок"""
        if not self.is_available():
            return self._unavailable_response("error_correction")

        try:
            import time
            start_time = time.time()

            result = self.language_ai.get_error_correction_guide(text)

            response_time = time.time() - start_time
            self._update_stats("error_corrections", response_time, result["success"])

            return result

        except Exception as e:
            self._update_stats("error_corrections", 0, False)
            return {
                "success": False,
                "error": str(e),
                "analysis_type": "error_correction"
            }

    def analyze_vocabulary(self, text: str) -> Dict:
        """Детальний аналіз лексики"""
        if not self.is_available():
            return self._unavailable_response("vocabulary_analysis")

        try:
            import time
            start_time = time.time()

            result = self.language_ai.get_vocabulary_analysis(text)

            response_time = time.time() - start_time
            self._update_stats("vocabulary_analyses", response_time, result["success"])

            return result

        except Exception as e:
            self._update_stats("vocabulary_analyses", 0, False)
            return {
                "success": False,
                "error": str(e),
                "analysis_type": "vocabulary"
            }

    def get_pronunciation_guide(self, text: str) -> Dict:
        """Детальна інструкція з вимови"""
        if not self.is_available():
            return self._unavailable_response("pronunciation_guide")

        try:
            import time
            start_time = time.time()

            result = self.language_ai.get_pronunciation_guide(text)

            response_time = time.time() - start_time
            self._update_stats("pronunciation_guides", response_time, result["success"])

            return result

        except Exception as e:
            self._update_stats("pronunciation_guides", 0, False)
            return {
                "success": False,
                "error": str(e),
                "analysis_type": "pronunciation"
            }

    def _unavailable_response(self, analysis_type: str) -> Dict:
        """Стандартна відповідь при недоступності AI"""
        return {
            "success": False,
            "error": "AI недоступний. Перевірте чи запущений Ollama",
            "analysis_type": analysis_type
        }

    def _update_stats(self, operation: str, response_time: float, success: bool):
        """Оновлює статистику використання"""
        self.usage_stats[operation] += 1
        self.usage_stats["total_requests"] += 1

        if not success:
            self.usage_stats["errors"] += 1

        # Оновлюємо середній час відповіді
        current_avg = self.usage_stats["average_response_time"]
        total_requests = self.usage_stats["total_requests"]
        self.usage_stats["average_response_time"] = (
                (current_avg * (total_requests - 1) + response_time) / total_requests
        )

        self.usage_stats["last_request"] = datetime.now().isoformat()

    def get_enhanced_status(self) -> Dict:
        """Отримує розширений статус AI менеджера"""
        base_status = {
            "available": self.is_available(),
            "model": self.config["ollama"]["model"],
            "language_learning_enabled": self.language_ai is not None,
            "user_level": self.config["language_learning"]["user_level"],
            "target_language": self.config["language_learning"]["target_language"],
            "usage_stats": self.usage_stats.copy(),
            "last_check": datetime.now().isoformat()
        }

        if self.is_available():
            base_status["features"] = {
                "comprehensive_analysis": True,
                "contextual_explanation": True,
                "error_correction": True,
                "vocabulary_analysis": True,
                "pronunciation_guide": True
            }

        return base_status

    def update_user_level(self, new_level: str):
        """Оновлює рівень користувача"""
        if new_level in ["beginner", "intermediate", "advanced"]:
            self.config["language_learning"]["user_level"] = new_level
            self._save_config(self.config)
            self.logger.info(f"Рівень користувача оновлено до: {new_level}")

    def get_learning_recommendations(self) -> Dict:
        """Отримує рекомендації для вивчення на основі статистики"""
        stats = self.usage_stats

        recommendations = []

        # Аналіз використання різних типів аналізу
        if stats["vocabulary_analyses"] < stats["comprehensive_analyses"] * 0.3:
            recommendations.append({
                "type": "vocabulary",
                "message": "Рекомендуємо більше працювати зі словниковими аналізами для розширення лексики",
                "priority": "medium"
            })

        if stats["pronunciation_guides"] < stats["total_requests"] * 0.1:
            recommendations.append({
                "type": "pronunciation",
                "message": "Додайте роботу з вимовою для покращення фонетичних навичок",
                "priority": "high"
            })

        if stats["contextual_explanations"] < stats["comprehensive_analyses"]:
            recommendations.append({
                "type": "context",
                "message": "Вивчайте контекстуальні пояснення для кращого розуміння живої мови",
                "priority": "medium"
            })

        # Рекомендації на основі рівня
        user_level = self.config["language_learning"]["user_level"]

        if user_level == "beginner":
            recommendations.append({
                "type": "focus",
                "message": "Зосередьтесь на базовій граматиці та найбільш вживаних словах",
                "priority": "high"
            })
        elif user_level == "intermediate":
            recommendations.append({
                "type": "focus",
                "message": "Розвивайте розуміння контексту та вивчайте ідіоматичні вирази",
                "priority": "medium"
            })
        else:  # advanced
            recommendations.append({
                "type": "focus",
                "message": "Працюйте над стилістичними нюансами та культурним контекстом",
                "priority": "low"
            })

        return {
            "recommendations": recommendations,
            "user_level": user_level,
            "total_requests": stats["total_requests"],
            "success_rate": (stats["total_requests"] - stats["errors"]) / max(stats["total_requests"], 1) * 100
        }


# Приклад використання
if __name__ == "__main__":
    # Налаштування логування
    logging.basicConfig(level=logging.INFO)

    # Створення покращеного AI менеджера
    ai_manager = EnhancedAIManager()

    print("=== Тест покращеного AI менеджера ===")

    # Перевірка статусу
    status = ai_manager.get_enhanced_status()
    print(f"Статус: {status}")

    if ai_manager.is_available():
        # Тест всебічного аналізу
        test_sentence = "I've been studying English for three years, but I still struggle with pronunciation."

        print(f"\n=== Всебічний аналіз ===")
        print(f"Речення: {test_sentence}")

        comprehensive = ai_manager.analyze_sentence_comprehensive(
            test_sentence,
            context={
                "video_title": "English Learning Journey",
                "difficulty_level": "intermediate"
            }
        )
        print(f"Результат: {comprehensive.get('success', False)}")

        # Тест контекстуального пояснення
        print(f"\n=== Контекстуальне пояснення ===")
        contextual = ai_manager.explain_in_context(
            test_sentence,
            context={
                "previous_sentence": "Learning languages is challenging.",
                "next_sentence": "But I'm not giving up!",
                "video_description": "Student talking about language learning"
            }
        )
        print(f"Результат: {contextual.get('success', False)}")

        # Тест аналізу лексики
        print(f"\n=== Аналіз лексики ===")
        vocabulary = ai_manager.analyze_vocabulary(test_sentence)
        print(f"Результат: {vocabulary.get('success', False)}")
        if vocabulary.get('success'):
            print(f"Ключові слова: {len(vocabulary.get('key_words', []))}")

        # Тест інструкції з вимови
        print(f"\n=== Інструкція з вимови ===")
        pronunciation = ai_manager.get_pronunciation_guide(test_sentence)
        print(f"Результат: {pronunciation.get('success', False)}")

        # Рекомендації
        print(f"\n=== Рекомендації для вивчення ===")
        recommendations = ai_manager.get_learning_recommendations()
        print(f"Кількість рекомендацій: {len(recommendations['recommendations'])}")

        # Фінальна статистика
        print(f"\n=== Статистика використання ===")
        final_status = ai_manager.get_enhanced_status()
        usage = final_status['usage_stats']
        print(f"Всього запитів: {usage['total_requests']}")
        print(f"Успішних: {usage['total_requests'] - usage['errors']}")
        print(f"Середній час відповіді: {usage['average_response_time']:.2f}с")

    else:
        print("❌ AI недоступний. Перевірте чи запущений Ollama")