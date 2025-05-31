#!/usr/bin/env python3
"""
Game Learning v2.0 - Головний файл програми
Програма для вивчення англійської мови через ігрові відео з AI підтримкою

Автор: Ваш проєкт
Версія: 2.0
Python: 3.11+
"""

import sys
import os
import logging
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

# Додаємо поточну папку до шляху Python
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

def setup_logging():
    """Налаштовує систему логування"""
    
    # Створюємо папку для логів
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Налаштування логування
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            # Запис у файл
            logging.FileHandler(logs_dir / "game_learning.log", encoding='utf-8'),
            # Вивід в консоль
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Налаштування рівнів для різних модулів
    logging.getLogger('PIL').setLevel(logging.WARNING)  # Pillow менше логів
    logging.getLogger('urllib3').setLevel(logging.WARNING)  # Requests менше логів
    
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("Game Learning v2.0 - Запуск програми")
    logger.info("=" * 60)
    
    return logger

def check_dependencies():
    """Перевіряє наявність необхідних залежностей"""
    
    logger = logging.getLogger(__name__)
    missing_deps = []
    
    # Критичні залежності
    critical_deps = {
        'tkinter': 'GUI фреймворк',
        'PIL': 'Pillow - робота з зображеннями', 
        'sqlite3': 'База даних SQLite',
        'json': 'JSON обробка',
        'pathlib': 'Робота з файлами'
    }
    
    # AI та відео залежності
    optional_deps = {
        'torch': 'PyTorch для Whisper AI',
        'whisper': 'OpenAI Whisper для транскрипції',
        'cv2': 'OpenCV для відео',
        'requests': 'HTTP запити для AI',
        'numpy': 'Числові обчислення',
        'pandas': 'Обробка даних'
    }
    
    # Перевіряємо критичні
    for module, description in critical_deps.items():
        try:
            __import__(module)
            logger.debug(f"✅ {module} - {description}")
        except ImportError:
            missing_deps.append(f"❌ {module} - {description}")
            logger.error(f"Відсутня критична залежність: {module}")
    
    # Перевіряємо опціональні
    optional_missing = []
    for module, description in optional_deps.items():
        try:
            __import__(module)
            logger.debug(f"✅ {module} - {description}")
        except ImportError:
            optional_missing.append(f"⚠️ {module} - {description}")
            logger.warning(f"Відсутня опціональна залежність: {module}")
    
    return missing_deps, optional_missing

def check_external_tools():
    """Перевіряє наявність зовнішніх інструментів"""
    
    logger = logging.getLogger(__name__)
    tools_status = {}
    
    # FFmpeg для обробки відео
    try:
        import subprocess
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, timeout=5)
        if result.returncode == 0:
            tools_status['ffmpeg'] = "✅ Доступний"
            logger.info("FFmpeg знайдено")
        else:
            tools_status['ffmpeg'] = "❌ Помилка запуску"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        tools_status['ffmpeg'] = "❌ Не встановлений"
        logger.warning("FFmpeg не знайдено")
    except Exception as e:
        tools_status['ffmpeg'] = f"❌ Помилка: {e}"
    
    # Ollama для AI
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=3)
        if response.status_code == 200:
            models = response.json().get("models", [])
            llama_models = [m for m in models if "llama" in m.get("name", "").lower()]
            
            if llama_models:
                tools_status['ollama'] = f"✅ Доступний ({len(llama_models)} Llama моделей)"
                logger.info(f"Ollama знайдено з {len(llama_models)} Llama моделями")
            else:
                tools_status['ollama'] = "⚠️ Доступний (немає Llama моделей)"
                logger.warning("Ollama працює, але немає Llama моделей")
        else:
            tools_status['ollama'] = "❌ Сервер не відповідає"
    except requests.exceptions.ConnectionError:
        tools_status['ollama'] = "❌ Сервер не запущений"
        logger.warning("Ollama сервер не запущений")
    except Exception as e:
        tools_status['ollama'] = f"❌ Помилка: {e}"
    
    return tools_status

