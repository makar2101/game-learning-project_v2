"""
Notes Panel - права панель для нотаток користувача
Підтримує текстові замітки, фотографії та теги
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
import io
import logging
from typing import Optional, Dict, Callable
from PIL import Image, ImageTk
import os

class NotesPanel:
    """Панель нотаток та зображень"""
    
    def __init__(self, parent_frame: ttk.Frame, data_manager, on_note_changed: Optional[Callable] = None):
        """
        Ініціалізація панелі нотаток
        
        Args:
            parent_frame: Батьківський фрейм
            data_manager: Менеджер даних
            on_note_changed: Callback при зміні нотатки
        """
        self.parent = parent_frame
        self.data_manager = data_manager
        self.on_note_changed = on_note_changed
        
        self.logger = logging.getLogger(__name__)
        
        # Поточні дані
        self.current_sentence = None
        self.current_video = None
        self.current_image = None
        self.current_image_path = None
        
        # Створюємо інтерфейс
        self.create_widgets()
        
        # Прив'язуємо події автозбереження
        self.setup_autosave()
    
    def create_widgets(self):
        """Створює віджети панелі нотаток"""
        # Заголовок панелі
        header_frame = ttk.Frame(self.parent)
        header_frame.pack(fill=tk.X, padx=5, pady=(5, 0))
        
        title_label = ttk.Label(header_frame, text="📝 Нотатки", font=("Arial", 12, "bold"))
        title_label.pack(side=tk.LEFT)
        
        # Кнопка очищення
        clear_btn = ttk.Button(header_frame, text="🗑️", width=3, command=self.clear_notes)
        clear_btn.pack(side=tk.RIGHT)
        
        # Область з прокруткою для всього вмісту
        self.create_scrollable_area()
        
        # Текстова нотатка
        self.create_text_note_section()
        
        # Зображення
        self.create_image_section()
        
        # Теги
        self.create_tags_section()
        
        # Статистика
        self.create_stats_section()
    
    def create_scrollable_area(self):
        """Створює область з прокруткою"""
        # Canvas для прокрутки
        self.canvas = tk.Canvas(self.parent, bg="white", highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.parent, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Прив'язуємо колесо миші
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
        self.canvas.pack(side="left", fill="both", expand=True, padx=(5, 0), pady=5)
        self.scrollbar.pack(side="right", fill="y", pady=5)
    
    def _on_mousewheel(self, event):
        """Обробка прокрутки мишкою"""
        if self.canvas.winfo_exists():
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    
    def create_text_note_section(self):
        """Створює секцію текстових нотаток"""
        # Заголовок
        text_frame = ttk.LabelFrame(self.scrollable_frame, text="Текстова нотатка")
        text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Текстове поле з прокруткою
        self.notes_text = ScrolledText(
            text_frame, 
            height=8, 
            wrap=tk.WORD,
            font=("Arial", 10),
            bg="#fffef7",  # Легко жовтуватий фон
            relief=tk.FLAT,
            borderwidth=1
        )
        self.notes_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Плейсхолдер
        self.notes_placeholder = "Введіть ваші нотатки тут...\n\n💡 Поради:\n• Записуйте незрозумілі слова\n• Помічайте граматичні особливості\n• Додавайте власні приклади"
        self.show_placeholder()
        
        # Кнопки для тексту
        text_buttons_frame = ttk.Frame(text_frame)
        text_buttons_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        
        ttk.Button(text_buttons_frame, text="💾 Зберегти", command=self.save_notes).pack(side=tk.LEFT, padx=2)
        ttk.Button(text_buttons_frame, text="📋 Копіювати", command=self.copy_notes).pack(side=tk.LEFT, padx=2)
        ttk.Button(text_buttons_frame, text="🔤 Форматувати", command=self.format_notes).pack(side=tk.LEFT, padx=2)
    
    def create_image_section(self):
        """Створює секцію зображень"""
        # Заголовок
        image_frame = ttk.LabelFrame(self.scrollable_frame, text="Зображення")
        image_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Кнопки для зображень
        image_buttons_frame = ttk.Frame(image_frame)
        image_buttons_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(image_buttons_frame, text="📁 Завантажити", command=self.load_image).pack(side=tk.LEFT, padx=2)
        ttk.Button(image_buttons_frame, text="📷 Скріншот", command=self.take_screenshot).pack(side=tk.LEFT, padx=2)
        ttk.Button(image_buttons_frame, text="🗑️ Видалити", command=self.remove_image).pack(side=tk.RIGHT, padx=2)
        
        # Контейнер для зображення
        self.image_container = ttk.Frame(image_frame)
        self.image_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Лейбл для зображення
        self.image_label = ttk.Label(self.image_container, text="📷 Зображення не завантажено")
        self.image_label.pack(expand=True)
        
        # Інформація про зображення
        self.image_info_label = ttk.Label(image_frame, text="", font=("Arial", 8))
        self.image_info_label.pack(padx=5, pady=(0, 5))
    
    def create_tags_section(self):
        """Створює секцію тегів"""
        tags_frame = ttk.LabelFrame(self.scrollable_frame, text="Теги")
        tags_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Поле для введення тегів
        tags_input_frame = ttk.Frame(tags_frame)
        tags_input_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(tags_input_frame, text="Теги:").pack(side=tk.LEFT)
        
        self.tags_var = tk.StringVar()
        self.tags_entry = ttk.Entry(tags_input_frame, textvariable=self.tags_var, font=("Arial", 9))
        self.tags_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 2))
        
        ttk.Button(tags_input_frame, text="➕", width=3, command=self.add_tag).pack(side=tk.RIGHT)
        
        # Популярні теги
        popular_tags_frame = ttk.Frame(tags_frame)
        popular_tags_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        
        ttk.Label(popular_tags_frame, text="Швидкі теги:", font=("Arial", 8)).pack(anchor=tk.W)
        
        self.quick_tags_frame = ttk.Frame(popular_tags_frame)
        self.quick_tags_frame.pack(fill=tk.X, pady=2)
        
        # Додаємо популярні теги
        popular_tags = ["#важливо", "#граматика", "#нове_слово", "#ідіома", "#помилка", "#повторити"]
        for tag in popular_tags:
            btn = ttk.Button(
                self.quick_tags_frame, 
                text=tag, 
                command=lambda t=tag: self.add_quick_tag(t)
            )
            btn.pack(side=tk.LEFT, padx=1, pady=1)
    
    def create_stats_section(self):
        """Створює секцію статистики"""
        stats_frame = ttk.LabelFrame(self.scrollable_frame, text="Статистика")
        stats_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.stats_label = ttk.Label(
            stats_frame, 
            text="Нотаток: 0 | Зображень: 0 | Тегів: 0",
            font=("Arial", 8)
        )
        self.stats_label.pack(padx=5, pady=5)
    
    def setup_autosave(self):
        """Налаштовує автозбереження"""
        # Автозбереження при зміні тексту
        self.notes_text.bind('<KeyRelease>', self.on_text_changed)
        self.notes_text.bind('<FocusOut>', self.save_notes)
        
        # Автозбереження тегів
        self.tags_entry.bind('<Return>', self.save_notes)
        self.tags_entry.bind('<FocusOut>', self.save_notes)
        
        # Обробка плейсхолдера
        self.notes_text.bind('<FocusIn>', self.on_text_focus_in)
        self.notes_text.bind('<FocusOut>', self.on_text_focus_out)
    
    def show_placeholder(self):
        """Показує плейсхолдер"""
        self.notes_text.delete(1.0, tk.END)
        self.notes_text.insert(1.0, self.notes_placeholder)
        self.notes_text.config(fg="gray")
    
    def hide_placeholder(self):
        """Приховує плейсхолдер"""
        if self.notes_text.get(1.0, tk.END).strip() == self.notes_placeholder.strip():
            self.notes_text.delete(1.0, tk.END)
        self.notes_text.config(fg="black")
    
    def on_text_focus_in(self, event):
        """Обробка фокусу на тексті"""
        self.hide_placeholder()
    
    def on_text_focus_out(self, event):
        """Обробка втрати фокусу"""
        if not self.notes_text.get(1.0, tk.END).strip():
            self.show_placeholder()
    
    def on_text_changed(self, event):
        """Обробка зміни тексту"""
        # Автозбереження через 2 секунди після останньої зміни
        if hasattr(self, '_save_after_id'):
            self.notes_text.after_cancel(self._save_after_id)
        
        self._save_after_id = self.notes_text.after(2000, self.save_notes)
    
    def set_sentence_context(self, sentence_data: Dict, video_filename: str):
        """
        Встановлює контекст речення для нотаток
        
        Args:
            sentence_data: Дані про речення
            video_filename: Назва відео файлу
        """
        self.current_sentence = sentence_data
        self.current_video = video_filename
        
        # Завантажуємо існуючі нотатки
        self.load_existing_notes()
    
    def load_existing_notes(self):
        """Завантажує існуючі нотатки для поточного речення"""
        if not self.current_sentence or not self.current_video:
            return
        
        try:
            # Отримуємо нотатки з БД
            note_data = self.data_manager.get_user_note(
                sentence_text=self.current_sentence['text'],
                video_filename=self.current_video,
                start_time=self.current_sentence['start_time']
            )
            
            if note_data:
                # Завантажуємо текст
                if note_data['note_text']:
                    self.notes_text.delete(1.0, tk.END)
                    self.notes_text.insert(1.0, note_data['note_text'])
                    self.notes_text.config(fg="black")
                else:
                    self.show_placeholder()
                
                # Завантажуємо зображення
                if note_data['image_data']:
                    self.load_image_from_data(note_data['image_data'])
                    
                    # Показуємо інформацію про зображення
                    if note_data['image_width'] and note_data['image_height']:
                        info_text = f"📏 {note_data['image_width']}×{note_data['image_height']}"
                        if note_data['image_filename']:
                            info_text += f" | {note_data['image_filename']}"
                        self.image_info_label.config(text=info_text)
                
                # Завантажуємо теги
                if note_data['tags']:
                    self.tags_var.set(note_data['tags'])
            else:
                # Очищуємо поля якщо немає нотаток
                self.clear_notes()
                
        except Exception as e:
            self.logger.error(f"Помилка завантаження нотаток: {e}")
    
    def save_notes(self):
        """Зберігає поточні нотатки"""
        if not self.current_sentence or not self.current_video:
            return
        
        try:
            # Отримуємо текст нотатки
            note_text = self.notes_text.get(1.0, tk.END).strip()
            if note_text == self.notes_placeholder.strip():
                note_text = ""
            
            # Отримуємо теги
            tags = self.tags_var.get().strip()
            
            # Отримуємо дані зображення
            image_data = None
            image_filename = None
            
            if self.current_image:
                # Конвертуємо PIL Image в bytes
                img_byte_arr = io.BytesIO()
                self.current_image.save(img_byte_arr, format='PNG')
                image_data = img_byte_arr.getvalue()
                image_filename = self.current_image_path or "uploaded_image.png"
            
            # Зберігаємо в БД
            self.data_manager.save_user_note(
                sentence_text=self.current_sentence['text'],
                video_filename=self.current_video,
                start_time=self.current_sentence['start_time'],
                note_text=note_text,
                image_data=image_data,
                image_filename=image_filename,
                tags=tags
            )
            
            # Викликаємо callback
            if self.on_note_changed:
                self.on_note_changed()
            
            # Оновлюємо статистику
            self.update_stats()
            
        except Exception as e:
            self.logger.error(f"Помилка збереження нотаток: {e}")
            messagebox.showerror("Помилка", f"Не вдалося зберегти нотатки: {e}")
    
    def load_image(self):
        """Завантажує зображення з файлу"""
        try:
            file_path = filedialog.askopenfilename(
                title="Виберіть зображення",
                filetypes=[
                    ("Зображення", "*.png *.jpg *.jpeg *.gif *.bmp"),
                    ("PNG файли", "*.png"),
                    ("JPEG файли", "*.jpg *.jpeg"),
                    ("Всі файли", "*.*")
                ]
            )
            
            if file_path:
                # Завантажуємо зображення
                image = Image.open(file_path)
                
                # Обмежуємо розмір для відображення
                display_image = self.resize_image_for_display(image)
                
                # Зберігаємо оригінал для БД
                self.current_image = image
                self.current_image_path = os.path.basename(file_path)
                
                # Показуємо зображення
                self.display_image(display_image)
                
                # Зберігаємо автоматично
                self.save_notes()
                
        except Exception as e:
            self.logger.error(f"Помилка завантаження зображення: {e}")
            messagebox.showerror("Помилка", f"Не вдалося завантажити зображення: {e}")
    
    def load_image_from_data(self, image_data: bytes):
        """Завантажує зображення з байтових даних"""
        try:
            image = Image.open(io.BytesIO(image_data))
            display_image = self.resize_image_for_display(image)
            
            self.current_image = image
            self.display_image(display_image)
            
        except Exception as e:
            self.logger.error(f"Помилка завантаження зображення з даних: {e}")
    
    def resize_image_for_display(self, image: Image.Image, max_width: int = 250, max_height: int = 200) -> Image.Image:
        """Змінює розмір зображення для відображення"""
        # Обчислюємо новий розмір зберігаючи пропорції
        ratio = min(max_width / image.width, max_height / image.height)
        
        if ratio < 1:
            new_width = int(image.width * ratio)
            new_height = int(image.height * ratio)
            return image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        return image
    
    def display_image(self, image: Image.Image):
        """Відображає зображення в інтерфейсі"""
        try:
            # Конвертуємо в PhotoImage
            photo = ImageTk.PhotoImage(image)
            
            # Оновлюємо лейбл
            self.image_label.config(image=photo, text="")
            self.image_label.image = photo  # Зберігаємо посилання
            
            # Додаємо можливість збільшення по кліку
            self.image_label.bind('<Double-Button-1>', self.zoom_image)
            
        except Exception as e:
            self.logger.error(f"Помилка відображення зображення: {e}")
    
    def zoom_image(self, event):
        """Відкриває зображення в повному розмірі"""
        if self.current_image:
            # Створюємо нове вікно для зображення
            zoom_window = tk.Toplevel(self.parent)
            zoom_window.title("Збільшене зображення")
            zoom_window.geometry("800x600")
            
            # Змінюємо розмір для великого вікна
            display_image = self.resize_image_for_display(self.current_image, 750, 550)
            photo = ImageTk.PhotoImage(display_image)
            
            label = ttk.Label(zoom_window, image=photo)
            label.image = photo
            label.pack(expand=True)
    
    def take_screenshot(self):
        """Робить скріншот екрану"""
        try:
            import tkinter.simpledialog as simpledialog
            
            # Просимо користувача вибрати область (заглушка)
            response = messagebox.askyesno(
                "Скріншот", 
                "Функція скріншотів буде додана в наступних версіях.\nПоки що використовуйте 'Завантажити' для додавання зображень."
            )
            
        except Exception as e:
            self.logger.error(f"Помилка скріншота: {e}")
    
    def remove_image(self):
        """Видаляє поточне зображення"""
        if self.current_image:
            if messagebox.askyesno("Підтвердження", "Видалити зображення?"):
                self.current_image = None
                self.current_image_path = None
                
                # Очищуємо відображення
                self.image_label.config(image="", text="📷 Зображення не завантажено")
                self.image_label.image = None
                self.image_info_label.config(text="")
                
                # Зберігаємо зміни
                self.save_notes()
    
    def add_tag(self):
        """Додає новий тег"""
        current_tags = self.tags_var.get().strip()
        new_tag = "#новий_тег"
        
        if current_tags:
            if new_tag not in current_tags:
                self.tags_var.set(f"{current_tags}, {new_tag}")
        else:
            self.tags_var.set(new_tag)
        
        # Фокус на поле тегів для редагування
        self.tags_entry.focus_set()
        self.tags_entry.selection_range(len(current_tags) + 2, tk.END)
    
    def add_quick_tag(self, tag: str):
        """Додає швидкий тег"""
        current_tags = self.tags_var.get().strip()
        
        if current_tags:
            if tag not in current_tags:
                self.tags_var.set(f"{current_tags}, {tag}")
        else:
            self.tags_var.set(tag)
        
        # Автозбереження
        self.save_notes()
    
    def copy_notes(self):
        """Копіює нотатки в буфер обміну"""
        try:
            note_text = self.notes_text.get(1.0, tk.END).strip()
            if note_text and note_text != self.notes_placeholder.strip():
                self.parent.clipboard_clear()
                self.parent.clipboard_append(note_text)
                messagebox.showinfo("Успіх", "Нотатки скопійовані в буфер обміну")
            else:
                messagebox.showwarning("Попередження", "Немає тексту для копіювання")
                
        except Exception as e:
            self.logger.error(f"Помилка копіювання: {e}")
    
    def format_notes(self):
        """Форматує нотатки"""
        try:
            note_text = self.notes_text.get(1.0, tk.END).strip()
            if note_text and note_text != self.notes_placeholder.strip():
                # Простий автоформат
                formatted_text = note_text.replace(". ", ".\n• ")
                formatted_text = "• " + formatted_text if not formatted_text.startswith("•") else formatted_text
                
                self.notes_text.delete(1.0, tk.END)
                self.notes_text.insert(1.0, formatted_text)
                
        except Exception as e:
            self.logger.error(f"Помилка форматування: {e}")
    
    def clear_notes(self):
        """Очищує всі нотатки"""
        self.show_placeholder()
        self.current_image = None
        self.current_image_path = None
        self.tags_var.set("")
        
        # Очищуємо зображення
        self.image_label.config(image="", text="📷 Зображення не завантажено")
        self.image_label.image = None
        self.image_info_label.config(text="")
    
    def update_stats(self):
        """Оновлює статистику"""
        try:
            # Тут можна додати підрахунок статистики з БД
            stats_text = "Нотаток: ? | Зображень: ? | Тегів: ?"
            self.stats_label.config(text=stats_text)
        except Exception as e:
            self.logger.error(f"Помилка оновлення статистики: {e}")

    def insert_text_to_notes(self, text_content: str, source_info: Dict):
        """
        Вставляє текст в нотатки з інформацією про джерело
        
        Args:
            text_content: Текст для вставки
            source_info: Інформація про джерело (тип, речення, відео і т.д.)
        """
        try:
            # Приховуємо плейсхолдер якщо він показується
            current_text = self.notes_text.get(1.0, tk.END).strip()
            if current_text == self.notes_placeholder.strip():
                self.notes_text.delete(1.0, tk.END)
                self.notes_text.config(fg="black")
            
            # Вставляємо новий текст в кінець
            self.notes_text.insert(tk.END, text_content)
            
            # Прокручуємо донизу щоб побачити вставлений текст
            self.notes_text.see(tk.END)
            
            # Автоматично зберігаємо
            self.save_notes()
            
            # Зберігаємо інформацію про вставку в БД
            self.save_note_insert(source_info, text_content)
            
            self.logger.info(f"Текст вставлено в нотатки з джерела: {source_info['source_type']}")
            
        except Exception as e:
            self.logger.error(f"Помилка вставки тексту в нотатки: {e}")

    def save_note_insert(self, source_info: Dict, text_content: str):
        """Зберігає інформацію про вставку тексту в БД"""
        try:
            if not self.current_sentence or not self.current_video:
                return
            
            db_path = Path("processed/database/game_learning.db")
            
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                
                # Знаходимо або створюємо нотатку
                cursor.execute("""
                    SELECT id FROM notes 
                    WHERE video_filename = ? AND sentence_text = ? AND sentence_start_time = ?
                """, (
                    self.current_video,
                    self.current_sentence['text'],
                    self.current_sentence['start_time']
                ))
                
                result = cursor.fetchone()
                
                if result:
                    note_id = result[0]
                else:
                    # Створюємо нову нотатку
                    cursor.execute("""
                        INSERT INTO notes (video_filename, sentence_text, sentence_start_time, content, note_type)
                        VALUES (?, ?, ?, ?, 'sentence')
                    """, (
                        self.current_video,
                        self.current_sentence['text'], 
                        self.current_sentence['start_time'],
                        "Автоматично створена нотатка"
                    ))
                    note_id = cursor.lastrowid
                
                # Зберігаємо інформацію про вставку
                cursor.execute("""
                    INSERT INTO note_inserts 
                    (note_id, source_type, source_text, video_filename, sentence_index)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    note_id,
                    source_info['source_type'],
                    text_content[:500],  # Обмежуємо довжину
                    source_info.get('video_filename', self.current_video),
                    source_info.get('sentence_index', 0)
                ))
                
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"Помилка збереження вставки: {e}")

    def get_insert_statistics(self) -> Dict:
        """Отримує статистику вставок тексту"""
        try:
            db_path = Path("processed/database/game_learning.db")
            
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                
                # Загальна кількість вставок
                cursor.execute("SELECT COUNT(*) FROM note_inserts")
                total_inserts = cursor.fetchone()[0]
                
                # Вставки по типах
                cursor.execute("""
                    SELECT source_type, COUNT(*) 
                    FROM note_inserts 
                    GROUP BY source_type
                """)
                inserts_by_type = dict(cursor.fetchall())
                
                # Останні вставки
                cursor.execute("""
                    SELECT source_type, inserted_at 
                    FROM note_inserts 
                    ORDER BY inserted_at DESC 
                    LIMIT 5
                """)
                recent_inserts = cursor.fetchall()
                
                return {
                    'total_inserts': total_inserts,
                    'inserts_by_type': inserts_by_type,
                    'recent_inserts': recent_inserts
                }
                
        except Exception as e:
            self.logger.error(f"Помилка отримання статистики: {e}")
            return {'total_inserts': 0, 'inserts_by_type': {}, 'recent_inserts': []}

# Приклад використання
if __name__ == "__main__":
    # Тестування NotesPanel
    root = tk.Tk()
    root.title("Тест Notes Panel")
    root.geometry("400x800")
    
    # Заглушка для data_manager
    class MockDataManager:
        def get_user_note(self, *args, **kwargs):
            return None
        
        def save_user_note(self, *args, **kwargs):
            print("Збережено нотатку:", args, kwargs)
    
    data_manager = MockDataManager()
    
    # Створюємо панель
    frame = ttk.Frame(root)
    frame.pack(fill=tk.BOTH, expand=True)
    
    notes_panel = NotesPanel(frame, data_manager)
    
    # Тестові дані
    test_sentence = {
        'text': "Hello world, this is a test sentence",
        'start_time': 10.5,
        'end_time': 15.0
    }
    
    notes_panel.set_sentence_context(test_sentence, "test_video.mkv")
    
    root.mainloop()