"""
Main Window - оновлена версія для інтеграції з новим SentenceWidget
Підтримує тільки граматичні пояснення з автоматично розширюваним полем
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import logging
import json
from pathlib import Path
from typing import Dict, List, Optional

# Імпорти наших модулів
from ai.enhanced_ai_manager import EnhancedAIManager
from data.data_manager import DataManager
from data.enhanced_video_processor import EnhancedVideoProcessor
from gui.enhanced_group_widget import EnhancedGroupWidget
from gui.notes_panel import NotesPanel
from utils.time_formatting import format_time, format_duration, format_time_range

# Імпорти наших модулів
from ai.ai_manager import AIManager
from data.data_manager import DataManager
from data.video_processor import VideoProcessor
from gui.sentence_widget import SentenceWidget
from gui.notes_panel import NotesPanel

# ФУНКЦІЇ ФОРМАТУВАННЯ ЧАСУ (НА ПОЧАТКУ, ЗОВНІ КЛАСУ)
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

def format_duration(duration_seconds: float, short: bool = False) -> str:
    """Форматує тривалість"""
    return format_time(duration_seconds, short)

def calculate_total_duration(sentences: List[Dict]) -> float:
    """Обчислює загальну тривалість всіх речень"""
    total = 0.0
    for sentence in sentences:
        if 'end_time' in sentence and 'start_time' in sentence:
            duration = sentence['end_time'] - sentence['start_time']
            total += duration
    return total

def get_video_time_stats(sentences: List[Dict]) -> Dict[str, str]:
    """Отримує статистику часу для відео"""
    if not sentences:
        return {
            'total_duration': '0 сек',
            'total_duration_short': '0с',
            'avg_sentence_duration': '0с',
            'shortest': '0с',
            'longest': '0с',
            'sentence_count': 0
        }
    
    durations = []
    for sentence in sentences:
        if 'end_time' in sentence and 'start_time' in sentence:
            duration = sentence['end_time'] - sentence['start_time']
            durations.append(duration)
    
    if not durations:
        return {
            'total_duration': '0 сек',
            'total_duration_short': '0с',
            'avg_sentence_duration': '0с',
            'shortest': '0с',
            'longest': '0с',
            'sentence_count': len(sentences)
        }
    
    total_duration = sum(durations)
    avg_duration = total_duration / len(durations)
    
    return {
        'total_duration': format_duration(total_duration),
        'total_duration_short': format_duration(total_duration, short=True),
        'avg_sentence_duration': format_duration(avg_duration, short=True),
        'shortest': format_duration(min(durations), short=True),
        'longest': format_duration(max(durations), short=True),
        'sentence_count': len(sentences)
    }


class MainWindow:
    """Головне вікно програми з підтримкою нового спрощеного SentenceWidget"""
    
    def __init__(self):
        """Ініціалізація головного вікна"""
        # Створюємо головне вікно
        self.root = tk.Tk()
        self.root.title("Game Learning - Вивчення англійської через ігрові відео")
        self.root.geometry("1400x900")
        self.root.minsize(1000, 700)
        
        # Налаштування логування
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Ініціалізація менеджерів
        self.init_managers()
        
        # Дані поточного стану
        self.current_video = None
        self.current_sentences = []
        self.sentence_widgets = []
        self.selected_sentence = None
        
        # Стан створення віджетів
        self.is_creating_widgets = False
        self.widgets_creation_cancelled = False
        
        # Створення інтерфейсу
        self.create_interface()
        
        # Завантаження даних
        self.load_initial_data()
    
    def init_managers(self):
        """Ініціалізує всі менеджери"""
        try:
            # AI Manager
            self.ai_manager = AIManager()
            
            # Data Manager
            self.data_manager = DataManager()
            
            # Video Processor
            self.video_processor = VideoProcessor()
            
            self.logger.info("Всі менеджери ініціалізовані успішно")
            
        except Exception as e:
            self.logger.error(f"Помилка ініціалізації менеджерів: {e}")
            messagebox.showerror("Критична помилка", 
                               f"Не вдалося ініціалізувати систему: {e}")
    
    def create_interface(self):
        """Створює інтерфейс програми"""
        # Меню
        self.create_menu()
        
        # Верхня панель з вибором відео
        self.create_top_panel()
        
        # Головна робоча область
        self.create_main_area()
        
        # Статус бар
        self.create_status_bar()
        
        # Налаштування стилів
        self.setup_styles()
    
    def create_menu(self):
        """Створює спрощене головне меню"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # Меню Файл
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Файл", menu=file_menu)
        file_menu.add_command(label="Додати відео...", command=self.add_video_file)
        file_menu.add_command(label="Обробити всі відео", command=self.process_all_videos)
        file_menu.add_separator()
        file_menu.add_command(label="Вихід", command=self.on_closing)
        
        # Меню AI (тільки граматика)
        ai_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="AI", menu=ai_menu)
        ai_menu.add_command(label="Генерувати граматику для всіх", command=self.generate_grammar_for_all)
        
        # Меню Допомога
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Допомога", menu=help_menu)
        help_menu.add_command(label="Про програму", command=self.simple_about)
    
    def create_top_panel(self):
        """Створює верхню панель з вибором відео"""
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Лейбл та комбобокс для вибору відео
        ttk.Label(top_frame, text="📹 Відео:", font=("Arial", 12)).pack(side=tk.LEFT, padx=(0, 10))
        
        self.video_var = tk.StringVar()
        self.video_combo = ttk.Combobox(
            top_frame, 
            textvariable=self.video_var, 
            state="readonly", 
            width=50,
            font=("Arial", 11)
        )
        self.video_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.video_combo.bind('<<ComboboxSelected>>', self.on_video_selected)
        
        # Кнопки управління (спрощені)
        buttons_frame = ttk.Frame(top_frame)
        buttons_frame.pack(side=tk.RIGHT)
        
        ttk.Button(buttons_frame, text="🔄 Оновити", 
                  command=self.refresh_videos).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(buttons_frame, text="⚙️ Обробити", 
                  command=self.process_current_video).pack(side=tk.LEFT, padx=2)
        
        # ОНОВЛЕНО: Тільки граматика
        ttk.Button(buttons_frame, text="📚 Граматика для всіх", 
                  command=self.generate_grammar_for_current_video).pack(side=tk.LEFT, padx=2)
        
        # Кнопка статистики
        ttk.Button(buttons_frame, text="📊 Статистика", 
                  command=self.show_video_statistics).pack(side=tk.LEFT, padx=2)
        
        # Кнопка скасування створення віджетів
        self.cancel_button = ttk.Button(buttons_frame, text="❌ Скасувати", 
                                      command=self.cancel_widget_creation, state=tk.DISABLED)
        self.cancel_button.pack(side=tk.LEFT, padx=2)
        
        # Індикатор стану AI
        self.ai_status_label = ttk.Label(top_frame, text="", font=("Arial", 9))
        self.ai_status_label.pack(side=tk.RIGHT, padx=(10, 0))
        
        # Оновлюємо статус AI
        self.update_ai_status()
    
    def create_main_area(self):
        """Створює головну робочу область"""
        # Основний контейнер
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Paned Window для розділення на ліву та праву частини
        self.paned_window = ttk.PanedWindow(main_container, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True)
        
        # Ліва частина - речення (70%)
        self.create_sentences_panel()
        
        # Права частина - нотатки (30%)
        self.create_notes_panel()
        
        # Встановлюємо початкові пропорції
        self.root.after(100, lambda: self.paned_window.sashpos(0, 980))
    
    def create_sentences_panel(self):
        """Створює панель з реченнями"""
        # Контейнер для речень
        sentences_frame = ttk.Frame(self.paned_window)
        self.paned_window.add(sentences_frame, weight=7)
        
        # Заголовок
        header_frame = ttk.Frame(sentences_frame)
        header_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.sentences_title = ttk.Label(
            header_frame, 
            text="📖 Речення (оберіть відео)", 
            font=("Arial", 14, "bold")
        )
        self.sentences_title.pack(side=tk.LEFT)
        
        # Статистика речень
        self.sentences_stats = ttk.Label(
            header_frame, 
            text="", 
            font=("Arial", 10)
        )
        self.sentences_stats.pack(side=tk.RIGHT)
        
        # Canvas з прокруткою для речень
        self.create_sentences_scroll_area(sentences_frame)
    
    def create_sentences_scroll_area(self, parent):
        """Створює область з прокруткою для речень"""
        # Canvas та Scrollbar
        self.sentences_canvas = tk.Canvas(parent, bg="white", highlightthickness=0)
        sentences_scrollbar = ttk.Scrollbar(parent, orient="vertical", 
                                          command=self.sentences_canvas.yview)
        
        self.sentences_scrollable_frame = ttk.Frame(self.sentences_canvas)
        
        # Налаштування прокрутки
        self.sentences_scrollable_frame.bind(
            "<Configure>",
            lambda e: self.sentences_canvas.configure(
                scrollregion=self.sentences_canvas.bbox("all")
            )
        )
        
        self.sentences_canvas.create_window(
            (0, 0), 
            window=self.sentences_scrollable_frame, 
            anchor="nw"
        )
        self.sentences_canvas.configure(yscrollcommand=sentences_scrollbar.set)
        
        # Прив'язка колеса миші
        self.sentences_canvas.bind_all("<MouseWheel>", self._on_sentences_mousewheel)
        
        # Пакування
        self.sentences_canvas.pack(side="left", fill="both", expand=True)
        sentences_scrollbar.pack(side="right", fill="y")
    
    def _on_sentences_mousewheel(self, event):
        """Обробка прокрутки мишкою для речень"""
        self.sentences_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    
    def create_notes_panel(self):
        """Створює панель нотаток"""
        # Контейнер для нотаток
        notes_frame = ttk.Frame(self.paned_window)
        self.paned_window.add(notes_frame, weight=3)
        
        # Створюємо NotesPanel
        self.notes_panel = NotesPanel(
            parent_frame=notes_frame,
            data_manager=self.data_manager,
            on_note_changed=self.on_note_changed
        )
        
        # Зберігаємо посилання
        self.notes_panel.main_window = self
    
    def display_sentences(self, sentences: List[Dict], filename: str):
        """Відображає речення з новим форматуванням часу"""
        try:
            self.logger.info(f"=== ПОЧАТОК ВІДОБРАЖЕННЯ РЕЧЕНЬ ===")
            self.logger.info(f"Кількість речень для відображення: {len(sentences)}")
            
            # Скасовуємо попереднє створення якщо воно триває
            if self.is_creating_widgets:
                self.cancel_widget_creation()
                # Чекаємо поки скасування завершиться
                self.root.after(100, lambda: self.display_sentences(sentences, filename))
                return
            
            # Очищаємо попередні речення
            self.clear_sentences()
            
            # Зберігаємо дані
            self.current_video = filename
            self.current_sentences = sentences
            
            # Обчислюємо статистику часу
            time_stats = get_video_time_stats(sentences)
            
            # Оновлюємо заголовок з тривалістю
            title_text = f"📖 {filename}"
            if time_stats['total_duration_short'] != '0с':
                title_text += f" • {time_stats['total_duration_short']}"
            
            self.sentences_title.config(text=title_text)
            
            # Оновлюємо статистику з детальною інформацією
            stats_parts = [f"{time_stats['sentence_count']} речень"]
            
            if time_stats['total_duration'] != '0 сек':
                stats_parts.append(f"⏱️ {time_stats['total_duration']}")
                stats_parts.append(f"📊 середнє: {time_stats['avg_sentence_duration']}")
                
                # Додаємо діапазон тривалості
                if time_stats['shortest'] != time_stats['longest']:
                    stats_parts.append(f"📏 {time_stats['shortest']} - {time_stats['longest']}")
            
            stats_text = " • ".join(stats_parts)
            self.sentences_stats.config(text=stats_text)
            
            self.logger.info(f"Заголовок оновлено: {filename}, статистика: {stats_text}")
            
            # Запускаємо батчеве створення віджетів
            self.create_widgets_in_batches(sentences, filename)
            
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"❌ КРИТИЧНА ПОМИЛКА відображення речень: {error_msg}")
            import traceback
            self.logger.error(f"Деталі помилки:\n{traceback.format_exc()}")
            self.status_var.set(f"Помилка: {error_msg}")
    
    def create_widgets_in_batches(self, sentences: List[Dict], filename: str, batch_size: int = 5):
        """Створює віджети порціями для уникнення рекурсії"""
        if self.is_creating_widgets:
            self.logger.warning("Створення віджетів вже в процесі")
            return
        
        self.is_creating_widgets = True
        self.widgets_creation_cancelled = False
        self.cancel_button.config(state=tk.NORMAL)
        
        total = len(sentences)
        current_index = 0
        
        # Показуємо прогрес
        self.show_progress_message(f"Створення віджетів: 0/{total}")
        
        def create_next_batch():
            nonlocal current_index
            
            # Перевірка на скасування
            if self.widgets_creation_cancelled:
                self.logger.info("Створення віджетів скасовано")
                self.finish_widget_creation(cancelled=True)
                return
            
            # Перевірка завершення
            if current_index >= total:
                self.logger.info(f"=== СТВОРЕНО {len(self.sentence_widgets)} ВІДЖЕТІВ ===")
                self.finish_widget_creation()
                return
            
            # Визначаємо межі батчу
            batch_end = min(current_index + batch_size, total)
            
            # Створюємо віджети в поточному батчі
            for i in range(current_index, batch_end):
                if self.widgets_creation_cancelled:
                    return
                
                try:
                    sentence = sentences[i]
                    self.logger.info(f"Створення речення {i+1}/{total}: {sentence['text'][:30]}...")
                    
                    # Перевіряємо структуру речення
                    required_fields = ['text', 'start_time', 'end_time']
                    missing_fields = [field for field in required_fields if field not in sentence]
                    
                    if missing_fields:
                        self.logger.error(f"Речення {i} має відсутні поля: {missing_fields}")
                        continue
                    
                    # ОНОВЛЕНО: Створюємо новий спрощений SentenceWidget
                    sentence_widget = SentenceWidget(
                        parent_frame=self.sentences_scrollable_frame,
                        sentence_data=sentence,
                        video_filename=filename,
                        sentence_index=i,
                        ai_manager=self.ai_manager,
                        data_manager=self.data_manager,
                        on_sentence_click=self.on_sentence_clicked
                    )
                    
                    self.sentence_widgets.append(sentence_widget)
                    self.logger.info(f"✅ SentenceWidget {i} створений успішно")
                    
                except Exception as widget_error:
                    self.logger.error(f"❌ Помилка створення SentenceWidget {i}: {widget_error}")
                    import traceback
                    self.logger.error(f"Деталі помилки:\n{traceback.format_exc()}")
                    continue
            
            # Оновлюємо прогрес
            current_index = batch_end
            progress_text = f"Створення віджетів: {current_index}/{total} ({current_index/total*100:.1f}%)"
            self.update_progress_message(progress_text)
            
            # Примусово оновлюємо інтерфейс
            self.sentences_canvas.update_idletasks()
            
            # Плануємо наступний батч з паузою
            self.root.after(100, create_next_batch)
        
        # Запускаємо перший батч
        self.root.after(10, create_next_batch)
    
    def finish_widget_creation(self, cancelled: bool = False):
        """Завершує створення віджетів"""
        try:
            self.is_creating_widgets = False
            self.cancel_button.config(state=tk.DISABLED)
            
            if cancelled:
                self.status_var.set("Створення віджетів скасовано")
                self.hide_progress_message()
                return
            
            # Ховаємо повідомлення прогресу
            self.hide_progress_message()
            
            # Примусово оновлюємо інтерфейс
            self.sentences_canvas.update_idletasks()
            
            # Прокрутка до початку
            self.sentences_canvas.yview_moveto(0)
            
            # Фінальне оновлення
            self.root.update_idletasks()
            
            total_widgets = len(self.sentence_widgets)
            self.status_var.set(f"Завантажено {total_widgets} речень")
            self.logger.info(f"=== ВІДОБРАЖЕННЯ ЗАВЕРШЕНО: {total_widgets} віджетів ===")
            
        except Exception as e:
            self.logger.error(f"Помилка завершення створення віджетів: {e}")
    
    def cancel_widget_creation(self):
        """Скасовує створення віджетів"""
        if self.is_creating_widgets:
            self.widgets_creation_cancelled = True
            self.logger.info("Запит на скасування створення віджетів")
    
    def show_progress_message(self, message: str):
        """Показує повідомлення прогресу"""
        if hasattr(self, 'progress_label'):
            self.progress_label.destroy()
        
        self.progress_label = ttk.Label(
            self.sentences_scrollable_frame,
            text=f"🔄 {message}",
            font=("Arial", 12, "bold"),
            background="#fff3cd"
        )
        self.progress_label.pack(pady=20)
        self.root.update_idletasks()
    
    def update_progress_message(self, message: str):
        """Оновлює повідомлення прогресу"""
        if hasattr(self, 'progress_label') and self.progress_label.winfo_exists():
            self.progress_label.config(text=f"🔄 {message}")
            self.root.update_idletasks()
    
    def hide_progress_message(self):
        """Ховає повідомлення прогресу"""
        if hasattr(self, 'progress_label'):
            try:
                self.progress_label.destroy()
                delattr(self, 'progress_label')
            except:
                pass
    
    def clear_sentences(self):
        """Очищає всі речення безпечно"""
        try:
            # Скасовуємо створення віджетів якщо воно триває
            if self.is_creating_widgets:
                self.cancel_widget_creation()
                # Даємо час на скасування
                self.root.after(50)
            
            self.logger.info(f"Очищення {len(self.sentence_widgets)} віджетів...")
            
            # Видаляємо віджети
            for i, widget in enumerate(self.sentence_widgets):
                try:
                    if hasattr(widget, 'main_frame') and widget.main_frame.winfo_exists():
                        widget.main_frame.destroy()
                        self.logger.debug(f"Віджет {i} видалений")
                except Exception as e:
                    self.logger.warning(f"Помилка видалення віджета {i}: {e}")
            
            self.sentence_widgets.clear()
            
            # Очищаємо батьківський фрейм
            for child in self.sentences_scrollable_frame.winfo_children():
                try:
                    child.destroy()
                except:
                    pass
            
            # Очищаємо дані
            self.current_sentences.clear()
            self.selected_sentence = None
            
            # Скидаємо прокрутку
            self.sentences_canvas.yview_moveto(0)
            
            self.logger.info("Очищення завершено")
            
        except Exception as e:
            self.logger.error(f"Помилка очищення: {e}")
    
    def refresh_videos(self):
        """Оновлює список відео з інформацією про тривалість"""
        try:
            # Отримуємо оброблені відео
            video_states = self.data_manager.get_all_video_states()
            processed_videos = [v for v in video_states if v['processing_completed']]
            
            # Створюємо список для комбобокса з покращеною інформацією
            video_options = []
            for video in processed_videos:
                filename = video['video_filename']
                sentences_count = video['sentences_extracted']
                
                # Намагаємося отримати тривалість відео
                try:
                    from processing.database_manager import DatabaseManager
                    db_manager = DatabaseManager()
                    videos = db_manager.get_all_videos()
                    video_data = next((v for v in videos if v['filename'] == filename), None)
                    
                    if video_data:
                        segments = db_manager.get_video_segments(video_data['id'])
                        sentences = self.video_processor.split_text_into_sentences(segments)
                        
                        if sentences:
                            total_duration = calculate_total_duration(sentences)
                            duration_text = format_duration(total_duration, short=True)
                            video_options.append(f"{filename} ({sentences_count} речень • {duration_text})")
                        else:
                            video_options.append(f"{filename} ({sentences_count} речень)")
                    else:
                        video_options.append(f"{filename} ({sentences_count} речень)")
                except Exception as e:
                    self.logger.debug(f"Не вдалося отримати тривалість для {filename}: {e}")
                    video_options.append(f"{filename} ({sentences_count} речень)")
            
            # Оновлюємо комбобокс
            self.video_combo['values'] = video_options
            
            if video_options and not self.current_video:
                self.video_combo.current(0)
                self.on_video_selected()
            
            self.logger.info(f"Завантажено {len(video_options)} відео")
            
        except Exception as e:
            self.logger.error(f"Помилка оновлення списку відео: {e}")
    
    def show_video_statistics(self):
        """Показує детальну статистику з новим форматуванням"""
        if not self.current_sentences:
            messagebox.showinfo("Статистика", "Немає завантажених речень")
            return
        
        try:
            time_stats = get_video_time_stats(self.current_sentences)
            
            # Додаткова статистика
            total_chars = sum(len(s.get('text', '')) for s in self.current_sentences)
            avg_chars = total_chars / len(self.current_sentences) if self.current_sentences else 0
            
            # Розподіл по тривалості
            durations = []
            for sentence in self.current_sentences:
                if 'end_time' in sentence and 'start_time' in sentence:
                    duration = sentence['end_time'] - sentence['start_time']
                    durations.append(duration)
            
            short_sentences = len([d for d in durations if d < 3])  # < 3 сек
            medium_sentences = len([d for d in durations if 3 <= d <= 10])  # 3-10 сек
            long_sentences = len([d for d in durations if d > 10])  # > 10 сек
            
            stats_text = f"""Статистика відео: {self.current_video}

📊 ЗАГАЛЬНА ІНФОРМАЦІЯ:
• Речень: {time_stats['sentence_count']}
• Загальна тривалість: {time_stats['total_duration']}
• Середня тривалість речення: {time_stats['avg_sentence_duration']}
• Найкоротше речення: {time_stats['shortest']}
• Найдовше речення: {time_stats['longest']}

📝 ТЕКСТОВА СТАТИСТИКА:
• Загальна кількість символів: {total_chars:,}
• Середня довжина речення: {avg_chars:.1f} символів

⏱️ РОЗПОДІЛ ЗА ТРИВАЛІСТЮ:
• Короткі (< 3 сек): {short_sentences} речень
• Середні (3-10 сек): {medium_sentences} речень  
• Довгі (> 10 сек): {long_sentences} речень

🎯 ЕФЕКТИВНІСТЬ:
• Символів/секунда: {total_chars/sum(durations):.1f} (швидкість мовлення)
• Речень/хвилина: {len(durations)/(sum(durations)/60):.1f}
"""
            
            # Створюємо вікно статистики
            stats_window = tk.Toplevel(self.root)
            stats_window.title(f"Статистика - {self.current_video}")
            stats_window.geometry("500x400")
            stats_window.resizable(True, True)
            
            # Текстове поле зі статистикою
            text_widget = tk.Text(stats_window, wrap=tk.WORD, padx=10, pady=10)
            text_widget.pack(fill=tk.BOTH, expand=True)
            
            text_widget.insert(tk.END, stats_text)
            text_widget.config(state=tk.DISABLED)
            
            # Кнопка закриття
            close_btn = ttk.Button(stats_window, text="Закрити", 
                                  command=stats_window.destroy)
            close_btn.pack(pady=10)
            
        except Exception as e:
            self.logger.error(f"Помилка показу статистики: {e}")
            messagebox.showerror("Помилка", f"Не вдалося показати статистику: {e}")
    
    def on_video_selected(self, event=None):
        """Обробляє вибір відео"""
        selected = self.video_var.get()
        if not selected:
            return
        
        try:
            # Витягуємо назву файлу з рядка
            filename = selected.split(' (')[0]
            
            self.status_var.set(f"Завантаження речень для {filename}...")
            
            # Завантажуємо речення в окремому потоці
            threading.Thread(target=self.load_sentences_for_video, 
                           args=(filename,), daemon=True).start()
            
        except Exception as e:
            self.logger.error(f"Помилка вибору відео: {e}")
            messagebox.showerror("Помилка", f"Не вдалося завантажити відео: {e}")
    
    def load_sentences_for_video(self, filename: str):
        """Завантажує речення для відео"""
        try:
            # Отримуємо дані з основної БД
            from processing.database_manager import DatabaseManager
            db_manager = DatabaseManager()
            
            # Знаходимо відео
            videos = db_manager.get_all_videos()
            video = next((v for v in videos if v['filename'] == filename), None)
            
            if not video:
                raise Exception(f"Відео {filename} не знайдено в БД")
            
            # Отримуємо сегменти
            segments = db_manager.get_video_segments(video['id'])
            
            # Розбиваємо на речення
            sentences = self.video_processor.split_text_into_sentences(segments)
            
            # Оновлюємо UI в головному потоці
            self.root.after(0, lambda: self.display_sentences(sentences, filename))
            
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Помилка завантаження речень: {error_msg}")
            self.root.after(0, lambda msg=error_msg: messagebox.showerror("Помилка", f"Не вдалося завантажити речення: {msg}"))
    
    def on_sentence_clicked(self, sentence_data: Dict, video_filename: str):
        """Обробляє клік по реченню"""
        self.selected_sentence = sentence_data
        
        # Передаємо контекст в панель нотаток
        self.notes_panel.set_sentence_context(sentence_data, video_filename)
        
        self.logger.debug(f"Вибрано речення: {sentence_data['text'][:50]}...")
    
    def on_note_changed(self):
        """Обробляє зміну нотатки"""
        # Тут можна додати додаткову логіку при зміні нотаток
        pass
    
    # ===============================
    # AI МЕТОДИ (ТІЛЬКИ ГРАМАТИКА)
    # ===============================
    
    def generate_grammar_for_all(self):
        """Генерує граматичні пояснення для всіх речень всіх відео"""
        if messagebox.askyesno("Підтвердження", 
                              "Згенерувати граматичні пояснення для всіх речень?\nЦе може зайняти дуже багато часу."):
            threading.Thread(target=self.generate_grammar_for_all_thread, daemon=True).start()
    
    def generate_grammar_for_all_thread(self):
        """Генерує граматику для всіх речень всіх відео в окремому потоці"""
        try:
            if not self.ai_manager.is_available():
                self.update_status("AI недоступний")
                return
            
            # Отримуємо всі оброблені відео
            video_states = self.data_manager.get_all_video_states()
            processed_videos = [v for v in video_states if v['processing_completed']]
            
            total_videos = len(processed_videos)
            total_sentences_processed = 0
            
            for video_idx, video in enumerate(processed_videos):
                filename = video['video_filename']
                self.update_status(f"Обробка відео {video_idx+1}/{total_videos}: {filename}")
                
                # Завантажуємо речення для відео
                from processing.database_manager import DatabaseManager
                db_manager = DatabaseManager()
                
                videos = db_manager.get_all_videos()
                video_data = next((v for v in videos if v['filename'] == filename), None)
                
                if video_data:
                    segments = db_manager.get_video_segments(video_data['id'])
                    sentences = self.video_processor.split_text_into_sentences(segments)
                    
                    for i, sentence in enumerate(sentences):
                        # Тільки граматика
                        grammar = self.ai_manager.explain_grammar(sentence['text'])
                        if grammar['success']:
                            self.data_manager.save_ai_response(
                                sentence_text=sentence['text'],
                                video_filename=filename,
                                start_time=sentence['start_time'],
                                end_time=sentence['end_time'],
                                response_type='grammar',
                                ai_response=grammar['result'],
                                ai_client='llama3.1'
                            )
                        
                        total_sentences_processed += 1
                        
                        # Невелика пауза між запитами
                        import time
                        time.sleep(1)
            
            self.update_status(f"Граматика згенерована для {total_sentences_processed} речень з {total_videos} відео")
            
        except Exception as e:
            self.logger.error(f"Помилка генерації граматики для всіх: {e}")
            self.update_status(f"Помилка: {e}")
    
    def generate_grammar_for_current_video(self):
        """Генерує граматику для поточного відео"""
        if not self.current_video:
            messagebox.showwarning("Попередження", "Оберіть відео")
            return
        
        if messagebox.askyesno("Підтвердження", 
                              f"Згенерувати граматичні пояснення для всіх речень у {self.current_video}?"):
            threading.Thread(target=self.generate_grammar_for_current_video_thread, daemon=True).start()
    
    def generate_grammar_for_current_video_thread(self):
        """Генерує граматику для поточного відео в окремому потоці"""
        try:
            if not self.ai_manager.is_available():
                self.update_status("AI недоступний")
                return
            
            total_sentences = len(self.current_sentences)
            
            for i, sentence in enumerate(self.current_sentences):
                self.update_status(f"Генерація граматики {i+1}/{total_sentences}...")
                
                # Тільки граматика
                grammar = self.ai_manager.explain_grammar(sentence['text'])
                if grammar['success']:
                    self.data_manager.save_ai_response(
                        sentence_text=sentence['text'],
                        video_filename=self.current_video,
                        start_time=sentence['start_time'],
                        end_time=sentence['end_time'],
                        response_type='grammar',
                        ai_response=grammar['result'],
                        ai_client='llama3.1'
                    )
                
                # Невелика пауза між запитами
                import time
                time.sleep(1)
            
            self.update_status(f"Граматика згенерована для {total_sentences} речень")
            
        except Exception as e:
            self.logger.error(f"Помилка генерації граматики: {e}")
            self.update_status(f"Помилка: {e}")
    
    # ===============================
    # УТИЛІТАРНІ МЕТОДИ
    # ===============================
    
    def run(self):
        """Запускає головний цикл програми"""
        # Встановлюємо обробник закриття
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()
    
    def create_status_bar(self):
        """Створює статус бар"""
        status_frame = ttk.Frame(self.root)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Основний статус
        self.status_var = tk.StringVar()
        self.status_var.set("Готово")
        
        self.status_label = ttk.Label(
            status_frame, 
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor=tk.W
        )
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2, pady=2)
        
        # Прогрес бар (прихований за замовчуванням)
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            status_frame,
            variable=self.progress_var,
            length=200
        )
        # НЕ пакуємо поки не потрібен
    
    def setup_styles(self):
        """Налаштовує стилі інтерфейсу"""
        style = ttk.Style()
        
        # Використовуємо сучасну тему
        try:
            style.theme_use('vista')  # Windows
        except:
            try:
                style.theme_use('clam')  # Кроссплатформна
            except:
                pass
        
        # Кастомні стилі
        style.configure("Title.TLabel", font=("Arial", 16, "bold"))
        style.configure("Header.TLabel", font=("Arial", 12, "bold"))
    
    def load_initial_data(self):
        """Завантажує початкові дані"""
        try:
            self.status_var.set("Завантаження...")
            
            # Автоматично обробляємо нові відео
            threading.Thread(target=self.auto_process_videos, daemon=True).start()
            
            # Завантажуємо список відео
            self.refresh_videos()
            
        except Exception as e:
            self.logger.error(f"Помилка завантаження початкових даних: {e}")
            self.status_var.set(f"Помилка: {e}")
    
    def auto_process_videos(self):
        """Автоматично обробляє нові/змінені відео"""
        try:
            self.update_status("Перевірка нових відео...")
            
            # Обробляємо тільки нові/змінені відео
            result = self.video_processor.process_all_videos(force_reprocess=False)
            
            if result['stats']['videos_processed'] > 0:
                message = f"Оброблено {result['stats']['videos_processed']} нових відео"
                self.root.after(0, lambda: self.status_var.set(message))
                self.root.after(0, self.refresh_videos)
            else:
                self.root.after(0, lambda: self.status_var.set("Готово"))
                
        except Exception as e:
            self.logger.error(f"Помилка автообробки відео: {e}")
            self.root.after(0, lambda: self.status_var.set("Готово"))
    
    def update_status(self, message: str):
        """Оновлює статус"""
        self.root.after(0, lambda: self.status_var.set(message))
    
    def update_ai_status(self):
        """Оновлює статус AI"""
        try:
            if self.ai_manager.is_available():
                status = self.ai_manager.get_status()
                model = status.get('model', 'unknown')
                self.ai_status_label.config(text=f"🤖 AI: {model}", foreground="green")
            else:
                self.ai_status_label.config(text="🤖 AI: Недоступний", foreground="red")
        except Exception as e:
            self.ai_status_label.config(text="🤖 AI: Помилка", foreground="red")
    
    def on_closing(self):
        """Безпечне закриття програми"""
        try:
            self.logger.info("Закриття програми...")
            
            # Скасовуємо створення віджетів
            if self.is_creating_widgets:
                self.widgets_creation_cancelled = True
            
            # Очищаємо віджети
            self.clear_sentences()
            
            # Закриваємо вікно
            self.root.quit()
            self.root.destroy()
            
        except Exception as e:
            self.logger.error(f"Помилка при закритті: {e}")
            # Аварійне закриття
            try:
                self.root.destroy()
            except:
                pass
    
    # ===============================
    # ФАЙЛОВІ ОПЕРАЦІЇ
    # ===============================
    
    def add_video_file(self):
        """Додає новий відео файл"""
        file_path = filedialog.askopenfilename(
            title="Виберіть відео файл",
            filetypes=[
                ("Відео файли", "*.mkv *.mp4 *.avi *.mov"),
                ("MKV файли", "*.mkv"),
                ("MP4 файли", "*.mp4"),
                ("Всі файли", "*.*")
            ]
        )
        
        if file_path:
            # Копіюємо файл в папку videos/ та обробляємо
            threading.Thread(target=self.add_and_process_video, 
                           args=(file_path,), daemon=True).start()
    
    def add_and_process_video(self, file_path: str):
        """Додає та обробляє новий відео файл"""
        try:
            import shutil
            from datetime import datetime
            
            self.update_status("Копіювання відео файлу...")
            
            # Копіюємо файл
            videos_dir = Path("videos")
            videos_dir.mkdir(exist_ok=True)
            
            filename = Path(file_path).name
            destination = videos_dir / filename
            
            shutil.copy2(file_path, destination)
            
            # Обробляємо
            self.update_status("Обробка нового відео...")
            
            video_info = {
                "filename": filename,
                "filepath": str(destination),
                "size": destination.stat().st_size,
                "modified": datetime.fromtimestamp(destination.stat().st_mtime),
                "extension": destination.suffix.lower()
            }
            
            result = self.video_processor.process_single_video(video_info)
            
            if result['success']:
                self.update_status(f"Відео оброблено: {result['sentences_count']} речень")
                self.root.after(0, self.refresh_videos)
            else:
                self.update_status(f"Помилка обробки: {result['error']}")
                
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Помилка додавання відео: {error_msg}")
            self.update_status(f"Помилка: {error_msg}")
    
    def process_all_videos(self):
        """Обробляє всі відео файли"""
        if messagebox.askyesno("Підтвердження", 
                              "Перепроцесувати всі відео файли?\nЦе може зайняти багато часу."):
            threading.Thread(target=self.process_all_videos_thread, daemon=True).start()
    
    def process_all_videos_thread(self):
        """Обробляє всі відео в окремому потоці"""
        try:
            self.update_status("Обробка всіх відео...")
            
            # Показуємо прогрес бар
            self.root.after(0, lambda: self.progress_bar.pack(side=tk.RIGHT, padx=10, pady=2))
            
            result = self.video_processor.process_all_videos(force_reprocess=True)
            
            # Приховуємо прогрес бар
            self.root.after(0, lambda: self.progress_bar.pack_forget())
            
            message = f"Оброблено {result['stats']['videos_processed']} відео"
            self.update_status(message)
            self.root.after(0, self.refresh_videos)
            
        except Exception as e:
            self.logger.error(f"Помилка обробки всіх відео: {e}")
            self.update_status(f"Помилка: {e}")
            self.root.after(0, lambda: self.progress_bar.pack_forget())
    
    def process_current_video(self):
        """Обробляє поточне відео"""
        if self.current_video:
            threading.Thread(target=self.process_current_video_thread, daemon=True).start()
    
    def process_current_video_thread(self):
        """Обробляє поточне відео в окремому потоці"""
        try:
            from datetime import datetime
            
            self.update_status(f"Переобробка {self.current_video}...")
            
            # Знаходимо файл
            videos_dir = Path("videos")
            video_path = videos_dir / self.current_video
            
            if video_path.exists():
                video_info = {
                    "filename": self.current_video,
                    "filepath": str(video_path),
                    "size": video_path.stat().st_size,
                    "modified": datetime.fromtimestamp(video_path.stat().st_mtime),
                    "extension": video_path.suffix.lower()
                }
                
                result = self.video_processor.process_single_video(video_info)
                
                if result['success']:
                    self.update_status(f"Переобробка завершена: {result['sentences_count']} речень")
                    # Перезавантажуємо речення
                    self.root.after(0, lambda: self.load_sentences_for_video(self.current_video))
                else:
                    self.update_status(f"Помилка переобробки: {result['error']}")
            else:
                self.update_status("Файл відео не знайдено")
                
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Помилка переобробки відео: {error_msg}")
            self.update_status(f"Помилка: {error_msg}")
    
    def simple_about(self):
        """Простий діалог про програму"""
        messagebox.showinfo("Про програму", 
                           "Game Learning v2.0\n\nПрограма для вивчення англійської мови\nчерез ігрові відео з AI підтримкою.\n\n🚀 Українська розробка!")


