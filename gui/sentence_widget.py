"""
Оновлений SentenceWidget з автоматично розширюваним полем граматики
Без згортання/розгортання, тільки поле граматичного пояснення
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
    
    def __init__(self, parent, min_height=3, max_height=15, **kwargs):
        """
        parent: батьківський віджет
        min_height: мінімальна висота в рядках
        max_height: максимальна висота в рядках
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
                    if len(line) > 80:  # Приблизна ширина поля
                        line_count += len(line) // 80
            
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
    """Спрощений віджет для відображення речення тільки з граматичним поясненням"""
    
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
    
    def _cleanup_on_error(self):
        """Очищає ресурси при помилці"""
        try:
            self.is_destroyed = True
            if hasattr(self, 'main_frame'):
                self.main_frame.destroy()
        except:
            pass
    
    def create_widget(self):
        """Створює спрощений віджет речення"""
        try:
            if not self.parent.winfo_exists():
                raise Exception("Батьківський фрейм було знищено")
            
            # Обчислюємо тривалість та форматуємо час
            duration = self.sentence_data['end_time'] - self.sentence_data['start_time']
            duration_text = format_duration(duration, short=True)
            start_time_text = format_time(self.sentence_data['start_time'], short=True)
            
            # Заголовок з форматованим часом
            title_text = (f"Речення {self.sentence_index + 1} • "
                         f"{start_time_text} • тривалість: {duration_text}")
            
            self.main_frame = ttk.LabelFrame(self.parent, text=title_text)
            self.main_frame.pack(fill=tk.X, padx=5, pady=3)
            
            # Налаштування стилів
            self.setup_styles()
            
            # Створюємо секції
            self.create_english_section()
            self.create_control_buttons()
            self.create_grammar_section()
            
            # Прив'язуємо події
            self.bind_events()
            
            # Завантажуємо збережені дані
            self.root_after_safe(100, self.load_saved_responses)
            
        except Exception as e:
            self.logger.error(f"Помилка створення віджета: {e}")
            self._cleanup_on_error()
            raise
    
    def setup_styles(self):
        """Налаштовує стилі"""
        self.colors = {
            'default_bg': '#f8f9fa',
            'edited_bg': '#e8f5e8',
            'loading_bg': '#fff3cd',
            'error_bg': '#f8d7da',
            'english_bg': '#f0f0f0'
        }
    
    def create_english_section(self):
        """Створює секцію англійського тексту"""
        try:
            english_frame = ttk.Frame(self.main_frame)
            english_frame.pack(fill=tk.X, padx=5, pady=5)
            
            # Заголовок
            header_label = ttk.Label(english_frame, text="🇬🇧 English:", font=("Arial", 10, "bold"))
            header_label.pack(anchor=tk.W)
            
            # Текстове поле
            self.english_text = tk.Text(
                english_frame,
                height=2,
                font=("Arial", 11),
                bg=self.colors['english_bg'],
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
    
    def create_grammar_section(self):
        """Створює секцію граматики з автоматично розширюваним полем"""
        try:
            # Заголовок
            grammar_header = ttk.Frame(self.main_frame)
            grammar_header.pack(fill=tk.X, padx=5, pady=(5, 0))
            
            ttk.Label(grammar_header, text="📚 Граматичне пояснення:", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
            ttk.Button(grammar_header, text="🤖 Пояснити", 
                      command=self.safe_call(self.generate_grammar_explanation),
                      width=12).pack(side=tk.RIGHT)
            
            # Автоматично розширюване поле
            self.grammar_text = AutoResizingText(
                self.main_frame,
                min_height=3,
                max_height=15,  # Максимум 15 рядків
                font=("Arial", 10),
                bg=self.colors['default_bg'],
                relief=tk.FLAT,
                borderwidth=1,
                wrap=tk.WORD
            )
            self.grammar_text.pack(fill=tk.X, padx=5, pady=(2, 5))
            
        except Exception as e:
            self.logger.error(f"Помилка створення секції граматики: {e}")
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
        """Копіює речення у буфер з форматованим часом"""
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
            text_to_copy += f"🇬🇧 {self.sentence_data['text']}\n"
            
            # Додаємо граматичне пояснення якщо є
            grammar_content = self.grammar_text.get(1.0, tk.END).strip()
            if grammar_content and grammar_content != "💡 Натисніть 'Пояснити' для отримання граматичного аналізу":
                text_to_copy += f"📚 Граматика: {grammar_content}\n"
            
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
    
    def generate_grammar_explanation(self):
        """Генерує граматичне пояснення"""
        try:
            if not self.ai_manager or not self.ai_manager.is_available():
                self.show_temporary_message("❌ AI недоступний")
                return
            
            # Запобігаємо дублюванню запитів
            if self.ai_request_in_progress:
                self.show_temporary_message("⏳ Запит вже обробляється...")
                return
            
            self.ai_request_in_progress = True
            threading.Thread(target=self.safe_call(self._generate_grammar_thread), daemon=True).start()
            
        except Exception as e:
            self.logger.error(f"Помилка генерації граматики: {e}")
            self.show_temporary_message("❌ Помилка запиту")
    
    def _generate_grammar_thread(self):
        """Генерує граматичне пояснення в потоці"""
        try:
            # Оновлюємо UI для завантаження
            self._update_ui_loading()
            
            # Генеруємо граматичне пояснення
            result = self.ai_manager.explain_grammar(self.sentence_data['text'])
            
            # Оновлюємо результат
            self._update_grammar_response(result)
            
        except Exception as e:
            self.logger.error(f"Помилка генерації граматики в потоці: {e}")
            self._update_ui_error(str(e))
        finally:
            self.ai_request_in_progress = False
    
    def _update_ui_loading(self):
        """Оновлює UI для завантаження"""
        def update():
            try:
                if self.is_destroyed or not self.grammar_text.winfo_exists():
                    return
                    
                self.grammar_text.config(bg=self.colors['loading_bg'])
                self.grammar_text.set_text("🔄 Генерація граматичного пояснення...")
                    
            except Exception as e:
                self.logger.error(f"Помилка оновлення UI loading: {e}")
        
        self.root_after_safe(0, update)
    
    def _update_ui_error(self, error_msg: str):
        """Оновлює UI для помилки"""
        def update():
            try:
                if self.is_destroyed or not self.grammar_text.winfo_exists():
                    return
                    
                self.grammar_text.config(bg=self.colors['error_bg'])
                self.grammar_text.set_text(f"❌ Помилка: {error_msg}")
                    
            except Exception as e:
                self.logger.error(f"Помилка оновлення UI error: {e}")
        
        self.root_after_safe(0, update)
    
    def _update_grammar_response(self, result: Dict):
        """Оновлює граматичне пояснення в UI"""
        def update():
            try:
                if self.is_destroyed or not self.grammar_text.winfo_exists():
                    return
                
                if result.get('success'):
                    self.grammar_text.config(bg=self.colors['default_bg'])
                    self.grammar_text.set_text(result['result'])
                    
                    # Зберігаємо в БД
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
                            self.logger.error(f"Помилка збереження граматики: {save_error}")
                else:
                    self.grammar_text.config(bg=self.colors['error_bg'])
                    self.grammar_text.set_text(f"❌ {result.get('error', 'Невідома помилка')}")
                    
            except Exception as e:
                self.logger.error(f"Помилка оновлення граматичної відповіді: {e}")
        
        self.root_after_safe(0, update)
    
    def load_saved_responses(self):
        """Завантажує збережене граматичне пояснення"""
        try:
            if not self.data_manager or self.is_destroyed:
                return
            
            # Завантажуємо граматику
            grammar = self.data_manager.get_ai_response(
                sentence_text=self.sentence_data['text'],
                video_filename=self.video_filename,
                start_time=self.sentence_data['start_time'],
                response_type='grammar'
            )
            
            if grammar and hasattr(self, 'grammar_text'):
                try:
                    display_text = grammar.get('edited_text') or grammar.get('ai_response', '')
                    if display_text:
                        self.grammar_text.set_text(display_text)
                        bg_color = self.colors['edited_bg'] if grammar.get('is_edited') else self.colors['default_bg']
                        self.grammar_text.config(bg=bg_color)
                    else:
                        self.grammar_text.set_text("💡 Натисніть 'Пояснити' для отримання граматичного аналізу")
                except Exception as e:
                    self.logger.error(f"Помилка завантаження граматики: {e}")
            else:
                # Якщо немає збережених даних
                try:
                    self.grammar_text.set_text("💡 Натисніть 'Пояснити' для отримання граматичного аналізу")
                except:
                    pass
            
        except Exception as e:
            self.logger.error(f"Помилка завантаження відповідей: {e}")
    
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
                    self.show_temporary_message(f"✅ {name} відкрито на {formatted_time}")
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
# ТЕСТУВАННЯ ОНОВЛЕНОГО ВІДЖЕТА
# ==============================================================

if __name__ == "__main__":
    """Тестування спрощеного SentenceWidget з автоматично розширюваним полем граматики"""
    
    print("Тестування оновленого SentenceWidget:")
    print("=" * 50)
    print("✅ Прибрано згортання/розгортання")
    print("✅ Прибрано переклад")
    print("✅ Додано автоматично розширюване поле граматики")
    print("✅ Всі речення відображаються одразу")
    
    # Тест GUI
    try:
        root = tk.Tk()
        root.title("Тест оновленого SentenceWidget")
        root.geometry("1000x800")
        
        # Створюємо тестові дані
        test_sentences = [
            {
                'text': "You're finally awake! You were trying to cross the border, right?",
                'start_time': 78.5,
                'end_time': 125.2,
                'confidence': 0.952
            },
            {
                'text': "Walked right into that Imperial ambush, same as us, and that thief over there.",
                'start_time': 126.1,
                'end_time': 182.7,
                'confidence': 0.981
            },
            {
                'text': "Damn you Stormcloaks. Skyrim was fine until you came along.",
                'start_time': 183.2,
                'end_time': 198.9,
                'confidence': 0.963
            }
        ]
        
        # Заглушки для менеджерів
        class DummyAIManager:
            def is_available(self): 
                return True
            
            def explain_grammar(self, text):
                # Симуляція різного розміру відповідей
                if "awake" in text:
                    return {
                        'success': True, 
                        'result': "Коротке пояснення: Present Perfect tense з 'finally'."
                    }
                elif "ambush" in text:
                    return {
                        'success': True, 
                        'result': """Детальне граматичне пояснення:

1. "Walked right into" - Past Simple, неформальний тон
2. "that Imperial ambush" - вказівний займенник "that"
3. "same as us" - порівняльна конструкція
4. "and that thief over there" - складносурядне речення з паралельною структурою

Це речення демонструє розмовний стиль англійської мови з елементами неформального синтаксису."""
                    }
                else:
                    return {
                        'success': True, 
                        'result': """Розширене граматичне пояснення для демонстрації автоматичного розширення поля:

1. "Damn you Stormcloaks" - вигук з прямим звертанням
2. "Skyrim was fine" - Past Simple з прикметником у функції присудка
3. "until you came along" - підрядне речення часу з Past Simple
4. Складне речення з підрядним часу

Цей приклад показує як поле автоматично розширюється для довших текстів, забезпечуючи оптимальну читабельність без необхідності прокрутки.

Додаткові граматичні особливості:
- Емоційне забарвлення через лайливе слово
- Неформальний тон розмови
- Використання фразового дієслова "came along"

Поле буде автоматично адаптуватися до розміру цього тексту!"""
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
            text="🎯 ТЕСТ ОНОВЛЕНОГО SENTENCEWIDGET:\n\n"
                 "✅ Прибрано згортання/розгортання - всі речення видимі\n"
                 "✅ Прибрано переклад - тільки граматичне пояснення\n"
                 "✅ Автоматично розширюване поле граматики (3-15 рядків)\n"
                 "✅ Натисніть 'Пояснити' на різних реченнях для тесту розширення\n"
                 "✅ Перше речення - коротка відповідь (3 рядки)\n"
                 "✅ Друге речення - середня відповідь (6-8 рядків)\n" 
                 "✅ Третє речення - довга відповідь (12+ рядків)",
            font=("Arial", 11),
            justify=tk.LEFT,
            bg="#e8f5e8",
            padx=15,
            pady=15,
            relief=tk.RAISED,
            borderwidth=2
        )
        instructions.pack(fill=tk.X, pady=(0, 15))
        
        # Створюємо віджети для кожного речення
        widgets = []
        for i, sentence_data in enumerate(test_sentences):
            try:
                widget = SentenceWidget(
                    parent_frame=scrollable_frame,
                    sentence_data=sentence_data,
                    video_filename="skyrim_intro.mkv",
                    sentence_index=i,
                    ai_manager=DummyAIManager(),
                    data_manager=DummyDataManager(),
                    on_sentence_click=lambda data, filename: print(f"Вибрано: {data['text'][:30]}...")
                )
                widgets.append(widget)
                
                print(f"✅ Речення {i+1} створено успішно")
                
            except Exception as e:
                print(f"❌ Помилка створення речення {i+1}: {e}")
        
        # Додаємо демо-функціонал
        demo_frame = ttk.LabelFrame(scrollable_frame, text="🔧 Демо-функції", padding="10")
        demo_frame.pack(fill=tk.X, pady=10)
        
        def test_auto_resize():
            """Тестує автоматичне розширення"""
            test_text = """Це тест автоматичного розширення поля!
            
Перший рядок - коротко.
Другий рядок трохи довший для демонстрації.
Третій рядок ще довший і показує як поле автоматично адаптується до розміру контенту.
Четвертий рядок продовжує демонстрацію функціоналу автоматичного ресайзингу.
П'ятий рядок показує що поле може розширюватися до 15 рядків максимум.

Поле автоматично:
- Розширюється при додаванні тексту
- Зменшується при видаленні
- Зберігає мінімум 3 рядки
- Обмежується максимумом 15 рядків
- Враховує перенос слів

Це значно покращує користувацький досвід!"""
            
            if widgets:
                widgets[0].grammar_text.set_text(test_text)
                print("🔧 Тест автоматичного розширення застосовано до першого речення")
        
        def clear_all():
            """Очищає всі поля граматики"""
            for widget in widgets:
                widget.grammar_text.set_text("💡 Натисніть 'Пояснити' для отримання граматичного аналізу")
            print("🧹 Всі поля граматики очищено")
        
        ttk.Button(demo_frame, text="🔧 Тест автоматичного розширення", 
                  command=test_auto_resize).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(demo_frame, text="🧹 Очистити всі поля", 
                  command=clear_all).pack(side=tk.LEFT, padx=5)
        
        # Прив'язуємо прокрутку
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        print(f"\n✅ Створено {len(widgets)} віджетів успішно!")
        print("🎯 Натисніть 'Пояснити' на різних реченнях для тесту автоматичного розширення")
        print("🚀 Запуск GUI...")
        
        root.mainloop()
        
    except Exception as e:
        print(f"❌ Помилка GUI тесту: {e}")
        import traceback
        traceback.print_exc()


# ==============================================================
# ІНСТРУКЦІЇ ДЛЯ ІНТЕГРАЦІЇ
# ==============================================================

"""
🎯 ОСНОВНІ ЗМІНИ В ОНОВЛЕНОМУ SENTENCEWIDGET:

✅ ПРИБРАНО:
- Функціонал згортання/розгортання (expand/collapse)
- Секція перекладу
- Кнопка "🤖 AI" (генерація всіх відповідей)
- ai_frame та його управління

✅ ДОДАНО:
- Клас AutoResizingText для автоматичного розширення
- Спрощена структура віджета
- Покращене граматичне пояснення
- Оптимізація продуктивності

✅ ЗБЕРЕЖЕНО:
- Форматування часу (format_time, format_time_range)
- Відкриття відео в потрібний момент
- Копіювання з форматованим часом
- Збереження у базі даних
- Безпечне управління помилками

🔧 ЩОБ ЗАСТОСУВАТИ У ВАШОМУ ПРОЕКТІ:
1. Замініть ваш sentence_widget.py на цю версію
2. Перевірте імпорти (особливо database_manager)
3. Протестуйте з вашими даними
4. За потреби адаптуйте методи ai_manager

📊 РЕЗУЛЬТАТ:
- Всі речення відображаються одразу
- Тільки граматичне пояснення
- Автоматично розширюване поле (3-15 рядків)
- Покращений UX без прокрутки
- Спрощена архітектура
"""