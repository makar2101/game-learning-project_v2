"""
Enhanced Group Widget - віджет для відображення групи сегментів з кадрами та покращеним AI
Замінює окремі речення на групи з паузами, додає відображення кадрів та детальні AI пояснення
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
import threading
import base64
import io
from typing import Dict, List, Optional, Callable
from datetime import datetime
from PIL import Image, ImageTk

# Імпорти функцій форматування часу
from utils.time_formatting import format_time, format_time_range, format_duration


class FrameViewer:
    """Компонент для відображення кадрів з відео"""

    def __init__(self, parent_frame: ttk.Frame):
        self.parent = parent_frame
        self.current_frames = []
        self.frame_index = 0
        self.logger = logging.getLogger(__name__)

        self.create_viewer()

    def create_viewer(self):
        """Створює інтерфейс для перегляду кадрів"""
        # Заголовок
        header_frame = ttk.Frame(self.parent)
        header_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(header_frame, text="🖼️ Кадри з відео:", font=("Arial", 10, "bold")).pack(side=tk.LEFT)

        # Індикатор кадрів
        self.frame_indicator = ttk.Label(header_frame, text="", font=("Arial", 9))
        self.frame_indicator.pack(side=tk.RIGHT)

        # Контейнер для кадру
        self.frame_container = ttk.Frame(self.parent)
        self.frame_container.pack(fill=tk.BOTH, expand=True)

        # Лейбл для зображення
        self.image_label = ttk.Label(self.frame_container, text="📷 Кадри не завантажені")
        self.image_label.pack(expand=True)

        # Кнопки навігації
        nav_frame = ttk.Frame(self.parent)
        nav_frame.pack(fill=tk.X, pady=(5, 0))

        self.prev_btn = ttk.Button(nav_frame, text="◀ Попередній",
                                   command=self.previous_frame, state=tk.DISABLED)
        self.prev_btn.pack(side=tk.LEFT, padx=2)

        self.next_btn = ttk.Button(nav_frame, text="Наступний ▶",
                                   command=self.next_frame, state=tk.DISABLED)
        self.next_btn.pack(side=tk.LEFT, padx=2)

        self.open_btn = ttk.Button(nav_frame, text="🔍 Збільшити",
                                   command=self.open_fullscreen, state=tk.DISABLED)
        self.open_btn.pack(side=tk.RIGHT, padx=2)

        # Інформація про кадр
        self.frame_info = ttk.Label(nav_frame, text="", font=("Arial", 8))
        self.frame_info.pack(side=tk.RIGHT, padx=(10, 5))

    def load_frames(self, frames_data: List[Dict]):
        """Завантажує кадри для відображення"""
        self.current_frames = frames_data
        self.frame_index = 0

        if frames_data:
            self.update_frame_display()
            self.prev_btn.config(state=tk.NORMAL if len(frames_data) > 1 else tk.DISABLED)
            self.next_btn.config(state=tk.NORMAL if len(frames_data) > 1 else tk.DISABLED)
            self.open_btn.config(state=tk.NORMAL)
        else:
            self.clear_display()

    def update_frame_display(self):
        """Оновлює відображення поточного кадру"""
        if not self.current_frames:
            return

        try:
            frame_data = self.current_frames[self.frame_index]

            # Декодуємо base64 зображення
            image_data = base64.b64decode(frame_data['thumbnail_b64'])
            image = Image.open(io.BytesIO(image_data))

            # Масштабуємо для відображення
            display_image = self.resize_for_display(image, (300, 200))
            photo = ImageTk.PhotoImage(display_image)

            # Оновлюємо відображення
            self.image_label.config(image=photo, text="")
            self.image_label.image = photo  # Зберігаємо посилання

            # Оновлюємо індикатор та інформацію
            total = len(self.current_frames)
            self.frame_indicator.config(text=f"{self.frame_index + 1}/{total}")

            timestamp = format_time(frame_data['timestamp'])
            self.frame_info.config(text=f"⏰ {timestamp}")

            # Додаємо клік для збільшення
            self.image_label.bind('<Double-Button-1>', lambda e: self.open_fullscreen())

        except Exception as e:
            self.logger.error(f"Помилка відображення кадру: {e}")
            self.image_label.config(image="", text="❌ Помилка завантаження кадру")

    def resize_for_display(self, image: Image.Image, target_size: tuple) -> Image.Image:
        """Змінює розмір зображення зберігаючи пропорції"""
        original_width, original_height = image.size
        target_width, target_height = target_size

        # Обчислюємо коефіцієнт масштабування
        ratio = min(target_width / original_width, target_height / original_height)

        new_width = int(original_width * ratio)
        new_height = int(original_height * ratio)

        return image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    def previous_frame(self):
        """Перехід до попереднього кадру"""
        if self.current_frames and self.frame_index > 0:
            self.frame_index -= 1
            self.update_frame_display()

    def next_frame(self):
        """Перехід до наступного кадру"""
        if self.current_frames and self.frame_index < len(self.current_frames) - 1:
            self.frame_index += 1
            self.update_frame_display()

    def open_fullscreen(self):
        """Відкриває кадр у повнорозмірному вікні"""
        if not self.current_frames:
            return

        try:
            frame_data = self.current_frames[self.frame_index]

            # Створюємо нове вікно
            fullscreen_window = tk.Toplevel(self.parent)
            fullscreen_window.title(f"Кадр - {format_time(frame_data['timestamp'])}")
            fullscreen_window.geometry("800x600")

            # Завантажуємо повнорозмірне зображення з файлу
            if 'frame_path' in frame_data:
                try:
                    image = Image.open(frame_data['frame_path'])
                    display_image = self.resize_for_display(image, (750, 550))
                    photo = ImageTk.PhotoImage(display_image)

                    label = ttk.Label(fullscreen_window, image=photo)
                    label.image = photo
                    label.pack(expand=True)

                    # Додаємо інформацію
                    info_frame = ttk.Frame(fullscreen_window)
                    info_frame.pack(fill=tk.X, padx=10, pady=5)

                    ttk.Label(info_frame, text=f"Час: {format_time(frame_data['timestamp'])}").pack(side=tk.LEFT)
                    ttk.Label(info_frame, text=f"Розмір: {image.size[0]}×{image.size[1]}").pack(side=tk.RIGHT)

                except Exception as e:
                    ttk.Label(fullscreen_window, text=f"❌ Помилка завантаження: {e}").pack(expand=True)

        except Exception as e:
            self.logger.error(f"Помилка відкриття повнорозмірного кадру: {e}")

    def clear_display(self):
        """Очищає відображення"""
        self.image_label.config(image="", text="📷 Кадри не завантажені")
        self.image_label.image = None
        self.frame_indicator.config(text="")
        self.frame_info.config(text="")
        self.prev_btn.config(state=tk.DISABLED)
        self.next_btn.config(state=tk.DISABLED)
        self.open_btn.config(state=tk.DISABLED)


class AIAnalysisPanel:
    """Панель для різних типів AI аналізу"""

    def __init__(self, parent_frame: ttk.Frame, ai_manager, group_data: Dict):
        self.parent = parent_frame
        self.ai_manager = ai_manager
        self.group_data = group_data
        self.logger = logging.getLogger(__name__)

        self.analysis_tabs = {}
        self.create_panel()

    def create_panel(self):
        """Створює панель з вкладками для різних типів аналізу"""
        # Заголовок
        header_frame = ttk.Frame(self.parent)
        header_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(header_frame, text="🤖 AI Аналіз:", font=("Arial", 10, "bold")).pack(side=tk.LEFT)

        # Кнопки для генерації різних типів аналізу
        buttons_frame = ttk.Frame(header_frame)
        buttons_frame.pack(side=tk.RIGHT)

        ttk.Button(buttons_frame, text="📚 Всебічний",
                   command=self.generate_comprehensive, width=12).pack(side=tk.LEFT, padx=1)
        ttk.Button(buttons_frame, text="🔗 Контекст",
                   command=self.generate_contextual, width=10).pack(side=tk.LEFT, padx=1)
        ttk.Button(buttons_frame, text="📝 Лексика",
                   command=self.generate_vocabulary, width=10).pack(side=tk.LEFT, padx=1)
        ttk.Button(buttons_frame, text="🗣️ Вимова",
                   command=self.generate_pronunciation, width=10).pack(side=tk.LEFT, padx=1)

        # Створюємо Notebook для вкладок
        self.notebook = ttk.Notebook(self.parent)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        # Створюємо вкладки для різних типів аналізу
        self.create_analysis_tabs()

    def create_analysis_tabs(self):
        """Створює вкладки для різних типів аналізу"""
        analysis_types = [
            ("comprehensive", "📚 Всебічний", "💡 Натисніть 'Всебічний' для детального аналізу"),
            ("contextual", "🔗 Контекст", "💡 Натисніть 'Контекст' для контекстуального пояснення"),
            ("vocabulary", "📝 Лексика", "💡 Натисніть 'Лексика' для аналізу словникового запасу"),
            ("pronunciation", "🗣️ Вимова", "💡 Натисніть 'Вимова' для інструкції з вимови")
        ]

        for analysis_type, tab_title, placeholder_text in analysis_types:
            # Створюємо фрейм для вкладки
            tab_frame = ttk.Frame(self.notebook)
            self.notebook.add(tab_frame, text=tab_title)

            # Створюємо текстове поле з прокруткою
            text_widget = tk.Text(
                tab_frame,
                wrap=tk.WORD,
                font=("Arial", 10),
                bg="#f8f9fa",
                relief=tk.FLAT,
                borderwidth=1
            )

            scrollbar = ttk.Scrollbar(tab_frame, orient="vertical", command=text_widget.yview)
            text_widget.configure(yscrollcommand=scrollbar.set)

            text_widget.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            # Додаємо плейсхолдер
            text_widget.insert(tk.END, placeholder_text)
            text_widget.config(state=tk.DISABLED)

            # Зберігаємо посилання
            self.analysis_tabs[analysis_type] = text_widget

    def generate_comprehensive(self):
        """Генерує всебічний аналіз"""
        self._generate_analysis("comprehensive",
                                self.ai_manager.analyze_sentence_comprehensive,
                                self._prepare_comprehensive_context())

    def generate_contextual(self):
        """Генерує контекстуальне пояснення"""
        self._generate_analysis("contextual",
                                self.ai_manager.explain_in_context,
                                self._prepare_contextual_context())

    def generate_vocabulary(self):
        """Генерує аналіз лексики"""
        self._generate_analysis("vocabulary",
                                self.ai_manager.analyze_vocabulary)

    def generate_pronunciation(self):
        """Генерує інструкцію з вимови"""
        self._generate_analysis("pronunciation",
                                self.ai_manager.get_pronunciation_guide)

    def _generate_analysis(self, analysis_type: str, ai_method, context=None):
        """Універсальний метод для генерації аналізу"""
        if not self.ai_manager or not self.ai_manager.is_available():
            self._show_error(analysis_type, "AI недоступний")
            return

        text_widget = self.analysis_tabs[analysis_type]
        text = self.group_data['combined_text']

        # Показуємо стан завантаження
        self._show_loading(analysis_type)

        # Переключаємо на відповідну вкладку
        for i, (tab_type, _, _) in enumerate([
            ("comprehensive", "", ""), ("contextual", "", ""),
            ("vocabulary", "", ""), ("pronunciation", "", "")
        ]):
            if tab_type == analysis_type:
                self.notebook.select(i)
                break

        # Запускаємо аналіз в окремому потоці
        threading.Thread(
            target=self._analysis_thread,
            args=(analysis_type, ai_method, text, context),
            daemon=True
        ).start()

    def _analysis_thread(self, analysis_type: str, ai_method, text: str, context=None):
        """Виконує аналіз в окремому потоці"""
        try:
            if context is not None:
                result = ai_method(text, context)
            else:
                result = ai_method(text)

            # Оновлюємо UI в головному потоці
            self.parent.after(0, lambda: self._update_analysis_result(analysis_type, result))

        except Exception as e:
            self.parent.after(0, lambda: self._show_error(analysis_type, str(e)))

    def _update_analysis_result(self, analysis_type: str, result: Dict):
        """Оновлює результат аналізу в UI"""
        text_widget = self.analysis_tabs[analysis_type]

        if result.get('success'):
            # Форматуємо відповідь залежно від типу аналізу
            formatted_text = self._format_analysis_result(analysis_type, result)

            text_widget.config(state=tk.NORMAL, bg="#ffffff")
            text_widget.delete(1.0, tk.END)
            text_widget.insert(tk.END, formatted_text)
            text_widget.config(state=tk.DISABLED)
        else:
            self._show_error(analysis_type, result.get('error', 'Невідома помилка'))

    def _format_analysis_result(self, analysis_type: str, result: Dict) -> str:
        """Форматує результат аналізу для відображення"""
        timestamp = datetime.now().strftime("%H:%M:%S")

        if analysis_type == "comprehensive":
            analysis = result.get('analysis', {})
            if isinstance(analysis, dict):
                formatted = f"🕐 Згенеровано: {timestamp}\n"
                formatted += f"📊 Рівень складності: {result.get('difficulty_level', 'Невизначено')}\n\n"

                sections = [
                    ("🔤 ПЕРЕКЛАД:", analysis.get('translation', '')),
                    ("📚 ГРАМАТИКА:", analysis.get('grammar', '')),
                    ("📖 ЛЕКСИКА:", analysis.get('vocabulary', '')),
                    ("🗣️ ФОНЕТИКА:", analysis.get('phonetics', '')),
                    ("💡 ПОРАДИ:", analysis.get('memorization_tips', ''))
                ]

                for title, content in sections:
                    if content.strip():
                        formatted += f"{title}\n{content.strip()}\n\n"

                return formatted
            else:
                return f"🕐 Згенеровано: {timestamp}\n\n{analysis.get('full_text', result.get('analysis', ''))}"

        elif analysis_type == "contextual":
            return f"🕐 Згенеровано: {timestamp}\n\n{result.get('explanation', '')}"

        elif analysis_type == "vocabulary":
            vocab_text = f"🕐 Згенеровано: {timestamp}\n\n"
            vocab_text += result.get('vocabulary_analysis', '')

            # Додаємо ключові слова
            key_words = result.get('key_words', [])
            if key_words:
                vocab_text += "\n\n🔑 КЛЮЧОВІ СЛОВА:\n"
                for word_info in key_words:
                    vocab_text += f"• {word_info['word']} (складність: {word_info['complexity']})\n"

            return vocab_text

        elif analysis_type == "pronunciation":
            pronunciation_text = f"🕐 Згенеровано: {timestamp}\n\n"
            pronunciation_text += result.get('pronunciation_guide', '')

            # Додаємо фонетичну інформацію
            phonetic_info = result.get('phonetic_info', {})
            if phonetic_info:
                pronunciation_text += "\n\n🎯 ФОНЕТИЧНА ІНФОРМАЦІЯ:\n"

                difficult_sounds = phonetic_info.get('difficult_sounds', [])
                if difficult_sounds:
                    pronunciation_text += f"⚠️ Складні звуки: {', '.join(difficult_sounds)}\n"

                duration = phonetic_info.get('estimated_duration', 0)
                if duration:
                    pronunciation_text += f"⏱️ Приблизна тривалість: {duration:.1f} секунд\n"

            return pronunciation_text

        return f"🕐 Згенеровано: {timestamp}\n\n{result}"

    def _show_loading(self, analysis_type: str):
        """Показує стан завантаження"""
        text_widget = self.analysis_tabs[analysis_type]
        text_widget.config(state=tk.NORMAL, bg="#fff3cd")
        text_widget.delete(1.0, tk.END)
        text_widget.insert(tk.END, "🔄 Генерація аналізу...\nБудь ласка, зачекайте...")
        text_widget.config(state=tk.DISABLED)

    def _show_error(self, analysis_type: str, error_message: str):
        """Показує помилку"""
        text_widget = self.analysis_tabs[analysis_type]
        text_widget.config(state=tk.NORMAL, bg="#f8d7da")
        text_widget.delete(1.0, tk.END)
        text_widget.insert(tk.END, f"❌ Помилка: {error_message}")
        text_widget.config(state=tk.DISABLED)

    def _prepare_comprehensive_context(self) -> Dict:
        """Підготовує контекст для всебічного аналізу"""
        return {
            "video_title": getattr(self, 'video_filename', 'Невідоме відео'),
            "scene_description": f"Група тривалістю {self.group_data.get('group_duration', 0):.1f} секунд",
            "difficulty_level": self.group_data.get('difficulty_level', 'intermediate'),
            "word_count": self.group_data.get('word_count', 0)
        }

    def _prepare_contextual_context(self) -> Dict:
        """Підготовує контекст для контекстуального аналізу"""
        # Тут можна додати логіку для отримання попередніх та наступних груп
        return {
            "previous_sentence": "Попередня група...",  # TODO: реалізувати
            "next_sentence": "Наступна група...",  # TODO: реалізувати
            "video_description": f"Відео група з {self.group_data.get('segments_count', 0)} сегментів"
        }


class EnhancedGroupWidget:
    """Розширений віджет для відображення групи сегментів з кадрами та AI"""

    def __init__(self,
                 parent_frame: ttk.Frame,
                 group_data: Dict,
                 video_filename: str,
                 group_index: int,
                 ai_manager,
                 data_manager,
                 on_group_click: Optional[Callable] = None):
        """Ініціалізація віджета групи"""

        self.parent = parent_frame
        self.group_data = group_data
        self.video_filename = video_filename
        self.group_index = group_index
        self.ai_manager = ai_manager
        self.data_manager = data_manager
        self.on_group_click = on_group_click

        self.logger = logging.getLogger(__name__)

        # Перевірка даних
        if not self._validate_group_data():
            raise ValueError("Невалідні дані групи")

        # Стан віджета
        self.is_expanded = False
        self.is_destroyed = False

        # Створюємо віджет
        self.create_widget()

    def _validate_group_data(self) -> bool:
        """Перевіряє валідність даних групи"""
        required_fields = ['combined_text', 'group_start_time', 'group_end_time', 'group_duration']
        return all(field in self.group_data for field in required_fields)

    def create_widget(self):
        """Створює віджет групи"""
        try:
            # Формуємо заголовок з інформацією про групу
            duration = self.group_data['group_duration']
            start_time = self.group_data['group_start_time']
            word_count = self.group_data.get('word_count', 0)
            segments_count = self.group_data.get('segments_count', 0)
            difficulty = self.group_data.get('difficulty_level', 'intermediate')

            # Форматуємо час
            duration_text = format_duration(duration, short=True)
            start_time_text = format_time(start_time, short=True)

            # Створюємо заголовок
            title_parts = [
                f"Група {self.group_index + 1}",
                f"🕐 {start_time_text}",
                f"⏱️ {duration_text}",
                f"📝 {word_count} слів",
                f"🎯 {segments_count} сегментів"
            ]

            # Додаємо індикатор складності
            difficulty_icons = {
                'beginner': '🟢',
                'intermediate': '🟡',
                'advanced': '🔴'
            }
            difficulty_icon = difficulty_icons.get(difficulty.split()[0].lower(), '🟡')
            title_parts.append(f"{difficulty_icon} {difficulty}")

            title_text = " • ".join(title_parts)

            # Створюємо основний фрейм групи
            self.main_frame = ttk.LabelFrame(self.parent, text=title_text)
            self.main_frame.pack(fill=tk.X, padx=5, pady=3)

            # Створюємо розгорнутий вміст
            self.create_group_header()
            self.create_expandable_content()

        except Exception as e:
            self.logger.error(f"Помилка створення віджета групи: {e}")
            raise

    def create_group_header(self):
        """Створює заголовок групи з основною інформацією"""
        header_frame = ttk.Frame(self.main_frame)
        header_frame.pack(fill=tk.X, padx=5, pady=5)

        # Текст групи (скорочена версія)
        text_frame = ttk.Frame(header_frame)
        text_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(text_frame, text="🇬🇧 English:", font=("Arial", 10, "bold")).pack(anchor=tk.W)

        # Показуємо перші 150 символів тексту
        preview_text = self.group_data['combined_text']
        if len(preview_text) > 150:
            preview_text = preview_text[:150] + "..."

        self.preview_label = tk.Text(
            text_frame,
            height=3,
            font=("Arial", 11),
            bg="#f0f0f0",
            relief=tk.FLAT,
            borderwidth=1,
            state=tk.DISABLED,
            cursor="hand2",
            wrap=tk.WORD
        )
        self.preview_label.pack(fill=tk.X, pady=(2, 0))

        # Вставляємо попередній текст
        self.preview_label.config(state=tk.NORMAL)
        self.preview_label.insert(tk.END, preview_text)
        self.preview_label.config(state=tk.DISABLED)

        # Кнопки управління
        controls_frame = ttk.Frame(header_frame)
        controls_frame.pack(fill=tk.X, pady=(5, 0))

        # Ліві кнопки
        left_controls = ttk.Frame(controls_frame)
        left_controls.pack(side=tk.LEFT)

        ttk.Button(left_controls, text="▶ Відтворити",
                   command=self.play_group_video, width=12).pack(side=tk.LEFT, padx=2)
        ttk.Button(left_controls, text="📋 Копіювати",
                   command=self.copy_group_text, width=12).pack(side=tk.LEFT, padx=2)

        # Права кнопка розгортання
        self.expand_button = ttk.Button(controls_frame, text="🔽 Детальніше",
                                        command=self.toggle_expansion, width=15)
        self.expand_button.pack(side=tk.RIGHT)

        # Прив'язуємо клік до тексту
        self.preview_label.bind('<Button-1>', self.on_group_selected)

    def create_expandable_content(self):
        """Створює розгорнутий вміст групи"""
        # Контейнер для розгорнутого вмісту (спочатку прихований)
        self.expanded_frame = ttk.Frame(self.main_frame)
        # Не пакуємо спочатку

        # Створюємо Paned Window для розділення
        self.content_paned = ttk.PanedWindow(self.expanded_frame, orient=tk.HORIZONTAL)
        self.content_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Ліва частина - повний текст та кадри (60%)
        self.create_left_panel()

        # Права частина - AI аналіз (40%)
        self.create_right_panel()

    def create_left_panel(self):
        """Створює ліву панель з текстом та кадрами"""
        left_frame = ttk.Frame(self.content_paned)
        self.content_paned.add(left_frame, weight=6)

        # Повний текст групи
        text_section = ttk.LabelFrame(left_frame, text="📝 Повний текст")
        text_section.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        self.full_text_widget = tk.Text(
            text_section,
            height=6,
            font=("Arial", 11),
            bg="#ffffff",
            relief=tk.FLAT,
            borderwidth=1,
            wrap=tk.WORD
        )

        text_scrollbar = ttk.Scrollbar(text_section, orient="vertical",
                                       command=self.full_text_widget.yview)
        self.full_text_widget.configure(yscrollcommand=text_scrollbar.set)

        self.full_text_widget.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        text_scrollbar.pack(side="right", fill="y", pady=5)

        # Вставляємо повний текст
        self.full_text_widget.insert(tk.END, self.group_data['combined_text'])
        self.full_text_widget.config(state=tk.DISABLED)

        # Секція кадрів
        frames_section = ttk.LabelFrame(left_frame, text="🖼️ Кадри з відео")
        frames_section.pack(fill=tk.BOTH, expand=True)

        # Створюємо переглядач кадрів
        self.frame_viewer = FrameViewer(frames_section)

        # Завантажуємо кадри якщо є
        frames_data = self.group_data.get('frames', [])
        if frames_data:
            self.frame_viewer.load_frames(frames_data)

    def create_right_panel(self):
        """Створює праву панель з AI аналізом"""
        right_frame = ttk.Frame(self.content_paned)
        self.content_paned.add(right_frame, weight=4)

        # Створюємо панель AI аналізу
        self.ai_panel = AIAnalysisPanel(right_frame, self.ai_manager, self.group_data)
        self.ai_panel.video_filename = self.video_filename  # Передаємо назву відео

    def toggle_expansion(self):
        """Перемикає розгортання/згортання групи"""
        if self.is_expanded:
            self.collapse_group()
        else:
            self.expand_group()

    def expand_group(self):
        """Розгортає групу"""
        self.expanded_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        self.expand_button.config(text="🔼 Згорнути")
        self.is_expanded = True

        # Встановлюємо пропорції Paned Window
        self.main_frame.after(100, lambda: self.content_paned.sashpos(0, 400))

    def collapse_group(self):
        """Згортає групу"""
        self.expanded_frame.pack_forget()
        self.expand_button.config(text="🔽 Детальніше")
        self.is_expanded = False

    def play_group_video(self):
        """Відтворює відео з початку групи"""
        try:
            import subprocess
            from pathlib import Path

            video_path = None

            # Пошук відео файлу
            try:
                from processing.database_manager import DatabaseManager
                db_manager = DatabaseManager()
                videos = db_manager.get_all_videos()
                for video in videos:
                    if video['filename'] == self.video_filename:
                        video_path = video['filepath']
                        break
            except:
                videos_dir = Path("videos")
                potential_path = videos_dir / self.video_filename
                if potential_path.exists():
                    video_path = str(potential_path)

            if not video_path:
                messagebox.showwarning("Помилка", "Відео файл не знайдено")
                return

            start_time = self.group_data['group_start_time']
            end_time = self.group_data['group_end_time']

            # Форматуємо час для повідомлення
            time_range = format_time_range(start_time, end_time)

            # Спроба запуску різних плеєрів
            players = [
                (['vlc', video_path, f'--start-time={start_time}', f'--stop-time={end_time}'], "VLC"),
                (['mpv', video_path, f'--start={start_time}', f'--end={end_time}'], "MPV"),
                (['ffplay', video_path, '-ss', str(start_time), '-t', str(end_time - start_time)], "FFplay")
            ]

            for cmd, name in players:
                try:
                    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    self.show_temporary_message(f"✅ {name} відкрито: {time_range}")
                    return
                except FileNotFoundError:
                    continue

            # Стандартний плеєр
            try:
                import os
                os.startfile(video_path)
                self.show_temporary_message(f"✅ Відкрито (перемотайте на {format_time(start_time)})")
            except:
                messagebox.showerror("Помилка", "Не вдалося відкрити відео")

        except Exception as e:
            self.logger.error(f"Помилка відтворення відео: {e}")
            messagebox.showerror("Помилка", f"Помилка відтворення: {e}")

    def copy_group_text(self):
        """Копіює текст групи з форматуванням"""
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")

            # Форматуємо інформацію про групу
            start_time = self.group_data['group_start_time']
            end_time = self.group_data['group_end_time']
            duration = self.group_data['group_duration']

            time_range = format_time_range(start_time, end_time)
            duration_text = format_duration(duration)

            text_to_copy = f"[{timestamp}] {self.video_filename}\n"
            text_to_copy += f"📦 Група {self.group_index + 1}\n"
            text_to_copy += f"🕐 Час: {time_range} (тривалість: {duration_text})\n"
            text_to_copy += f"📊 Складність: {self.group_data.get('difficulty_level', 'intermediate')}\n"
            text_to_copy += f"📝 Слів: {self.group_data.get('word_count', 0)}, "
            text_to_copy += f"Сегментів: {self.group_data.get('segments_count', 0)}\n\n"
            text_to_copy += f"🇬🇧 Текст:\n{self.group_data['combined_text']}\n"
            text_to_copy += "─" * 60

            self.main_frame.clipboard_clear()
            self.main_frame.clipboard_append(text_to_copy)

            start_time_short = format_time(start_time, short=True)
            self.show_temporary_message(f"✅ Скопійовано групу ({start_time_short})")

        except Exception as e:
            self.logger.error(f"Помилка копіювання: {e}")

    def show_temporary_message(self, message: str, duration: int = 3000):
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
            self.main_frame.after(duration, self.hide_temporary_message)

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

    def on_group_selected(self, event=None):
        """Обробляє вибір групи"""
        try:
            if self.on_group_click:
                self.on_group_click(self.group_data, self.video_filename)

            # Автоматично розгортаємо якщо згорнуто
            if not self.is_expanded:
                self.expand_group()

        except Exception as e:
            self.logger.error(f"Помилка вибору групи: {e}")

    def destroy(self):
        """Безпечне знищення віджета"""
        try:
            self.is_destroyed = True

            if hasattr(self, 'main_frame') and self.main_frame.winfo_exists():
                self.main_frame.destroy()

        except Exception as e:
            self.logger.error(f"Помилка знищення віджета групи: {e}")


# Приклад використання та тестування
if __name__ == "__main__":
    """Тестування EnhancedGroupWidget"""

    import json

    # Тестові дані групи
    test_group_data = {
        'id': 1,
        'group_index': 0,
        'group_start_time': 78.5,
        'group_end_time': 125.2,
        'group_duration': 46.7,
        'segments_count': 3,
        'combined_text': "You're finally awake! You were trying to cross the border, right? Walked right into that Imperial ambush, same as us, and that thief over there.",
        'word_count': 28,
        'difficulty_level': 'intermediate',
        'content_analysis': {
            'question_count': 1,
            'exclamation_count': 1,
            'long_sentences': 1
        },
        'frames': [
            {
                'timestamp': 80.0,
                'frame_path': 'processed/frames/test_frame_1.jpg',
                'thumbnail_b64': '/9j/4AAQSkZJRgABAQAAAQABAAD...',  # Тестовий base64
                'frame_analysis': {'brightness': 120.5, 'complexity_score': 75.2}
            },
            {
                'timestamp': 100.0,
                'frame_path': 'processed/frames/test_frame_2.jpg',
                'thumbnail_b64': '/9j/4AAQSkZJRgABAQAAAQABAAD...',  # Тестовий base64
                'frame_analysis': {'brightness': 98.3, 'complexity_score': 82.1}
            }
        ]
    }


    # Заглушки для менеджерів
    class DummyAIManager:
        def is_available(self):
            return True

        def analyze_sentence_comprehensive(self, text, context=None):
            return {
                'success': True,
                'analysis': {
                    'translation': 'Ти нарешті прокинувся! Ти намагався перетнути кордон, правда?',
                    'grammar': 'Present Perfect (You\'re = You are), Past Continuous (were trying)',
                    'vocabulary': 'awake - прокинутися, border - кордон, ambush - засідка',
                    'phonetics': 'Складні звуки: /θ/ в "thief", /r/ в "right"',
                    'memorization_tips': 'Запам\'ятайте: "finally" підсилює значення "нарешті"'
                },
                'difficulty_level': 'Intermediate',
                'analysis_type': 'comprehensive'
            }

        def explain_in_context(self, text, context):
            return {
                'success': True,
                'explanation': 'Це початок діалогу, де персонаж звертається до гравця після пробудження. Риторичне питання створює відчуття знайомості.',
                'analysis_type': 'contextual'
            }

        def analyze_vocabulary(self, text):
            return {
                'success': True,
                'vocabulary_analysis': 'Ключові слова включають фразові дієслова та розмовні вирази типові для неформального діалогу.',
                'key_words': [
                    {'word': 'finally', 'complexity': 'medium'},
                    {'word': 'awake', 'complexity': 'low'},
                    {'word': 'border', 'complexity': 'medium'},
                    {'word': 'ambush', 'complexity': 'high'}
                ],
                'analysis_type': 'vocabulary'
            }

        def get_pronunciation_guide(self, text):
            return {
                'success': True,
                'pronunciation_guide': 'Особлива увага звукам /θ/ в "thief" та інтонації питальних речень.',
                'phonetic_info': {
                    'difficult_sounds': ['th', 'r'],
                    'estimated_duration': 4.2
                },
                'analysis_type': 'pronunciation'
            }


    class DummyDataManager:
        def save_user_note(self, **kwargs):
            pass


    # Створюємо тестове вікно
    root = tk.Tk()
    root.title("Тест Enhanced Group Widget")
    root.geometry("1200x800")

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
        text="🎯 ТЕСТ ENHANCED GROUP WIDGET:\n\n"
             "✅ Розумне групування по паузах\n"
             "✅ Відображення кадрів з відео\n"
             "✅ Покращені AI пояснення (4 типи)\n"
             "✅ Натисніть 'Детальніше' для розгортання\n"
             "✅ Тестуйте різні типи AI аналізу\n"
             "✅ Функції відтворення та копіювання",
        font=("Arial", 11),
        justify=tk.LEFT,
        bg="#e8f5e8",
        padx=15,
        pady=15,
        relief=tk.RAISED,
        borderwidth=2
    )
    instructions.pack(fill=tk.X, pady=(0, 15))

    # Створюємо віджет групи
    try:
        group_widget = EnhancedGroupWidget(
            parent_frame=scrollable_frame,
            group_data=test_group_data,
            video_filename="skyrim_intro.mkv",
            group_index=0,
            ai_manager=DummyAIManager(),
            data_manager=DummyDataManager(),
            on_group_click=lambda data, filename: print(f"Вибрано групу: {data['combined_text'][:50]}...")
        )

        print("✅ Enhanced Group Widget створений успішно!")
        print("🎯 Тестуйте функціонал: розгортання, AI аналіз, перегляд кадрів")

    except Exception as e:
        print(f"❌ Помилка створення віджета групи: {e}")
        import traceback

        traceback.print_exc()


    # Прив'язуємо прокрутку
    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


    canvas.bind_all("<MouseWheel>", _on_mousewheel)

    print("🚀 Запуск GUI...")
    root.mainloop()