# ==============================================================
# ТЕСТУВАННЯ ТА ЗАПУСК
# ==============================================================

    def on_silence_threshold_changed(self):
        """Обробляє зміну порогу тиші"""
        new_threshold = self.silence_var.get()
        if new_threshold != self.silence_threshold:
            self.silence_threshold = new_threshold
            self.video_processor.segment_grouper.silence_threshold = new_threshold

            # Оновлюємо інформацію про групування
            if self.current_groups:
                threshold_text = f"💡 Групи розділені паузами ≥{self.silence_threshold}с"
                self.grouping_info.config(text=threshold_text + " (змініть відео для застосування)")

    # ===============================
    # ФІЛЬТРИ ТА СОРТУВАННЯ ГРУП
    # ===============================

    def apply_groups_filter(self, event=None):
        """Застосовує фільтр до груп"""
        filter_type = self.filter_var.get()

        if filter_type == "Всі групи":
            filtered_groups = self.current_groups
        elif filter_type == "Легкі":
            filtered_groups = [g for g in self.current_groups
                               if g.get('difficulty_level', '').startswith('beginner')]
        elif filter_type == "Середні":
            filtered_groups = [g for g in self.current_groups
                               if g.get('difficulty_level', '').startswith('intermediate')]
        elif filter_type == "Складні":
            filtered_groups = [g for g in self.current_groups
                               if g.get('difficulty_level', '').startswith('advanced')]
        elif filter_type == "З кадрами":
            filtered_groups = [g for g in self.current_groups
                               if len(g.get('frames', [])) > 0]
        elif filter_type == "Без кадрів":
            filtered_groups = [g for g in self.current_groups
                               if len(g.get('frames', [])) == 0]
        else:
            filtered_groups = self.current_groups

        # Перевідображаємо відфільтровані групи
        if filtered_groups != self.current_groups:
            self.display_filtered_groups(filtered_groups)

    def apply_groups_sorting(self, event=None):
        """Застосовує сортування до груп"""
        sort_type = self.sort_var.get()

        if sort_type == "За часом":
            sorted_groups = sorted(self.current_groups,
                                   key=lambda g: g.get('group_start_time', 0))
        elif sort_type == "За складністю":
            difficulty_order = {'beginner': 1, 'intermediate': 2, 'advanced': 3}
            sorted_groups = sorted(self.current_groups,
                                   key=lambda g: difficulty_order.get(
                                       g.get('difficulty_level', 'intermediate').split()[0], 2))
        elif sort_type == "За довжиною":
            sorted_groups = sorted(self.current_groups,
                                   key=lambda g: g.get('group_duration', 0), reverse=True)
        elif sort_type == "За кількістю слів":
            sorted_groups = sorted(self.current_groups,
                                   key=lambda g: g.get('word_count', 0), reverse=True)
        else:
            sorted_groups = self.current_groups

        # Перевідображаємо відсортовані групи
        if sorted_groups != self.current_groups:
            self.display_filtered_groups(sorted_groups)

    def display_filtered_groups(self, groups: List[Dict]):
        """Відображає відфільтровані/відсортовані групи"""
        # Очищаємо поточні віджети
        self.clear_groups()

        # Відображаємо нові групи
        self.create_group_widgets_in_batches(groups, self.current_video)

    # ===============================
    # AI МЕТОДИ ДЛЯ ГРУП
    # ===============================

    def generate_ai_for_current_video(self):
        """Генерує всі типи AI аналізу для поточного відео"""
        if not self.current_video:
            messagebox.showwarning("Попередження", "Оберіть відео")
            return

        if messagebox.askyesno("Підтвердження",
                               f"Згенерувати всі типи AI аналізу для груп у {self.current_video}?\n"
                               f"Це включає: всебічний аналіз, контекст, лексику та вимову."):
            threading.Thread(target=self.generate_all_ai_for_current_video_thread, daemon=True).start()

    def generate_all_ai_for_current_video_thread(self):
        """Генерує всі типи AI аналізу в окремому потоці"""
        try:
            if not self.ai_manager.is_available():
                self.update_status("AI недоступний")
                return

            total_groups = len(self.current_groups)
            analysis_types = ['comprehensive', 'contextual', 'vocabulary', 'pronunciation']
            total_operations = total_groups * len(analysis_types)
            current_operation = 0

            for group_idx, group in enumerate(self.current_groups):
                text = group['combined_text']

                self.update_status(f"Обробка групи {group_idx + 1}/{total_groups}...")

                # Всебічний аналіз
                comprehensive = self.ai_manager.analyze_sentence_comprehensive(text)
                current_operation += 1
                self.update_status(f"AI аналіз {current_operation}/{total_operations}: всебічний")

                # Контекстуальний аналіз
                context = self._prepare_group_context(group, group_idx)
                contextual = self.ai_manager.explain_in_context(text, context)
                current_operation += 1
                self.update_status(f"AI аналіз {current_operation}/{total_operations}: контекст")

                # Лексичний аналіз
                vocabulary = self.ai_manager.analyze_vocabulary(text)
                current_operation += 1
                self.update_status(f"AI аналіз {current_operation}/{total_operations}: лексика")

                # Фонетичний аналіз
                pronunciation = self.ai_manager.get_pronunciation_guide(text)
                current_operation += 1
                self.update_status(f"AI аналіз {current_operation}/{total_operations}: вимова")

                # Збереження результатів в БД
                self._save_group_ai_analysis(group, comprehensive, contextual, vocabulary, pronunciation)

                # Невелика пауза між групами
                import time
                time.sleep(0.5)

            self.update_status(f"AI аналіз завершено для {total_groups} груп")

        except Exception as e:
            self.logger.error(f"Помилка генерації AI аналізу: {e}")
            self.update_status(f"Помилка AI аналізу: {e}")

    def _prepare_group_context(self, group: Dict, group_index: int) -> Dict:
        """Підготовує контекст для групи"""
        context = {
            "video_description": f"Група {group_index + 1} з відео {self.current_video}",
            "group_duration": group.get('group_duration', 0),
            "word_count": group.get('word_count', 0),
            "difficulty_level": group.get('difficulty_level', 'intermediate')
        }

        # Додаємо попередню та наступну групи якщо є
        if group_index > 0:
            context["previous_sentence"] = self.current_groups[group_index - 1].get('combined_text', '')

        if group_index < len(self.current_groups) - 1:
            context["next_sentence"] = self.current_groups[group_index + 1].get('combined_text', '')

        return context

    def _save_group_ai_analysis(self, group: Dict, comprehensive: Dict,
                                contextual: Dict, vocabulary: Dict, pronunciation: Dict):
        """Зберігає AI аналіз групи в базі даних"""
        try:
            # Зберігаємо кожний тип аналізу окремо
            group_text = group['combined_text']
            start_time = group['group_start_time']
            end_time = group['group_end_time']

            # Всебічний аналіз
            if comprehensive.get('success'):
                self.data_manager.save_ai_response(
                    sentence_text=group_text,
                    video_filename=self.current_video,
                    start_time=start_time,
                    end_time=end_time,
                    response_type='comprehensive',
                    ai_response=json.dumps(comprehensive.get('analysis', {})),
                    ai_client='llama3.1'
                )

            # Контекстуальний аналіз
            if contextual.get('success'):
                self.data_manager.save_ai_response(
                    sentence_text=group_text,
                    video_filename=self.current_video,
                    start_time=start_time,
                    end_time=end_time,
                    response_type='contextual',
                    ai_response=contextual.get('explanation', ''),
                    ai_client='llama3.1'
                )

            # Лексичний аналіз
            if vocabulary.get('success'):
                self.data_manager.save_ai_response(
                    sentence_text=group_text,
                    video_filename=self.current_video,
                    start_time=start_time,
                    end_time=end_time,
                    response_type='vocabulary',
                    ai_response=vocabulary.get('vocabulary_analysis', ''),
                    ai_client='llama3.1'
                )

            # Фонетичний аналіз
            if pronunciation.get('success'):
                self.data_manager.save_ai_response(
                    sentence_text=group_text,
                    video_filename=self.current_video,
                    start_time=start_time,
                    end_time=end_time,
                    response_type='pronunciation',
                    ai_response=pronunciation.get('pronunciation_guide', ''),
                    ai_client='llama3.1'
                )

        except Exception as e:
            self.logger.error(f"Помилка збереження AI аналізу групи: {e}")

    # Окремі методи для генерації конкретних типів аналізу
    def generate_comprehensive_for_all(self):
        """Генерує всебічний аналіз для всіх груп"""
        self._generate_specific_ai_analysis('comprehensive')

    def generate_contextual_for_all(self):
        """Генерує контекстуальні пояснення для всіх груп"""
        self._generate_specific_ai_analysis('contextual')

    def generate_vocabulary_for_all(self):
        """Генерує аналіз лексики для всіх груп"""
        self._generate_specific_ai_analysis('vocabulary')

    def generate_pronunciation_for_all(self):
        """Генерує інструкції з вимови для всіх груп"""
        self._generate_specific_ai_analysis('pronunciation')

    def _generate_specific_ai_analysis(self, analysis_type: str):
        """Генерує конкретний тип AI аналізу"""
        if not self.current_video:
            messagebox.showwarning("Попередження", "Оберіть відео")
            return

        type_names = {
            'comprehensive': 'всебічний аналіз',
            'contextual': 'контекстуальні пояснення',
            'vocabulary': 'аналіз лексики',
            'pronunciation': 'інструкції з вимови'
        }

        type_name = type_names.get(analysis_type, analysis_type)

        if messagebox.askyesno("Підтвердження",
                               f"Згенерувати {type_name} для всіх груп у {self.current_video}?"):
            threading.Thread(target=self._generate_specific_ai_thread,
                             args=(analysis_type,), daemon=True).start()

    def _generate_specific_ai_thread(self, analysis_type: str):
        """Генерує конкретний тип аналізу в окремому потоці"""
        try:
            if not self.ai_manager.is_available():
                self.update_status("AI недоступний")
                return

            total_groups = len(self.current_groups)

            for group_idx, group in enumerate(self.current_groups):
                self.update_status(f"Генерація {analysis_type} {group_idx + 1}/{total_groups}...")

                text = group['combined_text']
                result = None

                # Викликаємо відповідний метод AI
                if analysis_type == 'comprehensive':
                    result = self.ai_manager.analyze_sentence_comprehensive(text)
                elif analysis_type == 'contextual':
                    context = self._prepare_group_context(group, group_idx)
                    result = self.ai_manager.explain_in_context(text, context)
                elif analysis_type == 'vocabulary':
                    result = self.ai_manager.analyze_vocabulary(text)
                elif analysis_type == 'pronunciation':
                    result = self.ai_manager.get_pronunciation_guide(text)

                # Зберігаємо результат
                if result and result.get('success'):
                    self._save_single_ai_analysis(group, analysis_type, result)

                # Пауза між запитами
                import time
                time.sleep(1)

            self.update_status(f"Генерація {analysis_type} завершена для {total_groups} груп")

        except Exception as e:
            self.logger.error(f"Помилка генерації {analysis_type}: {e}")
            self.update_status(f"Помилка генерації {analysis_type}: {e}")

    def _save_single_ai_analysis(self, group: Dict, analysis_type: str, result: Dict):
        """Зберігає одиночний AI аналіз"""
        try:
            group_text = group['combined_text']
            start_time = group['group_start_time']
            end_time = group['group_end_time']

            # Визначаємо що зберігати в залежності від типу
            if analysis_type == 'comprehensive':
                ai_response = json.dumps(result.get('analysis', {}))
            elif analysis_type == 'contextual':
                ai_response = result.get('explanation', '')
            elif analysis_type == 'vocabulary':
                ai_response = result.get('vocabulary_analysis', '')
            elif analysis_type == 'pronunciation':
                ai_response = result.get('pronunciation_guide', '')
            else:
                ai_response = str(result)

            self.data_manager.save_ai_response(
                sentence_text=group_text,
                video_filename=self.current_video,
                start_time=start_time,
                end_time=end_time,
                response_type=analysis_type,
                ai_response=ai_response,
                ai_client='llama3.1'
            )

        except Exception as e:
            self.logger.error(f"Помилка збереження {analysis_type} аналізу: {e}")

    # ===============================
    # ВІДЕО ТА КАДРИ
    # ===============================

    def extract_frames_for_current(self):
        """Витягує кадри для поточного відео"""
        if not self.current_video:
            messagebox.showwarning("Попередження", "Оберіть відео")
            return

        if messagebox.askyesno("Підтвердження",
                               f"Витягти додаткові кадри для {self.current_video}?"):
            threading.Thread(target=self.extract_frames_thread, daemon=True).start()

    def extract_frames_thread(self):
        """Витягує кадри в окремому потоці"""
        try:
            self.update_status("Витягування кадрів...")

            # Знаходимо відео файл
            video_path = f"videos/{self.current_video}"

            # Витягуємо кадри для кожної групи
            all_frames = []
            for group in self.current_groups:
                segments = group.get('segments', [])
                frames = self.video_processor.frame_extractor.extract_key_frames(
                    video_path, segments, max_frames_per_segment=5
                )
                all_frames.extend(frames)

            self.update_status(f"Витягнуто {len(all_frames)} кадрів")

        except Exception as e:
            self.logger.error(f"Помилка витягування кадрів: {e}")
            self.update_status(f"Помилка витягування кадрів: {e}")

    def analyze_frames_for_current(self):
        """Аналізує кадри для поточного відео"""
        if not self.current_video:
            messagebox.showwarning("Попередження", "Оберіть відео")
            return

        messagebox.showinfo("Інформація",
                            "Функція аналізу кадрів буде додана в наступних версіях.\n"
                            "Поки що доступний базовий аналіз (яскравість, складність).")

    # ===============================
    # СТАТИСТИКА ТА ЗВІТИ
    # ===============================

    def show_video_statistics(self):
        """Показує детальну статистику відео з групами"""
        if not self.current_groups:
            messagebox.showinfo("Статистика", "Немає завантажених груп")
            return

        try:
            stats = self.calculate_detailed_video_statistics()

            # Створюємо вікно статистики
            stats_window = tk.Toplevel(self.root)
            stats_window.title(f"Статистика - {self.current_video}")
            stats_window.geometry("700x600")
            stats_window.resizable(True, True)

            # Створюємо Notebook для різних типів статистики
            notebook = ttk.Notebook(stats_window)
            notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Вкладка "Загальна статистика"
            general_tab = ttk.Frame(notebook)
            notebook.add(general_tab, text="Загальна")

            general_text = tk.Text(general_tab, wrap=tk.WORD, padx=10, pady=10)
            general_text.pack(fill=tk.BOTH, expand=True)
            general_text.insert(tk.END, stats['general_stats'])
            general_text.config(state=tk.DISABLED)

            # Вкладка "Групи"
            groups_tab = ttk.Frame(notebook)
            notebook.add(groups_tab, text="Групи")

            groups_text = tk.Text(groups_tab, wrap=tk.WORD, padx=10, pady=10)
            groups_text.pack(fill=tk.BOTH, expand=True)
            groups_text.insert(tk.END, stats['groups_stats'])
            groups_text.config(state=tk.DISABLED)

            # Вкладка "Кадри"
            frames_tab = ttk.Frame(notebook)
            notebook.add(frames_tab, text="Кадри")

            frames_text = tk.Text(frames_tab, wrap=tk.WORD, padx=10, pady=10)
            frames_text.pack(fill=tk.BOTH, expand=True)
            frames_text.insert(tk.END, stats['frames_stats'])
            frames_text.config(state=tk.DISABLED)

            # Кнопка закриття
            close_btn = ttk.Button(stats_window, text="Закрити",
                                   command=stats_window.destroy)
            close_btn.pack(pady=10)

        except Exception as e:
            self.logger.error(f"Помилка показу статистики: {e}")
            messagebox.showerror("Помилка", f"Не вдалося показати статистику: {e}")

    def calculate_detailed_video_statistics(self) -> Dict:
        """Обчислює детальну статистику відео"""
        # Загальна статистика
        total_groups = len(self.current_groups)
        total_duration = sum(g.get('group_duration', 0) for g in self.current_groups)
        total_words = sum(g.get('word_count', 0) for g in self.current_groups)
        total_frames = sum(len(g.get('frames', [])) for g in self.current_groups)

        # Статистика по складності
        difficulty_counts = {}
        for group in self.current_groups:
            difficulty = group.get('difficulty_level', 'intermediate').split()[0]
            difficulty_counts[difficulty] = difficulty_counts.get(difficulty, 0) + 1

        # Статистика по тривалості груп
        durations = [g.get('group_duration', 0) for g in self.current_groups]
        avg_duration = sum(durations) / len(durations) if durations else 0
        min_duration = min(durations) if durations else 0
        max_duration = max(durations) if durations else 0

        # Формуємо текст статистики
        general_stats = f"""Статистика відео: {self.current_video}

📊 ЗАГАЛЬНА ІНФОРМАЦІЯ:
• Груп: {total_groups}
• Загальна тривалість: {format_duration(total_duration)}
• Середня тривалість групи: {format_duration(avg_duration)}
• Найкоротша група: {format_duration(min_duration)}
• Найдовша група: {format_duration(max_duration)}
• Поріг тиші: {self.silence_threshold} сек

📝 ТЕКСТОВА СТАТИСТИКА:
• Загальна кількість слів: {total_words:,}
• Середня кількість слів на групу: {total_words / total_groups:.1f}
• Слів за хвилину: {total_words / (total_duration / 60):.1f}

📊 РОЗПОДІЛ ЗА СКЛАДНІСТЮ:"""

        for difficulty, count in difficulty_counts.items():
            percentage = (count / total_groups) * 100
            general_stats += f"\n• {difficulty.title()}: {count} груп ({percentage:.1f}%)"

        # Статистика груп
        groups_stats = "ДЕТАЛЬНА ІНФОРМАЦІЯ ПРО ГРУПИ:\n\n"
        for i, group in enumerate(self.current_groups):
            start_time = format_time(group.get('group_start_time', 0))
            duration = format_duration(group.get('group_duration', 0))
            words = group.get('word_count', 0)
            frames_count = len(group.get('frames', []))
            difficulty = group.get('difficulty_level', 'intermediate')

            groups_stats += f"📦 Група {i + 1}:\n"
            groups_stats += f"   ⏰ Час: {start_time}, тривалість: {duration}\n"
            groups_stats += f"   📝 Слів: {words}, кадрів: {frames_count}\n"
            groups_stats += f"   🎯 Складність: {difficulty}\n"
            groups_stats += f"   📄 Текст: {group.get('combined_text', '')[:100]}...\n\n"

        # Статистика кадрів
        frames_stats = f"СТАТИСТИКА КАДРІВ:\n\n"
        frames_stats += f"• Загальна кількість кадрів: {total_frames}\n"
        frames_stats += f"• Середня кількість кадрів на групу: {total_frames / total_groups:.1f}\n"
        frames_stats += f"• Груп з кадрами: {len([g for g in self.current_groups if len(g.get('frames', [])) > 0])}\n"
        frames_stats += f"• Груп без кадрів: {len([g for g in self.current_groups if len(g.get('frames', [])) == 0])}\n\n"

        if total_frames > 0:
            frames_stats += "ДЕТАЛЬНА ІНФОРМАЦІЯ ПРО КАДРИ:\n\n"
            for i, group in enumerate(self.current_groups):
                frames = group.get('frames', [])
                if frames:
                    frames_stats += f"📦 Група {i + 1}: {len(frames)} кадрів\n"
                    for j, frame in enumerate(frames):
                        timestamp = format_time(frame.get('timestamp', 0))
                        frames_stats += f"   🖼️ Кадр {j + 1}: {timestamp}\n"
                    frames_stats += "\n"

        return {
            'general_stats': general_stats,
            'groups_stats': groups_stats,
            'frames_stats': frames_stats
        }

    def show_groups_statistics(self):
        """Показує статистику груп по всіх відео"""
        try:
            # Отримуємо статистику з video processor
            stats = self.video_processor.get_processing_statistics()

            stats_text = f"""СТАТИСТИКА ГРУПУВАННЯ:

📊 ЗАГАЛЬНА СТАТИСТИКА:
• Відео оброблено: {stats.get('videos_processed', 0)}
• Груп створено: {stats.get('groups_created', 0)}
• Кадрів витягнуто: {stats.get('frames_extracted', 0)}
• Час обробки: {stats.get('processing_time', 0):.1f} сек

⚙️ НАЛАШТУВАННЯ:
• Поточний поріг тиші: {self.silence_threshold} сек
• Підтримувані формати: {', '.join(self.video_processor.supported_formats)}

💡 РЕКОМЕНДАЦІЇ:
• Збільшуйте поріг тиші для меншої кількості довших груп
• Зменшуйте поріг тиші для більшої кількості коротших груп
• Оптимальний діапазон: 3-8 секунд"""

            messagebox.showinfo("Статистика групування", stats_text)

        except Exception as e:
            self.logger.error(f"Помилка показу статистики груп: {e}")
            messagebox.showerror("Помилка", f"Не вдалося показати статистику: {e}")

    # ===============================
    # КОНФІГУРАЦІЯ ТА НАЛАШТУВАННЯ
    # ===============================

    def configure_grouping(self):
        """Відкриває діалог налаштування групування"""
        config_window = tk.Toplevel(self.root)
        config_window.title("Налаштування групування")
        config_window.geometry("400x300")
        config_window.resizable(False, False)

        # Поріг тиші
        ttk.Label(config_window, text="Поріг тиші (секунди):").pack(pady=10)

        silence_var = tk.DoubleVar(value=self.silence_threshold)
        silence_scale = ttk.Scale(config_window, from_=1.0, to=15.0,
                                  variable=silence_var, orient=tk.HORIZONTAL)
        silence_scale.pack(fill=tk.X, padx=20, pady=5)

        silence_label = ttk.Label(config_window, text=f"{self.silence_threshold:.1f} сек")
        silence_label.pack()

        def update_silence_label(val):
            silence_label.config(text=f"{float(val):.1f} сек")

        silence_scale.config(command=update_silence_label)

        # Кнопки
        buttons_frame = ttk.Frame(config_window)
        buttons_frame.pack(pady=20)

        def apply_settings():
            self.silence_threshold = silence_var.get()
            self.silence_var.set(self.silence_threshold)
            self.video_processor.segment_grouper.silence_threshold = self.silence_threshold
            messagebox.showinfo("Успіх", "Налаштування збережені")
            config_window.destroy()

        ttk.Button(buttons_frame, text="Застосувати", command=apply_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Скасувати", command=config_window.destroy).pack(side=tk.LEFT, padx=5)

    def configure_ai(self):
        """Відкриває діалог налаштування AI"""
        config_window = tk.Toplevel(self.root)
        config_window.title("Налаштування AI")
        config_window.geometry("500x400")

        # Створюємо notebook для різних налаштувань
        notebook = ttk.Notebook(config_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Вкладка "Загальні"
        general_tab = ttk.Frame(notebook)
        notebook.add(general_tab, text="Загальні")

        # Статус AI
        status = self.ai_manager.get_enhanced_status()
        status_text = f"""Статус AI: {'✅ Доступний' if status['available'] else '❌ Недоступний'}
Модель: {status.get('model', 'Невідома')}
Рівень користувача: {status.get('user_level', 'intermediate')}
Мова навчання: {status.get('target_language', 'english')}"""

        ttk.Label(general_tab, text=status_text, justify=tk.LEFT).pack(pady=10)

        # Рівень користувача
        ttk.Label(general_tab, text="Рівень англійської:").pack(anchor=tk.W, padx=10)
        level_var = tk.StringVar(value=status.get('user_level', 'intermediate'))
        level_combo = ttk.Combobox(general_tab, textvariable=level_var,
                                   values=['beginner', 'intermediate', 'advanced'],
                                   state='readonly')
        level_combo.pack(fill=tk.X, padx=10, pady=5)

        # Кнопки
        buttons_frame = ttk.Frame(config_window)
        buttons_frame.pack(pady=10)

        def apply_ai_settings():
            new_level = level_var.get()
            self.ai_manager.update_user_level(new_level)
            messagebox.showinfo("Успіх", "Налаштування AI збережені")
            config_window.destroy()

        ttk.Button(buttons_frame, text="Застосувати", command=apply_ai_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Скасувати", command=config_window.destroy).pack(side=tk.LEFT, padx=5)

    def show_ai_status(self):
        """Показує детальний статус AI"""
        try:
            status = self.ai_manager.get_enhanced_status()
            recommendations = self.ai_manager.get_learning_recommendations()

            status_text = f"""СТАТУС AI СИСТЕМИ:

🤖 ОСНОВНА ІНФОРМАЦІЯ:
• Статус: {'✅ Активний' if status['available'] else '❌ Недоступний'}
• Модель: {status.get('model', 'Невідома')}
• Підтримка вивчення мови: {'✅ Активна' if status.get('language_learning_enabled') else '❌ Неактивна'}
• Рівень користувача: {status.get('user_level', 'intermediate').title()}
• Мова навчання: {status.get('target_language', 'english').title()}

📊 СТАТИСТИКА ВИКОРИСТАННЯ:
• Всього запитів: {status['usage_stats']['total_requests']}
• Всебічних аналізів: {status['usage_stats']['comprehensive_analyses']}
• Контекстуальних пояснень: {status['usage_stats']['contextual_explanations']}
• Аналізів лексики: {status['usage_stats']['vocabulary_analyses']}
• Інструкцій з вимови: {status['usage_stats']['pronunciation_guides']}
• Помилок: {status['usage_stats']['errors']}
• Середній час відповіді: {status['usage_stats']['average_response_time']:.2f} сек

💡 РЕКОМЕНДАЦІЇ ДЛЯ НАВЧАННЯ:"""

            for rec in recommendations['recommendations']:
                status_text += f"\n• {rec['message']} (пріоритет: {rec['priority']})"

            if status.get('features'):
                status_text += f"\n\n🔧 ДОСТУПНІ ФУНКЦІЇ:"
                for feature, enabled in status['features'].items():
                    status_icon = "✅" if enabled else "❌"
                    status_text += f"\n• {feature.replace('_', ' ').title()}: {status_icon}"

            messagebox.showinfo("Статус AI", status_text)

        except Exception as e:
            self.logger.error(f"Помилка показу статусу AI: {e}")
            messagebox.showerror("Помилка", f"Не вдалося отримати статус AI: {e}")

    def configure_video_processing(self):
        """Налаштування обробки відео"""
        messagebox.showinfo("Інформація",
                            "Налаштування обробки відео будуть додані в наступних версіях.\n"
                            "Поки що доступні: витягування кадрів та базовий аналіз.")

    # ===============================
    # ЕКСПОРТ/ІМПОРТ
    # ===============================

    def export_groups(self):
        """Експорт груп у файл"""
        if not self.current_groups:
            messagebox.showwarning("Попередження", "Немає груп для експорту")
            return

        try:
            file_path = filedialog.asksaveasfilename(
                title="Експорт груп",
                defaultextension=".json",
                filetypes=[("JSON файли", "*.json"), ("Всі файли", "*.*")]
            )

            if file_path:
                export_data = {
                    'video_filename': self.current_video,
                    'silence_threshold': self.silence_threshold,
                    'export_timestamp': datetime.now().isoformat(),
                    'groups': self.current_groups
                }

                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, ensure_ascii=False, indent=2)

                messagebox.showinfo("Успіх", f"Групи експортовані в {file_path}")

        except Exception as e:
            self.logger.error(f"Помилка експорту груп: {e}")
            messagebox.showerror("Помилка", f"Не вдалося експортувати групи: {e}")

    def import_groups(self):
        """Імпорт груп з файлу"""
        try:
            file_path = filedialog.askopenfilename(
                title="Імпорт груп",
                filetypes=[("JSON файли", "*.json"), ("Всі файли", "*.*")]
            )

            if file_path:
                with open(file_path, 'r', encoding='utf-8') as f:
                    import_data = json.load(f)

                groups = import_data.get('groups', [])
                video_filename = import_data.get('video_filename', 'imported_video')

                if groups:
                    self.display_groups(groups, video_filename)
                    messagebox.showinfo("Успіх", f"Імпортовано {len(groups)} груп")
                else:
                    messagebox.showwarning("Попередження", "Файл не містить груп")

        except Exception as e:
            self.logger.error(f"Помилка імпорту груп: {e}")
            messagebox.showerror("Помилка", f"Не вдалося імпортувати групи: {e}")

    # ===============================
    # ОБРОБКА ВІДЕО
    # ===============================

    def regroup_current_video(self):
        """Перегруповує поточне відео з новими налаштуваннями"""
        if not self.current_video:
            messagebox.showwarning("Попередження", "Оберіть відео")
            return

        if messagebox.askyesno("Підтвердження",
                               f"Перегрупувати {self.current_video} з порогом тиші {self.silence_threshold}с?"):
            threading.Thread(target=self.regroup_video_thread, daemon=True).start()

    def regroup_video_thread(self):
        """Перегруповує відео в окремому потоці"""
        try:
            self.update_status("Перегрупування відео...")

            # Отримуємо оригінальні сегменти з БД
            from processing.database_manager import DatabaseManager
            db_manager = DatabaseManager()

            videos = db_manager.get_all_videos()
            video = next((v for v in videos if v['filename'] == self.current_video), None)

            if video:
                segments = db_manager.get_video_segments(video['id'])

                # Створюємо нові групи з оновленим порогом
                new_groups = self.video_processor.segment_grouper.group_segments_by_silence(segments)

                # Оновлюємо відображення
                self.root.after(0, lambda: self.display_groups(new_groups, self.current_video))
                self.update_status(f"Створено {len(new_groups)} нових груп")
            else:
                self.update_status("Відео не знайдено в БД")

        except Exception as e:
            self.logger.error(f"Помилка перегрупування: {e}")
            self.update_status(f"Помилка перегрупування: {e}")

    def process_current_video(self):
        """Обробляє поточне відео з розширеними можливостями"""
        if not self.current_video:
            messagebox.showwarning("Попередження", "Оберіть відео")
            return

        if messagebox.askyesno("Підтвердження",
                               f"Переобробити {self.current_video} з витягуванням кадрів та створенням груп?"):
            threading.Thread(target=self.process_current_video_thread, daemon=True).start()

    def process_current_video_thread(self):
        """Обробляє поточне відео в окремому потоці"""
        try:
            from datetime import datetime

            self.update_status(f"Розширена обробка {self.current_video}...")

            # Знаходимо файл
            videos_dir = Path("videos")
            video_path = videos_dir / self.current_video

            if video_path.exists():
                video_info = {
                    "filename": self.current_video,
                    "filepath": str(video_path),
                    "size": video_path.stat().st_size,
                    "modified": datetime.fromtimestamp(video_path.stat().st_mtime),
                    "extension": video_path.suffix.lower()
                }

                # Використовуємо розширений обробник
                result = self.video_processor.process_single_video_enhanced(video_info)

                if result['success']:
                    message = f"Обробка завершена:\n"
                    message += f"• {result['groups_count']} груп створено\n"
                    message += f"• {result['frames_count']} кадрів витягнуто\n"
                    message += f"• {result['segments_count']} сегментів оброблено"

                    self.update_status("Обробка завершена успішно")

                    # Перезавантажуємо групи
                    self.root.after(0, lambda: self.load_groups_for_video(self.current_video))

                    # Показуємо результат
                    self.root.after(1000, lambda: messagebox.showinfo("Успіх", message))
                else:
                    self.update_status(f"Помилка обробки: {result['error']}")
            else:
                self.update_status("Файл відео не знайдено")

        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Помилка обробки відео: {error_msg}")
            self.update_status(f"Помилка: {error_msg}")

    def process_all_videos(self):
        """Обробляє всі відео з розширеними можливостями"""
        if messagebox.askyesno("Підтвердження",
                               "Обробити всі відео з витягуванням кадрів та створенням груп?\n"
                               "Це може зайняти багато часу."):
            threading.Thread(target=self.process_all_videos_thread, daemon=True).start()

    def process_all_videos_thread(self):
        """Обробляє всі відео в окремому потоці"""
        try:
            self.update_status("Розширена обробка всіх відео...")

            # Показуємо прогрес бар
            self.root.after(0, lambda: self.progress_bar.pack(side=tk.RIGHT, padx=10, pady=2))

            # Скануємо відео файли
            video_files = self.video_processor.scan_videos_directory()

            processed_count = 0
            total_groups = 0
            total_frames = 0

            for video_info in video_files:
                self.update_status(f"Обробка {video_info['filename']}...")

                result = self.video_processor.process_single_video_enhanced(video_info)

                if result['success']:
                    processed_count += 1
                    total_groups += result['groups_count']
                    total_frames += result['frames_count']

            # Приховуємо прогрес бар
            self.root.after(0, lambda: self.progress_bar.pack_forget())

            message = f"Обробка завершена:\n"
            message += f"• {processed_count} відео оброблено\n"
            message += f"• {total_groups} груп створено\n"
            message += f"• {total_frames} кадрів витягнуто"

            self.update_status("Обробка всіх відео завершена")
            self.root.after(0, self.refresh_videos)
            self.root.after(1000, lambda: messagebox.showinfo("Успіх", message))

        except Exception as e:
            self.logger.error(f"Помилка обробки всіх відео: {e}")
            self.update_status(f"Помилка: {e}")
            self.root.after(0, lambda: self.progress_bar.pack_forget())

    def add_video_file(self):
        """Додає новий відео файл з розширеною обробкою"""
        file_path = filedialog.askopenfilename(
            title="Виберіть відео файл",
            filetypes=[
                ("Відео файли", "*.mkv *.mp4 *.avi *.mov *.wmv"),
                ("MKV файли", "*.mkv"),
                ("MP4 файли", "*.mp4"),
                ("Всі файли", "*.*")
            ]
        )

        if file_path:
            threading.Thread(target=self.add_and_process_video_enhanced,
                             args=(file_path,), daemon=True).start()

    def add_and_process_video_enhanced(self, file_path: str):
        """Додає та обробляє новий відео файл з розширеними можливостями"""
        try:
            import shutil
            from datetime import datetime

            self.update_status("Копіювання відео файлу...")

            # Копіюємо файл
            videos_dir = Path("videos")
            videos_dir.mkdir(exist_ok=True)

            filename = Path(file_path).name
            destination = videos_dir / filename

            shutil.copy2(file_path, destination)

            # Розширена обробка
            self.update_status("Розширена обробка нового відео...")

            video_info = {
                "filename": filename,
                "filepath": str(destination),
                "size": destination.stat().st_size,
                "modified": datetime.fromtimestamp(destination.stat().st_mtime),
                "extension": destination.suffix.lower()
            }

            result = self.video_processor.process_single_video_enhanced(video_info)

            if result['success']:
                message = f"Відео оброблено:\n"
                message += f"• {result['groups_count']} груп створено\n"
                message += f"• {result['frames_count']} кадрів витягнуто\n"
                message += f"• {result['segments_count']} сегментів оброблено"

                self.update_status("Нове відео додано успішно")
                self.root.after(0, self.refresh_videos)
                self.root.after(1000, lambda: messagebox.showinfo("Успіх", message))
            else:
                self.update_status(f"Помилка обробки: {result['error']}")

        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Помилка додавання відео: {error_msg}")
            self.update_status(f"Помилка: {error_msg}")

    # ===============================
    # ДОПОМІЖНІ МЕТОДИ
    # ===============================

    def run(self):
        """Запускає головний цикл програми"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()

    def create_status_bar(self):
        """Створює статус бар"""
        status_frame = ttk.Frame(self.root)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)

        # Основний статус
        self.status_var = tk.StringVar()
        self.status_var.set("Готово")

        self.status_label = ttk.Label(
            status_frame,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor=tk.W
        )
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2, pady=2)

        # Прогрес бар
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            status_frame,
            variable=self.progress_var,
            length=200
        )

    def setup_styles(self):
        """Налаштовує стилі інтерфейсу"""
        style = ttk.Style()

        try:
            style.theme_use('vista')
        except:
            try:
                style.theme_use('clam')
            except:
                pass

        # Кастомні стилі
        style.configure("Title.TLabel", font=("Arial", 16, "bold"))
        style.configure("Header.TLabel", font=("Arial", 12, "bold"))

    def load_initial_data(self):
        """Завантажує початкові дані"""
        try:
            self.status_var.set("Завантаження...")

            # Автоматично обробляємо нові відео
            threading.Thread(target=self.auto_process_videos, daemon=True).start()

            # Завантажуємо список відео
            self.refresh_videos()

        except Exception as e:
            self.logger.error(f"Помилка завантаження початкових даних: {e}")
            self.status_var.set(f"Помилка: {e}")

    def auto_process_videos(self):
        """Автоматично обробляє нові/змінені відео"""
        try:
            self.update_status("Перевірка нових відео...")

            # Отримуємо статистику обробки
            stats = self.video_processor.get_processing_statistics()

            if stats.get('videos_processed', 0) > 0:
                message = f"Знайдено нових відео: {stats['videos_processed']}"
                self.root.after(0, lambda: self.status_var.set(message))
                self.root.after(0, self.refresh_videos)
            else:
                self.root.after(0, lambda: self.status_var.set("Готово"))

        except Exception as e:
            self.logger.error(f"Помилка автообробки відео: {e}")
            self.root.after(0, lambda: self.status_var.set("Готово"))

    def update_status(self, message: str):
        """Оновлює статус"""
        self.root.after(0, lambda: self.status_var.set(message))

    def update_ai_status(self):
        """Оновлює статус AI"""
        try:
            if self.ai_manager.is_available():
                status = self.ai_manager.get_enhanced_status()
                model = status.get('model', 'unknown')
                level = status.get('user_level', 'intermediate')
                self.ai_status_label.config(text=f"🤖 AI: {model} ({level})", foreground="green")
            else:
                self.ai_status_label.config(text="🤖 AI: Недоступний", foreground="red")
        except Exception as e:
            self.ai_status_label.config(text="🤖 AI: Помилка", foreground="red")

    def on_closing(self):
        """Безпечне закриття програми"""
        try:
            self.logger.info("Закриття програми...")

            # Скасовуємо створення віджетів
            if self.is_creating_widgets:
                self.widgets_creation_cancelled = True

            # Очищаємо віджети
            self.clear_groups()

            # Закриваємо вікно
            self.root.quit()
            self.root.destroy()

        except Exception as e:
            self.logger.error(f"Помилка при закритті: {e}")
            try:
                self.root.destroy()
            except:
                pass

    # Методи довідки
    def show_user_guide(self):
        """Показує керівництво користувача"""
        guide_text = """КЕРІВНИЦТВО КОРИСТУВАЧА Game Learning 3.0

🚀 ОСНОВНІ ФУНКЦІЇ:
• Розумне групування речень по паузах
• Витягування та аналіз кадрів з відео  
• 4 типи AI аналізу для кожної групи
• Система нотаток з підтримкою зображень

📦 РОБОТА З ГРУПАМИ:
• Групи створюються автоматично на основі пауз ≥5с
• Налаштуйте поріг тиші в верхній панелі
• Використовуйте фільтри для пошуку груп
• Клікніть "Детальніше" для розгортання групи

🤖 AI АНАЛІЗ:
• Всебічний - повний граматичний та лексичний аналіз
• Контекстуальний - пояснення в контексті діалогу
• Лексичний - детальний розбір словникового запасу
• Фонетичний - інструкції з правильної вимови

🖼️ КАДРИ З ВІДЕО:
• Автоматично витягуються при обробці
• Переглядайте кадри в групах
• Збільшуйте кадри подвійним кліком

📝 НОТАТКИ:
• Додавайте текстові замітки
• Прикріплюйте зображення
• Використовуйте теги для організації

⚙️ НАЛАШТУВАННЯ:
• Меню "Групування" - налаштування порогу тиші
• Меню "AI" - рівень користувача та функції
• Меню "Відео" - параметри обробки кадрів"""

        messagebox.showinfo("Керівництво користувача", guide_text)

    def show_shortcuts(self):
        """Показує гарячі клавіші"""
        shortcuts_text = """ГАРЯЧІ КЛАВІШІ:

🎬 ВІДЕО:
• F5 - Оновити список відео
• Ctrl+O - Додати відео файл
• Ctrl+P - Обробити поточне відео
• Ctrl+Shift+P - Обробити всі відео

🤖 AI:
• Ctrl+1 - Всебічний аналіз
• Ctrl+2 - Контекстуальний аналіз  
• Ctrl+3 - Аналіз лексики
• Ctrl+4 - Інструкція з вимови

📦 ГРУПИ:
• Space - Розгорнути/згорнути групу
• Ctrl+C - Копіювати текст групи
• Enter - Відтворити відео з групи

📝 НОТАТКИ:
• Ctrl+S - Зберегти нотатку
• Ctrl+Shift+C - Копіювати нотатку

⚙️ ІНШЕ:
• F1 - Це вікно
• Ctrl+, - Налаштування
• Ctrl+Q - Вихід"""

        messagebox.showinfo("Гарячі клавіші", shortcuts_text)

    def about_dialog(self):
        """Показує діалог про програму"""
        about_text = """Game Learning 3.0

🎯 Розумна система вивчення англійської мови через відео

🆕 НОВІ ФУНКЦІЇ:
• Автоматичне групування по паузах
• Витягування та аналіз кадрів
• 4 типи AI аналізу
• Покращена система нотаток
• Інтелектуальні фільтри та сортування

🛠️ ТЕХНОЛОГІЇ:
• Python 3.11+
• OpenAI Whisper для транскрипції
• Ollama + Llama для AI аналізу
• OpenCV для обробки кадрів
• SQLite для зберігання даних

👨‍💻 РОЗРОБКА:
• Версія: 3.0
• Підтримка: Enhanced Group Learning
• Ліцензія: MIT

🇺🇦 Українська розробка для ефективного вивчення мови!

🔗 GitHub: https://github.com/your-repo
📧 Email: your-email@example.com"""

        messagebox.showinfo("Про програму", about_text)


# ==============================================================
# ТЕСТУВАННЯ ТА ЗАПУСК
# ==============================================================

if __name__ == "__main__":
    """Тестування та запуск оновленого головного вікна"""

    print("🚀 Запуск Game Learning 3.0 - Enhanced Group Learning")
    print("=" * 60)
    print("✅ Розумне групування речень по паузах")
    print("✅ Витягування та аналіз кадрів з відео")
    print("✅ 4 типи AI аналізу для кожної групи")
    print("✅ Покращена система нотаток")
    print("✅ Інтелектуальні фільтри та сортування")
    print("=" * 60)

    try:
        app = UpdatedMainWindow()
        app.run()
    except Exception as e:
        print(f"❌ Помилка запуску програми: {e}")
        import traceback

        traceback.print_exc()
        analysis_submenu.add_command(label="Контекстуальні пояснення", command=self.generate_contextual_for_all)
        analysis_submenu.add_command(label="Аналіз лексики", command=self.generate_vocabulary_for_all)
        analysis_submenu.add_command(label="Інструкції з вимови", command=self.generate_pronunciation_for_all)

        ai_menu.add_separator()
        ai_menu.add_command(label="Налаштування AI...", command=self.configure_ai)
        ai_menu.add_command(label="Статус AI", command=self.show_ai_status)

        # Меню Відео
        video_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Відео", menu=video_menu)
        video_menu.add_command(label="Витягти кадри", command=self.extract_frames_for_current)
        video_menu.add_command(label="Аналіз кадрів", command=self.analyze_frames_for_current)
        video_menu.add_separator()
        video_menu.add_command(label="Налаштування відео...", command=self.configure_video_processing)

        # Меню Допомога
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Допомога", menu=help_menu)
        help_menu.add_command(label="Керівництво користувача", command=self.show_user_guide)
        help_menu.add_command(label="Гарячі клавіші", command=self.show_shortcuts)
        help_menu.add_separator()
        help_menu.add_command(label="Про програму", command=self.about_dialog)


    def create_top_panel(self):
        """Створює верхню панель з налаштуваннями"""
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill=tk.X, padx=10, pady=5)

        # Лейбл та комбобокс для вибору відео
        video_frame = ttk.Frame(top_frame)
        video_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Label(video_frame, text="📹 Відео:", font=("Arial", 12)).pack(side=tk.LEFT, padx=(0, 10))

        self.video_var = tk.StringVar()
        self.video_combo = ttk.Combobox(
            video_frame,
            textvariable=self.video_var,
            state="readonly",
            width=50,
            font=("Arial", 11)
        )
        self.video_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.video_combo.bind('<<ComboboxSelected>>', self.on_video_selected)

        # Налаштування групування
        grouping_frame = ttk.LabelFrame(top_frame, text="Групування")
        grouping_frame.pack(side=tk.LEFT, padx=(10, 0))

        ttk.Label(grouping_frame, text="Тиша (сек):").pack(side=tk.LEFT, padx=5)

        self.silence_var = tk.DoubleVar(value=self.silence_threshold)
        silence_spin = ttk.Spinbox(
            grouping_frame,
            from_=1.0, to=15.0, increment=0.5,
            textvariable=self.silence_var,
            width=8,
            command=self.on_silence_threshold_changed
        )
        silence_spin.pack(side=tk.LEFT, padx=5)

        # Кнопки управління
        buttons_frame = ttk.Frame(top_frame)
        buttons_frame.pack(side=tk.RIGHT)

        ttk.Button(buttons_frame, text="🔄 Оновити",
                   command=self.refresh_videos, width=10).pack(side=tk.LEFT, padx=2)

        ttk.Button(buttons_frame, text="⚙️ Обробити",
                   command=self.process_current_video, width=10).pack(side=tk.LEFT, padx=2)

        ttk.Button(buttons_frame, text="🧠 AI для всіх",
                   command=self.generate_ai_for_current_video, width=12).pack(side=tk.LEFT, padx=2)

        ttk.Button(buttons_frame, text="📊 Статистика",
                   command=self.show_video_statistics, width=12).pack(side=tk.LEFT, padx=2)

        # Кнопка скасування
        self.cancel_button = ttk.Button(buttons_frame, text="❌ Скасувати",
                                        command=self.cancel_widget_creation, state=tk.DISABLED)
        self.cancel_button.pack(side=tk.LEFT, padx=2)

        # Статус AI
        ai_status_frame = ttk.Frame(top_frame)
        ai_status_frame.pack(side=tk.RIGHT, padx=(10, 0))

        self.ai_status_label = ttk.Label(ai_status_frame, text="", font=("Arial", 9))
        self.ai_status_label.pack()

        # Оновлюємо статус AI
        self.update_ai_status()


    def create_main_area(self):
        """Створює головну робочу область"""
        # Основний контейнер
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Paned Window для розділення на ліву та праву частини
        self.paned_window = ttk.PanedWindow(main_container, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True)

        # Ліва частина - групи (75%)
        self.create_groups_panel()

        # Права частина - нотатки (25%)
        self.create_notes_panel()

        # Встановлюємо початкові пропорції
        self.root.after(100, lambda: self.paned_window.sashpos(0, 1200))


    def create_groups_panel(self):
        """Створює панель з групами"""
        # Контейнер для груп
        groups_frame = ttk.Frame(self.paned_window)
        self.paned_window.add(groups_frame, weight=7)

        # Заголовок з статистикою
        header_frame = ttk.Frame(groups_frame)
        header_frame.pack(fill=tk.X, pady=(0, 5))

        self.groups_title = ttk.Label(
            header_frame,
            text="📦 Групи (оберіть відео)",
            font=("Arial", 14, "bold")
        )
        self.groups_title.pack(side=tk.LEFT)

        # Статистика груп
        self.groups_stats = ttk.Label(
            header_frame,
            text="",
            font=("Arial", 10)
        )
        self.groups_stats.pack(side=tk.RIGHT)

        # Додаткова інформаційна панель
        info_frame = ttk.Frame(groups_frame)
        info_frame.pack(fill=tk.X, pady=(0, 5))

        self.grouping_info = ttk.Label(
            info_frame,
            text="💡 Групи створюються автоматично на основі пауз між сегментами",
            font=("Arial", 9),
            foreground="gray"
        )
        self.grouping_info.pack(side=tk.LEFT)

        # Фільтри та сортування
        filters_frame = ttk.Frame(groups_frame)
        filters_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(filters_frame, text="Фільтр:").pack(side=tk.LEFT, padx=(0, 5))

        self.filter_var = tk.StringVar()
        filter_combo = ttk.Combobox(
            filters_frame,
            textvariable=self.filter_var,
            values=["Всі групи", "Легкі", "Середні", "Складні", "З кадрами", "Без кадрів"],
            state="readonly",
            width=15
        )
        filter_combo.pack(side=tk.LEFT, padx=(0, 10))
        filter_combo.bind('<<ComboboxSelected>>', self.apply_groups_filter)

        ttk.Label(filters_frame, text="Сортування:").pack(side=tk.LEFT, padx=(10, 5))

        self.sort_var = tk.StringVar()
        sort_combo = ttk.Combobox(
            filters_frame,
            textvariable=self.sort_var,
            values=["За часом", "За складністю", "За довжиною", "За кількістю слів"],
            state="readonly",
            width=15
        )
        sort_combo.pack(side=tk.LEFT)
        sort_combo.bind('<<ComboboxSelected>>', self.apply_groups_sorting)

        # Canvas з прокруткою для груп
        self.create_groups_scroll_area(groups_frame)


    def create_groups_scroll_area(self, parent):
        """Створює область з прокруткою для груп"""
        # Canvas та Scrollbar
        self.groups_canvas = tk.Canvas(parent, bg="white", highlightthickness=0)
        groups_scrollbar = ttk.Scrollbar(parent, orient="vertical",
                                         command=self.groups_canvas.yview)

        self.groups_scrollable_frame = ttk.Frame(self.groups_canvas)

        # Налаштування прокрутки
        self.groups_scrollable_frame.bind(
            "<Configure>",
            lambda e: self.groups_canvas.configure(
                scrollregion=self.groups_canvas.bbox("all")
            )
        )

        self.groups_canvas.create_window(
            (0, 0),
            window=self.groups_scrollable_frame,
            anchor="nw"
        )
        self.groups_canvas.configure(yscrollcommand=groups_scrollbar.set)

        # Прив'язка колеса миші
        self.groups_canvas.bind_all("<MouseWheel>", self._on_groups_mousewheel)

        # Пакування
        self.groups_canvas.pack(side="left", fill="both", expand=True)
        groups_scrollbar.pack(side="right", fill="y")


    def _on_groups_mousewheel(self, event):
        """Обробка прокрутки мишкою для груп"""
        self.groups_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


    def create_notes_panel(self):
        """Створює панель нотаток"""
        # Контейнер для нотаток
        notes_frame = ttk.Frame(self.paned_window)
        self.paned_window.add(notes_frame, weight=3)

        # Створюємо NotesPanel
        self.notes_panel = NotesPanel(
            parent_frame=notes_frame,
            data_manager=self.data_manager,
            on_note_changed=self.on_note_changed
        )

        # Зберігаємо посилання
        self.notes_panel.main_window = self


    def display_groups(self, groups: List[Dict], filename: str):
        """Відображає групи замість окремих речень"""
        try:
            self.logger.info(f"=== ПОЧАТОК ВІДОБРАЖЕННЯ ГРУП ===")
            self.logger.info(f"Кількість груп для відображення: {len(groups)}")

            # Скасовуємо попереднє створення якщо воно триває
            if self.is_creating_widgets:
                self.cancel_widget_creation()
                self.root.after(100, lambda: self.display_groups(groups, filename))
                return

            # Очищаємо попередні групи
            self.clear_groups()

            # Зберігаємо дані
            self.current_video = filename
            self.current_groups = groups

            # Обчислюємо статистику груп
            group_stats = self.calculate_groups_statistics(groups)

            # Оновлюємо заголовок
            title_text = f"📦 {filename}"
            if group_stats['total_duration_short'] != '0с':
                title_text += f" • {group_stats['total_duration_short']}"

            self.groups_title.config(text=title_text)

            # Оновлюємо статистику
            stats_parts = [
                f"{group_stats['groups_count']} груп",
                f"⏱️ {group_stats['total_duration']}",
                f"📊 середня: {group_stats['avg_group_duration']}",
                f"📝 {group_stats['total_words']} слів"
            ]

            if group_stats['frames_count'] > 0:
                stats_parts.append(f"🖼️ {group_stats['frames_count']} кадрів")

            stats_text = " • ".join(stats_parts)
            self.groups_stats.config(text=stats_text)

            # Оновлюємо інформацію про групування
            threshold_text = f"💡 Групи розділені паузами ≥{self.silence_threshold}с"
            if group_stats['avg_pause_duration'] > 0:
                avg_pause = format_duration(group_stats['avg_pause_duration'], short=True)
                threshold_text += f" (середня пауза: {avg_pause})"

            self.grouping_info.config(text=threshold_text)

            self.logger.info(f"Статистика груп: {stats_text}")

            # Запускаємо створення віджетів груп
            self.create_group_widgets_in_batches(groups, filename)

        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"❌ КРИТИЧНА ПОМИЛКА відображення груп: {error_msg}")
            import traceback
            self.logger.error(f"Деталі помилки:\n{traceback.format_exc()}")
            self.status_var.set(f"Помилка: {error_msg}")


    def calculate_groups_statistics(self, groups: List[Dict]) -> Dict:
        """Обчислює статистику груп"""
        if not groups:
            return {
                'groups_count': 0,
                'total_duration': '0 сек',
                'total_duration_short': '0с',
                'avg_group_duration': '0с',
                'total_words': 0,
                'frames_count': 0,
                'avg_pause_duration': 0.0
            }

        total_duration = sum(g.get('group_duration', 0) for g in groups)
        total_words = sum(g.get('word_count', 0) for g in groups)
        total_frames = sum(len(g.get('frames', [])) for g in groups)

        avg_duration = total_duration / len(groups)

        # Обчислюємо середню паузу між групами
        pauses = []
        for i in range(1, len(groups)):
            prev_end = groups[i - 1].get('group_end_time', 0)
            curr_start = groups[i].get('group_start_time', 0)
            if curr_start > prev_end:
                pauses.append(curr_start - prev_end)

        avg_pause = sum(pauses) / len(pauses) if pauses else 0.0

        return {
            'groups_count': len(groups),
            'total_duration': format_duration(total_duration),
            'total_duration_short': format_duration(total_duration, short=True),
            'avg_group_duration': format_duration(avg_duration, short=True),
            'total_words': total_words,
            'frames_count': total_frames,
            'avg_pause_duration': avg_pause
        }


    def create_group_widgets_in_batches(self, groups: List[Dict], filename: str, batch_size: int = 3):
        """Створює віджети груп порціями"""
        if self.is_creating_widgets:
            self.logger.warning("Створення віджетів вже в процесі")
            return

        self.is_creating_widgets = True
        self.widgets_creation_cancelled = False
        self.cancel_button.config(state=tk.NORMAL)

        total = len(groups)
        current_index = 0

        # Показуємо прогрес
        self.show_progress_message(f"Створення груп: 0/{total}")

        def create_next_batch():
            nonlocal current_index

            # Перевірка на скасування
            if self.widgets_creation_cancelled:
                self.logger.info("Створення віджетів груп скасовано")
                self.finish_widget_creation(cancelled=True)
                return

            # Перевірка завершення
            if current_index >= total:
                self.logger.info(f"=== СТВОРЕНО {len(self.group_widgets)} ВІДЖЕТІВ ГРУП ===")
                self.finish_widget_creation()
                return

            # Визначаємо межі батчу
            batch_end = min(current_index + batch_size, total)

            # Створюємо віджети в поточному батчі
            for i in range(current_index, batch_end):
                if self.widgets_creation_cancelled:
                    return

                try:
                    group = groups[i]
                    self.logger.info(f"Створення групи {i + 1}/{total}: {group.get('combined_text', '')[:50]}...")

                    # Створюємо віджет групи
                    group_widget = EnhancedGroupWidget(
                        parent_frame=self.groups_scrollable_frame,
                        group_data=group,
                        video_filename=filename,
                        group_index=i,
                        ai_manager=self.ai_manager,
                        data_manager=self.data_manager,
                        on_group_click=self.on_group_clicked
                    )

                    self.group_widgets.append(group_widget)
                    self.logger.info(f"✅ GroupWidget {i} створений успішно")

                except Exception as widget_error:
                    self.logger.error(f"❌ Помилка створення GroupWidget {i}: {widget_error}")
                    import traceback
                    self.logger.error(f"Деталі помилки:\n{traceback.format_exc()}")
                    continue

            # Оновлюємо прогрес
            current_index = batch_end
            progress_text = f"Створення груп: {current_index}/{total} ({current_index / total * 100:.1f}%)"
            self.update_progress_message(progress_text)

            # Примусово оновлюємо інтерфейс
            self.groups_canvas.update_idletasks()

            # Плануємо наступний батч з паузою
            self.root.after(200, create_next_batch)  # Більша пауза для груп

        # Запускаємо перший батч
        self.root.after(10, create_next_batch)


    def finish_widget_creation(self, cancelled: bool = False):
        """Завершує створення віджетів груп"""
        try:
            self.is_creating_widgets = False
            self.cancel_button.config(state=tk.DISABLED)

            if cancelled:
                self.status_var.set("Створення груп скасовано")
                self.hide_progress_message()
                return

            # Ховаємо повідомлення прогресу
            self.hide_progress_message()

            # Примусово оновлюємо інтерфейс
            self.groups_canvas.update_idletasks()

            # Прокрутка до початку
            self.groups_canvas.yview_moveto(0)

            # Фінальне оновлення
            self.root.update_idletasks()

            total_widgets = len(self.group_widgets)
            self.status_var.set(f"Завантажено {total_widgets} груп")
            self.logger.info(f"=== ВІДОБРАЖЕННЯ ГРУП ЗАВЕРШЕНО: {total_widgets} віджетів ===")

        except Exception as e:
            self.logger.error(f"Помилка завершення створення віджетів груп: {e}")


    def cancel_widget_creation(self):
        """Скасовує створення віджетів"""
        if self.is_creating_widgets:
            self.widgets_creation_cancelled = True
            self.logger.info("Запит на скасування створення віджетів груп")


    def show_progress_message(self, message: str):
        """Показує повідомлення прогресу"""
        if hasattr(self, 'progress_label'):
            self.progress_label.destroy()

        self.progress_label = ttk.Label(
            self.groups_scrollable_frame,
            text=f"🔄 {message}",
            font=("Arial", 12, "bold"),
            background="#fff3cd"
        )
        self.progress_label.pack(pady=20)
        self.root.update_idletasks()


    def update_progress_message(self, message: str):
        """Оновлює повідомлення прогресу"""
        if hasattr(self, 'progress_label') and self.progress_label.winfo_exists():
            self.progress_label.config(text=f"🔄 {message}")
            self.root.update_idletasks()


    def hide_progress_message(self):
        """Ховає повідомлення прогресу"""
        if hasattr(self, 'progress_label'):
            try:
                self.progress_label.destroy()
                delattr(self, 'progress_label')
            except:
                pass


    def clear_groups(self):
        """Очищає всі групи безпечно"""
        try:
            # Скасовуємо створення віджетів якщо воно триває
            if self.is_creating_widgets:
                self.cancel_widget_creation()
                self.root.after(50)

            self.logger.info(f"Очищення {len(self.group_widgets)} віджетів груп...")

            # Видаляємо віджети
            for i, widget in enumerate(self.group_widgets):
                try:
                    if hasattr(widget, 'main_frame') and widget.main_frame.winfo_exists():
                        widget.main_frame.destroy()
                        self.logger.debug(f"Віджет групи {i} видалений")
                except Exception as e:
                    self.logger.warning(f"Помилка видалення віджета групи {i}: {e}")

            self.group_widgets.clear()

            # Очищаємо батьківський фрейм
            for child in self.groups_scrollable_frame.winfo_children():
                try:
                    child.destroy()
                except:
                    pass

            # Очищаємо дані
            self.current_groups.clear()
            self.selected_group = None

            # Скидаємо прокрутку
            self.groups_canvas.yview_moveto(0)

            self.logger.info("Очищення груп завершено")

        except Exception as e:
            self.logger.error(f"Помилка очищення груп: {e}")


    def refresh_videos(self):
        """Оновлює список відео з інформацією про групи"""
        try:
            # Отримуємо оброблені відео
            video_states = self.data_manager.get_all_video_states()
            processed_videos = [v for v in video_states if v['processing_completed']]

            # Створюємо список для комбобокса з інформацією про групи
            video_options = []
            for video in processed_videos:
                filename = video['video_filename']

                try:
                    # Отримуємо групи для відео
                    groups = self.video_processor.get_video_groups(filename)

                    if groups:
                        total_duration = sum(g.get('group_duration', 0) for g in groups)
                        duration_text = format_duration(total_duration, short=True)
                        frames_count = sum(len(g.get('frames', [])) for g in groups)

                        info_parts = [f"{len(groups)} груп", duration_text]
                        if frames_count > 0:
                            info_parts.append(f"{frames_count} кадрів")

                        video_options.append(f"{filename} ({' • '.join(info_parts)})")
                    else:
                        video_options.append(f"{filename} (не оброблено)")

                except Exception as e:
                    self.logger.debug(f"Не вдалося отримати групи для {filename}: {e}")
                    video_options.append(f"{filename} (помилка)")

            # Оновлюємо комбобокс
            self.video_combo['values'] = video_options

            if video_options and not self.current_video:
                self.video_combo.current(0)
                self.on_video_selected()

            self.logger.info(f"Завантажено {len(video_options)} відео")

        except Exception as e:
            self.logger.error(f"Помилка оновлення списку відео: {e}")


    def on_video_selected(self, event=None):
        """Обробляє вибір відео"""
        selected = self.video_var.get()
        if not selected:
            return

        try:
            # Витягуємо назву файлу з рядка
            filename = selected.split(' (')[0]

            self.status_var.set(f"Завантаження груп для {filename}...")

            # Завантажуємо групи в окремому потоці
            threading.Thread(target=self.load_groups_for_video,
                             args=(filename,), daemon=True).start()

        except Exception as e:
            self.logger.error(f"Помилка вибору відео: {e}")
            messagebox.showerror("Помилка", f"Не вдалося завантажити відео: {e}")


    def load_groups_for_video(self, filename: str):
        """Завантажує групи для відео"""
        try:
            # Отримуємо групи з enhanced video processor
            groups = self.video_processor.get_video_groups(filename)

            if not groups:
                # Якщо немає груп, спробуємо створити їх
                self.logger.info(f"Немає груп для {filename}, створюємо...")
                self.root.after(0, lambda: self.status_var.set(f"Створення груп для {filename}..."))

                # Викликаємо обробку відео для створення груп
                video_info = {
                    "filename": filename,
                    "filepath": f"videos/{filename}"  # Припускаємо стандартну структуру
                }

                result = self.video_processor.process_single_video_enhanced(video_info)

                if result['success']:
                    groups = self.video_processor.get_video_groups(filename)
                else:
                    raise Exception(f"Помилка створення груп: {result.get('error', 'Невідома помилка')}")

            # Оновлюємо UI в головному потоці
            self.root.after(0, lambda: self.display_groups(groups, filename))

        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Помилка завантаження груп: {error_msg}")
            self.root.after(0, lambda msg=error_msg: messagebox.showerror("Помилка",
                                                                          f"Не вдалося завантажити групи: {msg}"))


    def on_group_clicked(self, group_data: Dict, video_filename: str):
        """Обробляє клік по групі"""
        self.selected_group = group_data

        # Передаємо контекст групи в панель нотаток
        # Використовуємо перше речення групи як контекст
        segments = group_data.get('segments', [])
        if segments:
            first_segment = segments[0]
            sentence_data = {
                'text': first_segment.get('text', ''),
                'start_time': first_segment.get('start_time', 0),
                'end_time': first_segment.get('end_time', 0)
            }
            self.notes_panel.set_sentence_context(sentence_data, video_filename)

        self.logger.debug(f"Вибрано групу: {group_data.get('combined_text', '')[:50]}...")


    def on_note_changed(self):
        """Обробляє зміну нотатки"""
        pass


    def on_silence_threshold_changed(self):
        """Обробляє зміну порогу тиші"""
        new_threshold = self.silence_var.get()
        if new_threshold != self.silence_threshold:
            self.silence_threshold = new_threshold
            self.video_processor.segment_grouper.silence_threshold = new_threshold



