"""
Database Manager - модуль для управління SQLite базою даних
Зберігає відео, транскрипції та забезпечує швидкий пошук
"""

import sqlite3
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from datetime import datetime

class DatabaseManager:
    """Клас для управління SQLite базою даних проєкту"""
    
    def __init__(self, db_path: str = "processed/database/game_learning.db"):
        """
        Ініціалізація менеджера бази даних
        
        Args:
            db_path: Шлях до файлу бази даних
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Налаштування логування
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Створення бази даних та таблиць
        self._create_tables()

    def _create_tables(self):
        """Створює таблиці в базі даних (ОНОВЛЕНА ВЕРСІЯ)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Існуючі таблиці (videos, transcriptions, segments, bookmarks)
            # ... ваш існуючий код ...
            
            # НОВІ ТАБЛИЦІ ДЛЯ НОТАТОК:
            
            # Таблиця нотаток користувача
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sentence_text TEXT NOT NULL,
                    video_filename TEXT NOT NULL,
                    start_time REAL NOT NULL,
                    note_text TEXT,
                    image_data BLOB,
                    image_filename TEXT,
                    image_width INTEGER,
                    image_height INTEGER,
                    tags TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблиця AI відповідей (якщо не існує)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sentence_hash TEXT NOT NULL,
                    sentence_text TEXT NOT NULL,
                    video_filename TEXT NOT NULL,
                    start_time REAL NOT NULL,
                    end_time REAL NOT NULL,
                    response_type TEXT NOT NULL,
                    ai_response TEXT NOT NULL,
                    ai_client TEXT DEFAULT 'llama3.1',
                    custom_prompt TEXT,
                    is_edited BOOLEAN DEFAULT 0,
                    edited_text TEXT,
                    version INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблиця вставок тексту в нотатки
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS note_inserts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_note_id INTEGER,
                    source_type TEXT NOT NULL,
                    source_text TEXT NOT NULL,
                    video_filename TEXT,
                    sentence_index INTEGER,
                    ai_response_id INTEGER,
                    inserted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_note_id) REFERENCES user_notes (id),
                    FOREIGN KEY (ai_response_id) REFERENCES ai_responses (id)
                )
            """)
            
            # Індекси для швидкого пошуку
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_notes_video ON user_notes(video_filename)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_notes_sentence ON user_notes(sentence_text)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_notes_time ON user_notes(start_time)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_responses_hash ON ai_responses(sentence_hash)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_note_inserts_note ON note_inserts(user_note_id)")
            
            conn.commit()
            self.logger.info("База даних з підтримкою нотаток ініціалізована успішно")

    def save_user_note(self, 
                    sentence_text: str,
                    video_filename: str, 
                    start_time: float,
                    note_text: str = None,
                    image_data: bytes = None,
                    image_filename: str = None,
                    tags: str = None) -> int:
        """
        Зберігає нотатку користувача
        
        Args:
            sentence_text: Текст речення
            video_filename: Назва відео файлу
            start_time: Час початку речення
            note_text: Текст нотатки
            image_data: Дані зображення
            image_filename: Назва файлу зображення
            tags: Теги через кому
            
        Returns:
            ID збереженої нотатки
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Перевіряємо чи існує нотатка
            cursor.execute("""
                SELECT id FROM user_notes 
                WHERE sentence_text = ? AND video_filename = ? AND start_time = ?
            """, (sentence_text, video_filename, start_time))
            
            result = cursor.fetchone()
            
            # Отримуємо розміри зображення якщо є
            image_width = None
            image_height = None
            
            if image_data:
                try:
                    from PIL import Image
                    import io
                    image = Image.open(io.BytesIO(image_data))
                    image_width, image_height = image.size
                except Exception as e:
                    self.logger.warning(f"Не вдалося отримати розміри зображення: {e}")
            
            if result:
                # Оновлюємо існуючу нотатку
                note_id = result[0]
                cursor.execute("""
                    UPDATE user_notes SET
                        note_text = ?,
                        image_data = ?,
                        image_filename = ?,
                        image_width = ?,
                        image_height = ?,
                        tags = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (note_text, image_data, image_filename, image_width, image_height, tags, note_id))
                
            else:
                # Створюємо нову нотатку
                cursor.execute("""
                    INSERT INTO user_notes 
                    (sentence_text, video_filename, start_time, note_text, 
                    image_data, image_filename, image_width, image_height, tags)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (sentence_text, video_filename, start_time, note_text, 
                    image_data, image_filename, image_width, image_height, tags))
                
                note_id = cursor.lastrowid
            
            conn.commit()
            
            self.logger.info(f"Нотатка збережена: ID {note_id}")
            return note_id

    def get_user_note(self, 
                    sentence_text: str,
                    video_filename: str,
                    start_time: float) -> Optional[Dict]:
        """
        Отримує нотатку користувача
        
        Args:
            sentence_text: Текст речення
            video_filename: Назва відео файлу  
            start_time: Час початку речення
            
        Returns:
            Словник з даними нотатки або None
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT note_text, image_data, image_filename, image_width, 
                    image_height, tags, created_at, updated_at
                FROM user_notes
                WHERE sentence_text = ? AND video_filename = ? AND start_time = ?
            """, (sentence_text, video_filename, start_time))
            
            result = cursor.fetchone()
            
            if result:
                return {
                    "note_text": result[0],
                    "image_data": result[1], 
                    "image_filename": result[2],
                    "image_width": result[3],
                    "image_height": result[4],
                    "tags": result[5],
                    "created_at": result[6],
                    "updated_at": result[7]
                }
            
            return None

    def get_all_user_notes(self, video_filename: str = None) -> List[Dict]:
        """
        Отримує всі нотатки користувача
        
        Args:
            video_filename: Фільтр по відео (опціонально)
            
        Returns:
            Список нотаток
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            if video_filename:
                cursor.execute("""
                    SELECT sentence_text, video_filename, start_time, note_text, 
                        tags, created_at, updated_at
                    FROM user_notes
                    WHERE video_filename = ?
                    ORDER BY start_time
                """, (video_filename,))
            else:
                cursor.execute("""
                    SELECT sentence_text, video_filename, start_time, note_text, 
                        tags, created_at, updated_at
                    FROM user_notes
                    ORDER BY video_filename, start_time
                """)
            
            notes = []
            for row in cursor.fetchall():
                notes.append({
                    "sentence_text": row[0],
                    "video_filename": row[1], 
                    "start_time": row[2],
                    "note_text": row[3],
                    "tags": row[4],
                    "created_at": row[5],
                    "updated_at": row[6]
                })
            
            return notes

    def delete_user_note(self, 
                        sentence_text: str,
                        video_filename: str,
                        start_time: float) -> bool:
        """
        Видаляє нотатку користувача
        
        Returns:
            True якщо видалено успішно
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                DELETE FROM user_notes
                WHERE sentence_text = ? AND video_filename = ? AND start_time = ?
            """, (sentence_text, video_filename, start_time))
            
            deleted = cursor.rowcount > 0
            conn.commit()
            
            if deleted:
                self.logger.info("Нотатка видалена")
            
            return deleted

    def search_user_notes(self, query: str, limit: int = 50) -> List[Dict]:
        """
        Пошук в нотатках користувача
        
        Args:
            query: Текст для пошуку
            limit: Максимальна кількість результатів
            
        Returns:
            Список знайдених нотаток
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT sentence_text, video_filename, start_time, note_text, 
                    tags, created_at
                FROM user_notes
                WHERE note_text LIKE ? OR tags LIKE ? OR sentence_text LIKE ?
                ORDER BY updated_at DESC
                LIMIT ?
            """, (f"%{query}%", f"%{query}%", f"%{query}%", limit))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    "sentence_text": row[0],
                    "video_filename": row[1],
                    "start_time": row[2], 
                    "note_text": row[3],
                    "tags": row[4],
                    "created_at": row[5]
                })
            
            self.logger.info(f"Знайдено {len(results)} нотаток для '{query}'")
            return results

    def get_notes_statistics(self) -> Dict:
        """
        Отримує статистику нотаток
        
        Returns:
            Словник зі статистикою
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Загальна кількість нотаток
            cursor.execute("SELECT COUNT(*) FROM user_notes")
            total_notes = cursor.fetchone()[0]
            
            # Нотатки з текстом
            cursor.execute("SELECT COUNT(*) FROM user_notes WHERE note_text IS NOT NULL AND note_text != ''")
            notes_with_text = cursor.fetchone()[0]
            
            # Нотатки з зображеннями
            cursor.execute("SELECT COUNT(*) FROM user_notes WHERE image_data IS NOT NULL")
            notes_with_images = cursor.fetchone()[0]
            
            # Нотатки з тегами
            cursor.execute("SELECT COUNT(*) FROM user_notes WHERE tags IS NOT NULL AND tags != ''")
            notes_with_tags = cursor.fetchone()[0]
            
            # Популярні теги
            cursor.execute("""
                SELECT tags, COUNT(*) as count
                FROM user_notes 
                WHERE tags IS NOT NULL AND tags != ''
                GROUP BY tags
                ORDER BY count DESC
                LIMIT 10
            """)
            popular_tags = cursor.fetchall()
            
            # Нотатки по відео
            cursor.execute("""
                SELECT video_filename, COUNT(*) as count
                FROM user_notes
                GROUP BY video_filename
                ORDER BY count DESC
                LIMIT 10
            """)
            notes_by_video = cursor.fetchall()
            
            return {
                "total_notes": total_notes,
                "notes_with_text": notes_with_text,
                "notes_with_images": notes_with_images, 
                "notes_with_tags": notes_with_tags,
                "popular_tags": popular_tags,
                "notes_by_video": notes_by_video
            }

    def save_note_insert(self, 
                        user_note_id: int,
                        source_type: str,
                        source_text: str,
                        video_filename: str = None,
                        sentence_index: int = None,
                        ai_response_id: int = None) -> int:
        """
        Зберігає інформацію про вставку тексту в нотатку
        
        Returns:
            ID створеного запису
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO note_inserts 
                (user_note_id, source_type, source_text, video_filename, 
                sentence_index, ai_response_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_note_id, source_type, source_text, video_filename, 
                sentence_index, ai_response_id))
            
            insert_id = cursor.lastrowid
            conn.commit()
            
            self.logger.debug(f"Вставка тексту збережена: ID {insert_id}")
            return insert_id

    def get_note_inserts(self, user_note_id: int) -> List[Dict]:
        """
        Отримує всі вставки для конкретної нотатки
        
        Returns:
            Список вставок
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT source_type, source_text, video_filename, 
                    sentence_index, inserted_at
                FROM note_inserts
                WHERE user_note_id = ?
                ORDER BY inserted_at
            """, (user_note_id,))
            
            inserts = []
            for row in cursor.fetchall():
                inserts.append({
                    "source_type": row[0],
                    "source_text": row[1],
                    "video_filename": row[2],
                    "sentence_index": row[3], 
                    "inserted_at": row[4]
                })
            
            return inserts
    
    def add_video(self, 
                  filename: str, 
                  filepath: str, 
                  duration: Optional[float] = None,
                  file_size: Optional[int] = None) -> int:
        """
        Додає відео в базу даних
        
        Args:
            filename: Назва файлу
            filepath: Повний шлях до файлу
            duration: Тривалість в секундах
            file_size: Розмір файлу в байтах
            
        Returns:
            ID створеного запису
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            try:
                cursor.execute("""
                    INSERT INTO videos (filename, filepath, duration, file_size)
                    VALUES (?, ?, ?, ?)
                """, (filename, filepath, duration, file_size))
                
                video_id = cursor.lastrowid
                conn.commit()
                
                self.logger.info(f"Відео додано в БД: {filename} (ID: {video_id})")
                return video_id
                
            except sqlite3.IntegrityError:
                # Відео вже існує, повертаємо його ID
                cursor.execute("SELECT id FROM videos WHERE filename = ?", (filename,))
                result = cursor.fetchone()
                return result[0] if result else None
    
    def add_transcription(self, 
                         video_id: int,
                         transcription_data: Dict) -> int:
        """
        Додає транскрипцію в базу даних
        
        Args:
            video_id: ID відео
            transcription_data: Дані транскрипції з Whisper
            
        Returns:
            ID створеної транскрипції
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Додаємо основну транскрипцію
            cursor.execute("""
                INSERT INTO transcriptions 
                (video_id, audio_path, language, model_size, full_text)
                VALUES (?, ?, ?, ?, ?)
            """, (
                video_id,
                transcription_data.get("audio_file"),
                transcription_data.get("language"),
                transcription_data.get("model_size"),
                transcription_data.get("full_text")
            ))
            
            transcription_id = cursor.lastrowid
            
            # Додаємо сегменти
            for segment in transcription_data.get("segments", []):
                cursor.execute("""
                    INSERT INTO segments 
                    (transcription_id, start_time, end_time, text, confidence)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    transcription_id,
                    segment["start"],
                    segment["end"],
                    segment["text"],
                    segment.get("avg_logprob", 0.0)
                ))
            
            # Оновлюємо статус відео
            cursor.execute("""
                UPDATE videos 
                SET status = 'processed', processed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (video_id,))
            
            conn.commit()
            
            self.logger.info(f"Транскрипція додана: {len(transcription_data.get('segments', []))} сегментів")
            return transcription_id
    
    def search_text(self, query: str, limit: int = 50) -> List[Dict]:
        """
        Пошук тексту в транскрипціях
        
        Args:
            query: Текст для пошуку
            limit: Максимальна кількість результатів
            
        Returns:
            Список знайдених сегментів з інформацією про відео
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    v.filename,
                    v.filepath,
                    s.start_time,
                    s.end_time,
                    s.text,
                    s.confidence,
                    t.language
                FROM segments s
                JOIN transcriptions t ON s.transcription_id = t.id
                JOIN videos v ON t.video_id = v.id
                WHERE s.text LIKE ?
                ORDER BY s.confidence DESC, v.filename
                LIMIT ?
            """, (f"%{query}%", limit))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    "filename": row[0],
                    "filepath": row[1],
                    "start_time": row[2],
                    "end_time": row[3],
                    "text": row[4],
                    "confidence": row[5],
                    "language": row[6]
                })
            
            self.logger.info(f"Знайдено {len(results)} результатів для '{query}'")
            return results
    
    def get_video_segments(self, video_id: int) -> List[Dict]:
        """
        Отримує всі сегменти для конкретного відео
        
        Args:
            video_id: ID відео
            
        Returns:
            Список всіх сегментів відео
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    s.start_time,
                    s.end_time,
                    s.text,
                    s.confidence
                FROM segments s
                JOIN transcriptions t ON s.transcription_id = t.id
                WHERE t.video_id = ?
                ORDER BY s.start_time
            """, (video_id,))
            
            segments = []
            for row in cursor.fetchall():
                segments.append({
                    "start_time": row[0],
                    "end_time": row[1],
                    "text": row[2],
                    "confidence": row[3]
                })
            
            return segments
    
    def add_bookmark(self, 
                    video_id: int,
                    start_time: float,
                    end_time: Optional[float] = None,
                    title: Optional[str] = None,
                    description: Optional[str] = None,
                    tags: Optional[str] = None) -> int:
        """
        Додає закладку (улюблений момент)
        
        Args:
            video_id: ID відео
            start_time: Час початку в секундах
            end_time: Час кінця в секундах
            title: Назва закладки
            description: Опис
            tags: Теги (через кому)
            
        Returns:
            ID створеної закладки
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO bookmarks 
                (video_id, start_time, end_time, title, description, tags)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (video_id, start_time, end_time, title, description, tags))
            
            bookmark_id = cursor.lastrowid
            conn.commit()
            
            self.logger.info(f"Закладка додана: {title or 'Без назви'}")
            return bookmark_id
    
    def get_all_videos(self) -> List[Dict]:
        """
        Отримує список всіх відео
        
        Returns:
            Список відео з інформацією
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    id, filename, filepath, duration, file_size, 
                    status, created_at, processed_at
                FROM videos
                ORDER BY created_at DESC
            """)
            
            videos = []
            for row in cursor.fetchall():
                videos.append({
                    "id": row[0],
                    "filename": row[1],
                    "filepath": row[2],
                    "duration": row[3],
                    "file_size": row[4],
                    "status": row[5],
                    "created_at": row[6],
                    "processed_at": row[7]
                })
            
            return videos
    
    def get_database_stats(self) -> Dict:
        """
        Отримує статистику бази даних
        
        Returns:
            Словник зі статистикою
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Підрахунок відео
            cursor.execute("SELECT COUNT(*) FROM videos")
            total_videos = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM videos WHERE status = 'processed'")
            processed_videos = cursor.fetchone()[0]
            
            # Підрахунок сегментів
            cursor.execute("SELECT COUNT(*) FROM segments")
            total_segments = cursor.fetchone()[0]
            
            # Підрахунок закладок
            cursor.execute("SELECT COUNT(*) FROM bookmarks")
            total_bookmarks = cursor.fetchone()[0]
            
            # Загальна тривалість
            cursor.execute("SELECT SUM(duration) FROM videos WHERE duration IS NOT NULL")
            total_duration = cursor.fetchone()[0] or 0
            
            return {
                "total_videos": total_videos,
                "processed_videos": processed_videos,
                "pending_videos": total_videos - processed_videos,
                "total_segments": total_segments,
                "total_bookmarks": total_bookmarks,
                "total_duration_minutes": round(total_duration / 60, 1) if total_duration else 0
            }


# Приклад використання
if __name__ == "__main__":
    # Створюємо менеджер БД
    db = DatabaseManager()
    
    # Додаємо відео
    video_id = db.add_video(
        filename="test_video.mkv",
        filepath="videos/test_video.mkv",
        duration=120.5,
        file_size=1024000
    )
    
    # Симуляція транскрипції
    transcription_data = {
        "audio_file": "processed/audio/test_video.wav",
        "language": "en",
        "model_size": "tiny",
        "full_text": "Hello world, this is a test transcription.",
        "segments": [
            {"start": 0.0, "end": 5.0, "text": "Hello world", "avg_logprob": -0.5},
            {"start": 5.0, "end": 10.0, "text": "this is a test", "avg_logprob": -0.3}
        ]
    }
    
    # Додаємо транскрипцію
    transcription_id = db.add_transcription(video_id, transcription_data)
    
    # Пошук
    results = db.search_text("hello")
    print(f"Знайдено: {len(results)} результатів")
    
    # Статистика
    stats = db.get_database_stats()
    print(f"Статистика: {stats}")