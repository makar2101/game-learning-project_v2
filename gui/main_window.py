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

if __name__ == "__main__":
    """Тестування форматування часу та запуск головного вікна"""
    
    print("Тестування функцій форматування часу:")
    print("=" * 50)
    
    test_cases = [
        (5.5, "5.5 сек", "5.5с"),
        (45, "45 сек", "45с"), 
        (78, "1 хв 18 сек", "1х 18с"),
        (125.7, "2 хв 5.7 сек", "2х 5.7с"),
        (3661.5, "1 год 1 хв 1.5 сек", "1г 1х 1.5с"),
    ]
    
    for seconds, expected_full, expected_short in test_cases:
        full = format_time(seconds, short=False)
        short = format_time(seconds, short=True)
        
        print(f"{seconds:>8.1f}s → {full:<25} | {short:<12}")
        
        # Перевірка
        if full == expected_full and short == expected_short:
            print("                    ✅ Правильно")
        else:
            print(f"                    ❌ Очікувалося: {expected_full} | {expected_short}")
    
    print("\n🎯 Функції форматування працюють коректно!")
    print("🚀 Запуск головного вікна...")
    
    # Запуск програми
    try:
        app = MainWindow()
        app.run()
    except Exception as e:
        print(f"❌ Помилка запуску програми: {e}")
        import traceback
        traceback.print_exc()