def check_directory_structure():
    """Перевіряє та створює необхідну структуру папок"""
    
    logger = logging.getLogger(__name__)
    
    # Необхідні папки
    required_dirs = [
        "videos",
        "processed/audio", 
        "processed/subtitles",
        "processed/frames",
        "processed/database",
        "models/whisper",
        "config",
        "logs",
        "temp"
    ]
    
    created_dirs = []
    
    for dir_path in required_dirs:
        path = Path(dir_path)
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            created_dirs.append(dir_path)
            logger.info(f"Створено папку: {dir_path}")
    
    if created_dirs:
        logger.info(f"Створено {len(created_dirs)} нових папок")
    else:
        logger.debug("Всі необхідні папки вже існують")
    
    return created_dirs

def show_startup_info(missing_deps, optional_missing, tools_status):
    """Показує інформацію про стан системи при запуску"""
    
    if missing_deps:
        # Критичні залежності відсутні
        error_msg = "Відсутні критичні компоненти:\n\n" + "\n".join(missing_deps)
        error_msg += "\n\nВстановіть їх командою:\npip install -r requirements.txt"
        
        messagebox.showerror("Критична помилка", error_msg)
        return False
    
    if optional_missing or any("❌" in status for status in tools_status.values()):
        # Показуємо попередження про відсутні компоненти
        
        warning_parts = []
        
        if optional_missing:
            warning_parts.append("Відсутні AI компоненти:")
            warning_parts.extend(optional_missing)
            warning_parts.append("")
        
        if tools_status['ffmpeg'].startswith("❌"):
            warning_parts.append("FFmpeg не встановлений:")
            warning_parts.append("• Встановіть: winget install Gyan.FFmpeg")
            warning_parts.append("• Без FFmpeg неможлива обробка відео")
            warning_parts.append("")
        
        if tools_status['ollama'].startswith("❌"):
            warning_parts.append("Ollama AI не доступний:")
            warning_parts.append("• Встановіть: winget install Ollama.Ollama")  
            warning_parts.append("• Завантажте модель: ollama pull llama3.1:8b")
            warning_parts.append("• Без Ollama неможливі AI переклади")
            warning_parts.append("")
        
        warning_parts.append("Продовжити запуск програми?")
        
        warning_msg = "\n".join(warning_parts)
        
        if not messagebox.askyesno("Попередження", warning_msg):
            return False
    
    return True

def create_initial_config():
    """Створює початкові конфігураційні файли"""
    
    logger = logging.getLogger(__name__)
    
    # AI конфігурація
    ai_config_path = Path("config/ai_config.json")
    if not ai_config_path.exists():
        ai_config = {
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
            "version": "2.0"
        }
        
        with open(ai_config_path, 'w', encoding='utf-8') as f:
            import json
            json.dump(ai_config, f, indent=2, ensure_ascii=False)
        
        logger.info("Створено конфігурацію AI")
    
    # UI конфігурація
    ui_config_path = Path("config/ui_config.json")
    if not ui_config_path.exists():
        ui_config = {
            "window": {
                "default_width": 1400,
                "default_height": 900,
                "min_width": 1000,
                "min_height": 700
            },
            "panels": {
                "sentences_width_ratio": 0.7,
                "notes_width_ratio": 0.3
            },
            "fonts": {
                "default_size": 11,
                "title_size": 14,
                "small_size": 9
            },
            "colors": {
                "default_bg": "#f8f9fa",
                "edited_bg": "#e8f5e8", 
                "loading_bg": "#fff3cd",
                "error_bg": "#f8d7da",
                "english_bg": "#f0f0f0"
            },
            "version": "2.0"
        }
        
        with open(ui_config_path, 'w', encoding='utf-8') as f:
            import json
            json.dump(ui_config, f, indent=2, ensure_ascii=False)
        
        logger.info("Створено конфігурацію UI")

