"""
Оновлений SentenceWidget для лаконічних AI відповідей з Skyrim контекстом
ЗМІНИ: Покращене відображення перекладу + граматики, автоматичне розширення поля
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
import threading
import subprocess
from typing import Dict, Optional, Callable
from datetime import datetime

# ФУНКЦІЇ ФОРМАТУВАННЯ ЧАСУ (винесені на початок)
def format_time(seconds: float, short: bool = False) -> str:
    """Форматує час з секунд у зручний формат"""
    if seconds < 0:
        return "0 сек" if not short else "0с"

    total_seconds = int(seconds)
    milliseconds = seconds - total_seconds

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    remaining_seconds = total_seconds % 60

    final_seconds = remaining_seconds + milliseconds

    parts = []

    if short:
        if hours > 0:
            parts.append(f"{hours}г")
        if minutes > 0:
            parts.append(f"{minutes}х")
        if final_seconds > 0 or not parts:
            if final_seconds == int(final_seconds):
                parts.append(f"{int(final_seconds)}с")
            else:
                parts.append(f"{final_seconds:.1f}с")
    else:
        if hours > 0:
            parts.append(f"{hours} год")
        if minutes > 0:
            parts.append(f"{minutes} хв")
        if final_seconds > 0 or not parts:
            if final_seconds == int(final_seconds):
                parts.append(f"{int(final_seconds)} сек")
            else:
                parts.append(f"{final_seconds:.1f} сек")

    return " ".join(parts)

def format_time_range(start_seconds: float, end_seconds: float, short: bool = False) -> str:
    """Форматує часовий діапазон"""
    start_formatted = format_time(start_seconds, short)
    end_formatted = format_time(end_seconds, short)
    separator = " - " if not short else "-"
    return f"{start_formatted}{separator}{end_formatted}"

def format_duration(duration_seconds: float, short: bool = False) -> str:
    """Форматує тривалість"""
    return format_time(duration_seconds, short)


class AutoResizingText(tk.Text):
    """Текстове поле що автоматично змінює висоту залежно від вмісту"""

    def __init__(self, parent, min_height=2, max_height=12, **kwargs):
        """
        ОНОВЛЕНО: Зменшені мін/макс висоти для лаконічних відповідей
        """
        self.min_height = min_height
        self.max_height = max_height

        # Встановлюємо початкову висоту
        kwargs['height'] = min_height

        super().__init__(parent, **kwargs)

        # Прив'язуємо подію зміни вмісту
        self.bind('<<Modified>>', self._on_text_modified)
        self.bind('<KeyRelease>', self._on_text_modified)

        # Початкове налаштування
        self._last_content = ""

    def _on_text_modified(self, event=None):
        """Викликається при зміні тексту"""
        try:
            current_content = self.get(1.0, tk.END)

            # Перевіряємо чи змінився вміст
            if current_content != self._last_content:
                self._last_content = current_content
                self._resize_to_content()

        except Exception as e:
            # Ігноруємо помилки при зміні розміру
            pass

    def _resize_to_content(self):
        """Змінює розмір поля відповідно до вмісту"""
        try:
            # Підраховуємо кількість рядків
            content = self.get(1.0, tk.END).rstrip('\n')
            if not content:
                line_count = 1
            else:
                # Рахуємо рядки з урахуванням переносу слів
                lines = content.split('\n')
                line_count = len(lines)

                # Додаткова перевірка для довгих рядків (враховуємо wrap=WORD)
                for line in lines:
                    if len(line) > 70:  # Приблизна ширина поля для лаконічних відповідей
                        line_count += len(line) // 70

            # Обмежуємо висоту
            new_height = max(self.min_height, min(self.max_height, line_count))

            # Встановлюємо нову висоту тільки якщо вона змінилась
            current_height = int(self.cget('height'))
            if new_height != current_height:
                self.config(height=new_height)

        except Exception as e:
            # У разі помилки встановлюємо мінімальну висоту
            self.config(height=self.min_height)

    def insert(self, index, chars, *args):
        """Перевизначаємо insert для автоматичного ресайзу"""
        super().insert(index, chars, *args)
        self.after_idle(self._resize_to_content)

    def delete(self, index1, index2=None):
        """Перевизначаємо delete для автоматичного ресайзу"""
        super().delete(index1, index2)
        self.after_idle(self._resize_to_content)

    def set_text(self, text):
        """Безпечний метод для встановлення тексту"""
        try:
            self.config(state=tk.NORMAL)
            self.delete(1.0, tk.END)
            self.insert(tk.END, text)
            self._resize_to_content()
        except Exception as e:
            pass


class SentenceWidget:
    """ОНОВЛЕНИЙ віджет для відображення речення з лаконічними AI відповідями"""

    def __init__(self,
                parent_frame: ttk.Frame,
                sentence_data: Dict,
                video_filename: str,
                sentence_index: int,
                ai_manager,
                data_manager,
                on_sentence_click: Optional[Callable] = None):
        """Ініціалізація віджета речення"""

        # Логування з захистом від помилок
        try:
            self.logger = logging.getLogger(__name__)
        except:
            class DummyLogger:
                def info(self, msg): pass
                def error(self, msg): pass
                def debug(self, msg): pass
                def warning(self, msg): pass
            self.logger = DummyLogger()

        # Валідація вхідних параметрів
        if not self._validate_inputs(parent_frame, sentence_data, video_filename, sentence_index):
            raise ValueError("Невалідні вхідні параметри для SentenceWidget")

        self.parent = parent_frame
        self.sentence_data = sentence_data
        self.video_filename = video_filename
        self.sentence_index = sentence_index
        self.ai_manager = ai_manager
        self.data_manager = data_manager
        self.on_sentence_click = on_sentence_click

        # Стан віджета
        self.is_destroyed = False
        self.ai_request_in_progress = False

        # НОВИЙ: Детекція Skyrim контексту
        self.is_skyrim_content = self._detect_skyrim_content()

        # Безпечне створення віджета
        try:
            self.create_widget()
            self.logger.info(f"✅ SentenceWidget {sentence_index} створений успішно")
        except Exception as e:
            self.logger.error(f"❌ Помилка створення віджета {sentence_index}: {e}")
            self._cleanup_on_error()
            raise

    def _validate_inputs(self, parent_frame, sentence_data, video_filename, sentence_index):
        """Валідує вхідні параметри"""
        try:
            # Перевіряємо parent_frame
            if not parent_frame or not hasattr(parent_frame, 'winfo_exists'):
                return False

            # Перевіряємо sentence_data
            required_fields = ['text', 'start_time', 'end_time']
            if not isinstance(sentence_data, dict):
                return False

            for field in required_fields:
                if field not in sentence_data:
                    return False

            # Перевіряємо типи
            if not isinstance(sentence_data['text'], str) or not sentence_data['text'].strip():
                return False

            if not isinstance(sentence_data['start_time'], (int, float)):
                return False

            if not isinstance(sentence_data['end_time'], (int, float)):
                return False

            # Перевіряємо інші параметри
            if not isinstance(video_filename, str) or not video_filename.strip():
                return False

            if not isinstance(sentence_index, int) or sentence_index < 0:
                return False

            return True

        except Exception:
            return False

    def _detect_skyrim_content(self) -> bool:
        """НОВИЙ: Визначає чи це контент з Skyrim"""
        text = self.sentence_data['text'].lower()
        filename = self.video_filename.lower()

        # Skyrim маркери в тексті
        skyrim_phrases = [
            "finally awake", "arrow to the knee", "dragonborn", "thu'um",
            "stormcloaks", "imperial", "jarl", "thane", "septim", "nord",
            "fus ro dah", "whiterun", "solitude", "riften", "companion"
        ]

        # Skyrim маркери в назві файлу
        skyrim_files = ["skyrim", "tes", "elder scrolls", "dovahkiin"]

        text_match = any(phrase in text for phrase in skyrim_phrases)
        file_match = any(marker in filename for marker in skyrim_files)

        return text_match or file_match

    def _cleanup_on_error(self):
        """Очищає ресурси при помилці"""
        try:
            self.is_destroyed = True
            if hasattr(self, 'main_frame'):
                self.main_frame.destroy()
        except:
            pass

    def create_widget(self):
        """Створює оновлений віджет речення з індикатором Skyrim"""
        try:
            if not self.parent.winfo_exists():
                raise Exception("Батьківський фрейм було знищено")

            # Обчислюємо тривалість та форматуємо час
            duration = self.sentence_data['end_time'] - self.sentence_data['start_time']
            duration_text = format_duration(duration, short=True)
            start_time_text = format_time(self.sentence_data['start_time'], short=True)

            # ОНОВЛЕНИЙ заголовок з індикатором Skyrim
            title_text = f"Речення {self.sentence_index + 1} • {start_time_text} • {duration_text}"
            if self.is_skyrim_content:
                title_text += " 🐉"  # Дракон для Skyrim контенту

            self.main_frame = ttk.LabelFrame(self.parent, text=title_text)
            self.main_frame.pack(fill=tk.X, padx=5, pady=3)

            # Налаштування стилів
            self.setup_styles()

            # Створюємо секції
            self.create_english_section()
            self.create_control_buttons()
            self.create_combined_ai_section()  # НОВИЙ: Комбінована секція

            # Прив'язуємо події
            self.bind_events()

            # Завантажуємо збережені дані
            self.root_after_safe(100, self.load_saved_responses)

        except Exception as e:
            self.logger.error(f"Помилка створення віджета: {e}")
            self._cleanup_on_error()
            raise

    def setup_styles(self):
        """Налаштовує стилі з урахуванням Skyrim контексту"""
        self.colors = {
            'default_bg': '#f8f9fa',
            'edited_bg': '#e8f5e8',
            'loading_bg': '#fff3cd',
            'error_bg': '#f8d7da',
            'english_bg': '#f0f0f0',
            'skyrim_bg': '#e6f3ff' if self.is_skyrim_content else '#f8f9fa'  # НОВИЙ: синий фон для Skyrim
        }

    def create_english_section(self):
        """Створює секцію англійського тексту"""
        try:
            english_frame = ttk.Frame(self.main_frame)
            english_frame.pack(fill=tk.X, padx=5, pady=5)

            # ОНОВЛЕНИЙ заголовок з іконкою залежно від контенту
            icon = "🐉" if self.is_skyrim_content else "🇬🇧"
            context = "TES Skyrim" if self.is_skyrim_content else "English"
            header_label = ttk.Label(english_frame, text=f"{icon} {context}:", font=("Arial", 10, "bold"))
            header_label.pack(anchor=tk.W)

            # Текстове поле з відповідним фоном
            bg_color = self.colors['skyrim_bg'] if self.is_skyrim_content else self.colors['english_bg']

            self.english_text = tk.Text(
                english_frame,
                height=2,
                font=("Arial", 11),
                bg=bg_color,
                relief=tk.FLAT,
                borderwidth=1,
                state=tk.DISABLED,
                cursor="hand2",
                wrap=tk.WORD
            )
            self.english_text.pack(fill=tk.X, pady=(2, 0))

            # Вставляємо текст безпечно
            self.safe_text_insert(self.english_text, self.sentence_data['text'])

            # Інформаційна панель з форматованим часом
            time_range = format_time_range(
                self.sentence_data['start_time'],
                self.sentence_data['end_time'],
                short=True
            )

            duration = self.sentence_data['end_time'] - self.sentence_data['start_time']
            duration_text = format_duration(duration, short=True)

            info_parts = [f"⏰ {time_range}", f"⏱️ {duration_text}"]

            if 'confidence' in self.sentence_data and self.sentence_data['confidence'] > 0:
                info_parts.append(f"📊 {self.sentence_data['confidence']:.1%}")

            # НОВИЙ: Додаємо індикатор Skyrim контексту
            if self.is_skyrim_content:
                info_parts.append("🎮 Skyrim")

            info_text = " • ".join(info_parts)
            info_label = ttk.Label(english_frame, text=info_text, font=("Arial", 9))
            info_label.pack(anchor=tk.W, pady=(2, 0))

        except Exception as e:
            self.logger.error(f"Помилка створення англійської секції: {e}")
            raise

    def create_control_buttons(self):
        """Створює спрощені кнопки управління"""
        try:
            buttons_frame = ttk.Frame(self.main_frame)
            buttons_frame.pack(fill=tk.X, padx=5, pady=(0, 5))

            # Ліві кнопки
            left_frame = ttk.Frame(buttons_frame)
            left_frame.pack(side=tk.LEFT)

            ttk.Button(left_frame, text="▶ Відео",
                      command=self.safe_call(self.play_video_moment), width=8).pack(side=tk.LEFT, padx=2)

            ttk.Button(left_frame, text="📋 Копія",
                      command=self.safe_call(self.copy_sentence), width=8).pack(side=tk.LEFT, padx=2)

        except Exception as e:
            self.logger.error(f"Помилка створення кнопок: {e}")
            raise

    def create_combined_ai_section(self):
        """НОВИЙ: Створює комбіновану секцію для перекладу + граматики"""
        try:
            # Заголовок
            ai_header = ttk.Frame(self.main_frame)
            ai_header.pack(fill=tk.X, padx=5, pady=(5, 0))

            # ОНОВЛЕНИЙ заголовок залежно від контексту
            title = "🐉 Skyrim переклад + граматика:" if self.is_skyrim_content else "📚 Переклад + граматика:"
            ttk.Label(ai_header, text=title, font=("Arial", 10, "bold")).pack(side=tk.LEFT)

            # ОНОВЛЕНА кнопка з відповідним текстом
            button_text = "🐉 Аналіз" if self.is_skyrim_content else "🤖 Аналіз"
            ttk.Button(ai_header, text=button_text,
                      command=self.safe_call(self.generate_combined_analysis),
                      width=12).pack(side=tk.RIGHT)

            # ОНОВЛЕНЕ автоматично розширюване поле (менші розміри для лаконічності)
            self.combined_ai_text = AutoResizingText(
                self.main_frame,
                min_height=2,  # Зменшено з 3
                max_height=8,  # Зменшено з 15
                font=("Arial", 10),
                bg=self.colors['default_bg'],
                relief=tk.FLAT,
                borderwidth=1,
                wrap=tk.WORD
            )
            self.combined_ai_text.pack(fill=tk.X, padx=5, pady=(2, 5))

        except Exception as e:
            self.logger.error(f"Помилка створення AI секції: {e}")
            raise

    def bind_events(self):
        """Прив'язує події"""
        try:
            # Клік по реченню
            self.english_text.bind('<Button-1>', self.safe_call(self.on_sentence_selected))
            self.main_frame.bind('<Button-1>', self.safe_call(self.on_sentence_selected))

        except Exception as e:
            self.logger.error(f"Помилка прив'язки подій: {e}")

    def safe_call(self, func):
        """Обгортка для безпечного виклику функцій"""
        def wrapper(*args, **kwargs):
            try:
                if self.is_destroyed:
                    return
                return func(*args, **kwargs)
            except Exception as e:
                self.logger.error(f"Помилка у {func.__name__}: {e}")
        return wrapper

    def safe_text_insert(self, text_widget, content):
        """Безпечна вставка тексту"""
        try:
            text_widget.config(state=tk.NORMAL)
            text_widget.delete(1.0, tk.END)
            text_widget.insert(tk.END, content)
            text_widget.config(state=tk.DISABLED)
        except Exception as e:
            self.logger.error(f"Помилка вставки тексту: {e}")

    def root_after_safe(self, delay, func):
        """Безпечний after виклик"""
        try:
            if not self.is_destroyed and self.main_frame.winfo_exists():
                self.main_frame.after(delay, func)
        except Exception as e:
            self.logger.error(f"Помилка root.after: {e}")

    def copy_sentence(self):
        """Копіює речення у буфер з форматованим часом та AI відповіддю"""
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")

            # Покращене форматування часової інформації
            time_range = format_time_range(
                self.sentence_data['start_time'],
                self.sentence_data['end_time']
            )
            duration = self.sentence_data['end_time'] - self.sentence_data['start_time']
            duration_text = format_duration(duration)

            text_to_copy = f"[{timestamp}] {self.video_filename}\n"
            text_to_copy += f"🕐 Час: {time_range} (тривалість: {duration_text})\n"

            # НОВИЙ: Додаємо індикатор Skyrim
            if self.is_skyrim_content:
                text_to_copy += f"🐉 TES Skyrim: {self.sentence_data['text']}\n"
            else:
                text_to_copy += f"🇬🇧 English: {self.sentence_data['text']}\n"

            # Додаємо AI аналіз якщо є
            ai_content = self.combined_ai_text.get(1.0, tk.END).strip()
            if ai_content and "Натисніть" not in ai_content:
                text_to_copy += f"\n{ai_content}\n"

            text_to_copy += "─" * 50

            self.main_frame.clipboard_clear()
            self.main_frame.clipboard_append(text_to_copy)

            # Повідомлення з форматованим часом
            start_time_short = format_time(self.sentence_data['start_time'], short=True)
            self.show_temporary_message(f"✅ Скопійовано ({start_time_short})")

        except Exception as e:
            self.logger.error(f"Помилка копіювання: {e}")

    def show_temporary_message(self, message: str, duration: int = 2000):
        """Показує тимчасове повідомлення"""
        try:
            # Видаляємо попереднє повідомлення
            if hasattr(self, 'temp_message_label'):
                self.temp_message_label.destroy()

            # Створюємо нове
            self.temp_message_label = tk.Label(
                self.main_frame,
                text=message,
                bg="#d4edda",
                fg="#155724",
                font=("Arial", 9, "bold"),
                relief=tk.RAISED,
                borderwidth=1,
                padx=10,
                pady=2
            )

            # Показуємо в правому верхньому куті
            self.temp_message_label.place(relx=1.0, rely=0.0, anchor="ne")

            # Автоматично ховаємо
            self.root_after_safe(duration, self.hide_temporary_message)

        except Exception as e:
            self.logger.error(f"Помилка показу повідомлення: {e}")

    def hide_temporary_message(self):
        """Ховає тимчасове повідомлення"""
        try:
            if hasattr(self, 'temp_message_label'):
                self.temp_message_label.destroy()
                delattr(self, 'temp_message_label')
        except:
            pass

    def on_sentence_selected(self, event=None):
        """Обробляє вибір речення"""
        try:
            if self.on_sentence_click:
                self.on_sentence_click(self.sentence_data, self.video_filename)
        except Exception as e:
            self.logger.error(f"Помилка вибору речення: {e}")

    def generate_combined_analysis(self):
        """НОВИЙ: Генерує комбінований аналіз (переклад + граматика)"""
        try:
            if not self.ai_manager or not self.ai_manager.is_available():
                self.show_temporary_message("❌ AI недоступний")
                return

            # Запобігаємо дублюванню запитів
            if self.ai_request_in_progress:
                self.show_temporary_message("⏳ Запит вже обробляється...")
                return

            self.ai_request_in_progress = True
            threading.Thread(target=self.safe_call(self._generate_combined_analysis_thread), daemon=True).start()

        except Exception as e:
            self.logger.error(f"Помилка генерації аналізу: {e}")
            self.show_temporary_message("❌ Помилка запиту")

    def _generate_combined_analysis_thread(self):
        """Генерує комбінований аналіз в потоці"""
        try:
            # Оновлюємо UI для завантаження
            self._update_ui_loading()

            # Генеруємо граматичне пояснення (нова версія вже включає переклад)
            result = self.ai_manager.explain_grammar(self.sentence_data['text'])

            # Оновлюємо результат
            self._update_combined_response(result)

        except Exception as e:
            self.logger.error(f"Помилка генерації аналізу в потоці: {e}")
            self._update_ui_error(str(e))
        finally:
            self.ai_request_in_progress = False

    def _update_ui_loading(self):
        """Оновлює UI для завантаження"""
        def update():
            try:
                if self.is_destroyed or not self.combined_ai_text.winfo_exists():
                    return

                self.combined_ai_text.config(bg=self.colors['loading_bg'])
                loading_text = "🐉 Аналіз Skyrim діалогу..." if self.is_skyrim_content else "🔄 Генерація аналізу..."
                self.combined_ai_text.set_text(loading_text)

            except Exception as e:
                self.logger.error(f"Помилка оновлення UI loading: {e}")

        self.root_after_safe(0, update)

    def _update_ui_error(self, error_msg: str):
        """Оновлює UI для помилки"""
        def update():
            try:
                if self.is_destroyed or not self.combined_ai_text.winfo_exists():
                    return

                self.combined_ai_text.config(bg=self.colors['error_bg'])
                self.combined_ai_text.set_text(f"❌ Помилка: {error_msg}")

            except Exception as e:
                self.logger.error(f"Помилка оновлення UI error: {e}")

        self.root_after_safe(0, update)

    def _update_combined_response(self, result: Dict):
        """НОВИЙ: Оновлює комбіновану відповідь в UI"""
        def update():
            try:
                if self.is_destroyed or not self.combined_ai_text.winfo_exists():
                    return

                if result.get('success'):
                    # Визначаємо фон залежно від результату
                    bg_color = self.colors['skyrim_bg'] if result.get('is_skyrim', False) else self.colors['default_bg']
                    self.combined_ai_text.config(bg=bg_color)
                    self.combined_ai_text.set_text(result['result'])

                    # Зберігаємо в БД як граматичне пояснення
                    if self.data_manager:
                        try:
                            self.data_manager.save_ai_response(
                                sentence_text=self.sentence_data['text'],
                                video_filename=self.video_filename,
                                start_time=self.sentence_data['start_time'],
                                end_time=self.sentence_data['end_time'],
                                response_type='grammar',
                                ai_response=result['result'],
                                ai_client='llama3.1'
                            )
                        except Exception as save_error:
                            self.logger.error(f"Помилка збереження аналізу: {save_error}")

                    # Показуємо успішне повідомлення
                    icon = "🐉" if result.get('is_skyrim', False) else "✅"
                    self.show_temporary_message(f"{icon} Аналіз готовий")
                else:
                    self.combined_ai_text.config(bg=self.colors['error_bg'])
                    self.combined_ai_text.set_text(f"❌ {result.get('error', 'Невідома помилка')}")

            except Exception as e:
                self.logger.error(f"Помилка оновлення комбінованої відповіді: {e}")

        self.root_after_safe(0, update)

    def load_saved_responses(self):
        """Завантажує збережений аналіз"""
        try:
            if not self.data_manager or self.is_destroyed:
                return

            # Завантажуємо граматику (тепер включає переклад)
            grammar = self.data_manager.get_ai_response(
                sentence_text=self.sentence_data['text'],
                video_filename=self.video_filename,
                start_time=self.sentence_data['start_time'],
                response_type='grammar'
            )

            if grammar and hasattr(self, 'combined_ai_text'):
                try:
                    display_text = grammar.get('edited_text') or grammar.get('ai_response', '')
                    if display_text:
                        self.combined_ai_text.set_text(display_text)

                        # Встановлюємо фон залежно від типу контенту та редагування
                        if grammar.get('is_edited'):
                            bg_color = self.colors['edited_bg']
                        elif self.is_skyrim_content:
                            bg_color = self.colors['skyrim_bg']
                        else:
                            bg_color = self.colors['default_bg']

                        self.combined_ai_text.config(bg=bg_color)
                    else:
                        self._set_placeholder_text()
                except Exception as e:
                    self.logger.error(f"Помилка завантаження аналізу: {e}")
            else:
                # Якщо немає збережених даних
                self._set_placeholder_text()

        except Exception as e:
            self.logger.error(f"Помилка завантаження відповідей: {e}")

    def _set_placeholder_text(self):
        """Встановлює текст-заглушку"""
        try:
            if self.is_skyrim_content:
                placeholder_text = "🐉 Натисніть 'Аналіз' для перекладу та граматичного пояснення Skyrim діалогу"
            else:
                placeholder_text = "💡 Натисніть 'Аналіз' для отримання перекладу та граматичного пояснення"

            self.combined_ai_text.set_text(placeholder_text)
        except:
            pass

    def play_video_moment(self):
        """Відкриває відео в момент речення"""
        try:
            video_path = None

            # Пошук відео
            try:
                from processing.database_manager import DatabaseManager
                db_manager = DatabaseManager()
                videos = db_manager.get_all_videos()
                for video in videos:
                    if video['filename'] == self.video_filename:
                        video_path = video['filepath']
                        break
            except:
                from pathlib import Path
                videos_dir = Path("videos")
                potential_path = videos_dir / self.video_filename
                if potential_path.exists():
                    video_path = str(potential_path)

            if not video_path:
                self.show_temporary_message("❌ Відео не знайдено")
                return

            start_time = self.sentence_data['start_time']
            formatted_time = format_time(start_time, short=True)

            # Спроба запуску різних плеєрів
            players = [
                (['vlc', video_path, f'--start-time={start_time}', '--intf=dummy'], "VLC"),
                (['mpv', video_path, f'--start={start_time}'], "MPV"),
                (['ffplay', video_path, '-ss', str(start_time)], "FFplay")
            ]

            for cmd, name in players:
                try:
                    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    icon = "🐉" if self.is_skyrim_content else "✅"
                    self.show_temporary_message(f"{icon} {name} відкрито на {formatted_time}")
                    return
                except FileNotFoundError:
                    continue

            # Стандартний плеєр
            try:
                import os
                os.startfile(video_path)
                self.show_temporary_message(f"✅ Відкрито (перемотайте на {formatted_time})")
            except:
                self.show_temporary_message("❌ Не вдалося відкрити")

        except Exception as e:
            self.logger.error(f"Помилка відкриття відео: {e}")
            self.show_temporary_message("❌ Помилка відкриття")

    def destroy(self):
        """Безпечне знищення віджета"""
        try:
            self.is_destroyed = True
            self.ai_request_in_progress = False

            if hasattr(self, 'main_frame') and self.main_frame.winfo_exists():
                self.main_frame.destroy()

        except Exception as e:
            self.logger.error(f"Помилка знищення віджета: {e}")