def main():
    """Головна функція програми"""
    
    logger = None
    
    try:
        # Налаштування логування
        logger = setup_logging()
        
        logger.info("Початок ініціалізації системи...")
        
        # Перевірка структури папок
        created_dirs = check_directory_structure()
        
        # Створення конфігурацій
        create_initial_config()
        
        # Перевірка залежностей
        logger.info("Перевірка залежностей...")
        missing_deps, optional_missing = check_dependencies()
        
        # Перевірка зовнішніх інструментів
        logger.info("Перевірка зовнішніх інструментів...")
        tools_status = check_external_tools()
        
        # Показуємо статус
        logger.info("Статус системи:")
        logger.info(f"FFmpeg: {tools_status['ffmpeg']}")
        logger.info(f"Ollama: {tools_status['ollama']}")
        
        if optional_missing:
            logger.warning(f"Відсутні опціональні залежності: {len(optional_missing)}")
        
        # Перевіряємо чи можна запускати
        if not show_startup_info(missing_deps, optional_missing, tools_status):
            logger.info("Запуск скасований користувачем")
            return 1
        
        # Імпортуємо та запускаємо головне вікно
        logger.info("Запуск головного вікна...")
        
        try:
            from gui.main_window import MainWindow
            
            app = MainWindow()
            logger.info("Головне вікно створено успішно")
            
            # Запускаємо програму
            app.run()
            
            logger.info("Програма завершена нормально")
            return 0
            
        except ImportError as e:
            logger.error(f"Помилка імпорту головного вікна: {e}")
            messagebox.showerror("Помилка", 
                               f"Не вдалося завантажити головне вікно:\n{e}\n\nПеревірте чи всі файли на місці.")
            return 1
            
    except KeyboardInterrupt:
        if logger:
            logger.info("Програма зупинена користувачем (Ctrl+C)")
        return 0
        
    except Exception as e:
        error_msg = f"Критична помилка: {e}"
        error_details = traceback.format_exc()
        
        if logger:
            logger.error(error_msg)
            logger.error(f"Деталі помилки:\n{error_details}")
        else:
            print(error_msg)
            print(error_details)
        
        # Спробуємо показати повідомлення про помилку
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Критична помилка", 
                               f"{error_msg}\n\nДеталі збережені в логах.")
            root.destroy()
        except:
            print("Не вдалося показати повідомлення про помилку")
        
        return 1

def show_help():
    """Показує довідку по використанню"""
    
    help_text = """Game Learning v2.0 - Вивчення англійської через ігрові відео

ВИКОРИСТАННЯ:
    python learning_app_v2.py          # Запуск програми
    python learning_app_v2.py --help   # Показати цю довідку

СИСТЕМНІ ВИМОГИ:
    • Python 3.11+
    • Windows 10/11
    • 8+ GB RAM
    • NVIDIA GPU (опціонально, для прискорення AI)
    • Вільне місце: 5+ GB

ВСТАНОВЛЕННЯ ЗАЛЕЖНОСТЕЙ:
    pip install -r requirements.txt
    winget install Gyan.FFmpeg
    winget install Ollama.Ollama
    ollama pull llama3.1:8b

СТРУКТУРА ПРОЄКТУ:
    videos/           # Відео файли (MKV, MP4, AVI)
    processed/        # Оброблені дані
    config/           # Налаштування
    logs/             # Файли логів

ПІДТРИМУВАНІ ФОРМАТИ:
    • Відео: MKV, MP4, AVI, MOV, WMV
    • Аудіо: WAV, FLAC, MP3 (внутрішньо)
    • Зображення: PNG, JPG, GIF, BMP

КОНТАКТИ:
    GitHub: https://github.com/your-repo
    Email: your-email@example.com

Удачі у вивченні англійської! 🚀"""
    
    print(help_text)

if __name__ == "__main__":
    # Перевіряємо аргументи командного рядка
    if len(sys.argv) > 1:
        if sys.argv[1] in ['--help', '-h', 'help']:
            show_help()
            sys.exit(0)
        elif sys.argv[1] in ['--version', '-v']:
            print("Game Learning v2.0")
            sys.exit(0)
        else:
            print(f"Невідомий аргумент: {sys.argv[1]}")
            print("Використовуйте --help для довідки")
            sys.exit(1)
    
    # Запускаємо програму
    exit_code = main()
    sys.exit(exit_code)