# ==============================================================
# ТЕСТУВАННЯ ОНОВЛЕНОГО ВІДЖЕТА З SKYRIM ПІДТРИМКОЮ
# ==============================================================

if __name__ == "__main__":
    """Тестування оновленого SentenceWidget з підтримкою Skyrim"""

    print("Тестування оновленого SentenceWidget для Skyrim:")
    print("=" * 60)
    print("✅ Детекція Skyrim контенту")
    print("✅ Лаконічні відповіді (переклад + граматика)")
    print("✅ Автоматично розширюване поле (2-8 рядків)")
    print("✅ Спеціальні іконки для Skyrim")
    print("✅ Оптимізовані промпти")

    # Тест GUI
    try:
        root = tk.Tk()
        root.title("Тест Skyrim SentenceWidget")
        root.geometry("1200x900")

        # Створюємо тестові дані з Skyrim фразами
        test_sentences = [
            {
                'text': "You're finally awake! You were trying to cross the border, right?",
                'start_time': 0.5,
                'end_time': 4.6,
                'confidence': 0.952
            },
            {
                'text': "I used to be an adventurer like you, then I took an arrow to the knee.",
                'start_time': 15.1,
                'end_time': 19.7,
                'confidence': 0.981
            },
            {
                'text': "This is a regular English sentence without any game context.",
                'start_time': 25.2,
                'end_time': 28.9,
                'confidence': 0.963
            }
        ]

        # Заглушки для менеджерів з Skyrim підтримкою
        class DummyAISkyrimManager:
            def is_available(self):
                return True

            def explain_grammar(self, text):
                if "awake" in text.lower():
                    return {
                        'success': True,
                        'result': "🇺🇦 ПЕРЕКЛАД: Ти нарешті прокинувся! Ти намагався перетнути кордон, правда?\n\n📚 ГРАМАТИКА: Present Perfect (You're = You are) + питальна форма 'right?' для підтвердження.",
                        'is_skyrim': True
                    }
                elif "arrow to the knee" in text.lower():
                    return {
                        'success': True,
                        'result': "🇺🇦 ПЕРЕКЛАД: Колись я був пригодником, як ти, але потім отримав стрілу в коліно.\n\n📚 ГРАМАТИКА: Past Simple з 'used to' (минула звичка) + Past Simple в складному реченні.",
                        'is_skyrim': True
                    }
                else:
                    return {
                        'success': True,
                        'result': "🇺🇦 ПЕРЕКЛАД: Це звичайне англійське речення без ігрового контексту.\n\n📚 ГРАМАТИКА: Present Simple з демонстративним займенником 'this' + прикметники.",
                        'is_skyrim': False
                    }

        class DummyDataManager:
            def get_ai_response(self, **kwargs):
                return None
            def save_ai_response(self, **kwargs):
                pass

        # Створюємо контейнер з прокруткою
        main_frame = ttk.Frame(root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Інструкції
        instructions = tk.Label(
            scrollable_frame,
            text="🐉 ТЕСТ SKYRIM SENTENCEWIDGET:\n\n"
                 "✅ Перші два речення - автоматична детекція Skyrim (іконка 🐉)\n"
                 "✅ Третє речення - звичайний контент (іконка 🇬🇧)\n"
                 "✅ Лаконічні відповіді: переклад + коротка граматика\n"
                 "✅ Автоматично розширюване поле (2-8 рядків)\n"
                 "✅ Спеціальний фон для Skyrim контенту\n"
                 "✅ Натисніть 'Аналіз' на різних реченнях для тесту",
            font=("Arial", 11),
            justify=tk.LEFT,
            bg="#e6f3ff",
            padx=15,
            pady=15,
            relief=tk.RAISED,
            borderwidth=2
        )
        instructions.pack(fill=tk.X, pady=(0, 15))

        # Створюємо віджети для кожного речення
        widgets = []
        filenames = ["skyrim_intro.mkv", "skyrim_guards.mkv", "regular_video.mp4"]

        for i, sentence_data in enumerate(test_sentences):
            try:
                widget = SentenceWidget(
                    parent_frame=scrollable_frame,
                    sentence_data=sentence_data,
                    video_filename=filenames[i],
                    sentence_index=i,
                    ai_manager=DummyAISkyrimManager(),
                    data_manager=DummyDataManager(),
                    on_sentence_click=lambda data, filename: print(f"Вибрано: {data['text'][:30]}...")
                )
                widgets.append(widget)

                skyrim_status = "🐉 Skyrim" if widget.is_skyrim_content else "🇬🇧 Regular"
                print(f"✅ Речення {i+1} створено: {skyrim_status}")

            except Exception as e:
                print(f"❌ Помилка створення речення {i+1}: {e}")

        # Прив'язуємо прокрутку
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        print(f"\n✅ Створено {len(widgets)} віджетів успішно!")
        print("🐉 Натисніть 'Аналіз' для тесту лаконічних Skyrim відповідей")
        print("🚀 Запуск GUI...")

        root.mainloop()

    except Exception as e:
        print(f"❌ Помилка GUI тесту: {e}")
        import traceback
        traceback.print_exc()