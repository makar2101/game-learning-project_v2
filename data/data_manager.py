"""
Data Manager - управління користувацькими даними, нотатками та збереженням стану
Зберігає AI відповіді, нотатки з фото, налаштування та відстежує зміни
"""

import hashlib
import sqlite3
import json
import logging
import base64
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

class DataManager:
    """Менеджер даних з підтримкою AI відповідей та нотаток"""
    
    def __init__(self, db_path: str = "processed/database/game_learning.db"):
        """Ініціалізація менеджера даних"""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.logger = logging.getLogger(__name__)
        
        # Створюємо таблиці
        self._create_tables()
    
    def _create_tables(self):
        """Створює всі необхідні таблиці"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Таблиця AI відповідей
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
            
            # Таблиця нотаток користувача
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sentence_hash TEXT NOT NULL,
                    video_filename TEXT NOT NULL,
                    sentence_text TEXT NOT NULL,
                    start_time REAL NOT NULL,
                    note_text TEXT,
                    image_data TEXT,
                    image_filename TEXT,
                    image_width INTEGER,
                    image_height INTEGER,
                    tags TEXT,
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
            
            # Таблиця налаштувань UI
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ui_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    setting_key TEXT UNIQUE NOT NULL,
                    setting_value TEXT NOT NULL,
                    setting_type TEXT DEFAULT 'string',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблиця стану обробки відео
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS video_processing_state (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_filename TEXT UNIQUE NOT NULL,
                    video_path TEXT NOT NULL,
                    file_hash TEXT NOT NULL,
                    file_size INTEGER,
                    duration REAL,
                    sentences_extracted INTEGER DEFAULT 0,
                    sentences_with_ai INTEGER DEFAULT 0,
                    processing_completed BOOLEAN DEFAULT FALSE,
                    last_modified TIMESTAMP,
                    last_processed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Індекси для швидкого пошуку
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_responses_hash ON ai_responses(sentence_hash)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_responses_type ON ai_responses(response_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_responses_video ON ai_responses(video_filename)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_notes_hash ON user_notes(sentence_hash)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_notes_video ON user_notes(video_filename)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_note_inserts_note ON note_inserts(user_note_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_video_state_filename ON video_processing_state(video_filename)")
            
            conn.commit()
            self.logger.info("База даних ініціалізована успішно")
    
    def _get_sentence_hash(self, sentence_text: str, video_filename: str, start_time: float) -> str:
        """Генерує унікальний хеш для речення"""
        data = f"{sentence_text}_{video_filename}_{start_time:.2f}"
        return hashlib.md5(data.encode('utf-8')).hexdigest()
    
    def _get_file_hash(self, file_path: str) -> str:
        """Обчислює MD5 хеш файлу"""
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                return ""
            
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            self.logger.error(f"Помилка обчислення хешу файлу {file_path}: {e}")
            return ""
    
    # ====================================================================
    # AI RESPONSES METHODS
    # ====================================================================
    
    def save_ai_response(self, 
                        sentence_text: str,
                        video_filename: str,
                        start_time: float,
                        end_time: float,
                        response_type: str,
                        ai_response: str,
                        ai_client: str = 'llama3.1',
                        custom_prompt: Optional[str] = None) -> int:
        """Зберігає AI відповідь в БД"""
        try:
            sentence_hash = self._get_sentence_hash(sentence_text, video_filename, start_time)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Перевіряємо чи існує відповідь
                cursor.execute("""
                    SELECT id, version FROM ai_responses
                    WHERE sentence_hash = ? AND response_type = ? AND (custom_prompt = ? OR (custom_prompt IS NULL AND ? IS NULL))
                """, (sentence_hash, response_type, custom_prompt, custom_prompt))
                
                result = cursor.fetchone()
                
                if result:
                    # Оновлюємо існуючу відповідь
                    response_id, current_version = result
                    new_version = current_version + 1
                    
                    cursor.execute("""
                        UPDATE ai_responses SET
                            ai_response = ?,
                            ai_client = ?,
                            version = ?,
                            is_edited = 0,
                            edited_text = NULL,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (ai_response, ai_client, new_version, response_id))
                    
                    self.logger.debug(f"AI відповідь оновлена: {response_type} v{new_version}")
                    return response_id
                else:
                    # Створюємо нову відповідь
                    cursor.execute("""
                        INSERT INTO ai_responses 
                        (sentence_hash, sentence_text, video_filename, start_time, end_time,
                         response_type, ai_response, ai_client, custom_prompt)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (sentence_hash, sentence_text, video_filename, start_time, end_time,
                          response_type, ai_response, ai_client, custom_prompt))
                    
                    response_id = cursor.lastrowid
                    conn.commit()
                    
                    self.logger.debug(f"AI відповідь збережена: {response_type} ID {response_id}")
                    return response_id
                    
        except Exception as e:
            self.logger.error(f"Помилка збереження AI відповіді: {e}")
            raise
    
    def get_ai_response(self, 
                       sentence_text: str,
                       video_filename: str,
                       start_time: float,
                       response_type: str,
                       custom_prompt: Optional[str] = None) -> Optional[Dict]:
        """Отримує збережену AI відповідь"""
        try:
            sentence_hash = self._get_sentence_hash(sentence_text, video_filename, start_time)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT ai_response, ai_client, is_edited, edited_text, 
                           version, created_at, updated_at, custom_prompt
                    FROM ai_responses 
                    WHERE sentence_hash = ? AND response_type = ? AND (custom_prompt = ? OR (custom_prompt IS NULL AND ? IS NULL))
                    ORDER BY version DESC LIMIT 1
                """, (sentence_hash, response_type, custom_prompt, custom_prompt))
                
                result = cursor.fetchone()
                if result:
                    return {
                        "ai_response": result[0],
                        "ai_client": result[1],
                        "is_edited": bool(result[2]),
                        "edited_text": result[3],
                        "version": result[4],
                        "created_at": result[5],
                        "updated_at": result[6],
                        "custom_prompt": result[7]
                    }
                return None
                
        except Exception as e:
            self.logger.error(f"Помилка отримання AI відповіді: {e}")
            return None
    
    def update_ai_response(self, 
                          sentence_text: str,
                          video_filename: str,
                          start_time: float,
                          response_type: str,
                          edited_text: str,
                          custom_prompt: Optional[str] = None) -> bool:
        """Оновлює AI відповідь відредагованим текстом"""
        try:
            sentence_hash = self._get_sentence_hash(sentence_text, video_filename, start_time)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE ai_responses SET
                        is_edited = 1,
                        edited_text = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE sentence_hash = ? AND response_type = ? AND (custom_prompt = ? OR (custom_prompt IS NULL AND ? IS NULL))
                """, (edited_text, sentence_hash, response_type, custom_prompt, custom_prompt))
                
                updated = cursor.rowcount > 0
                conn.commit()
                
                if updated:
                    self.logger.debug(f"AI відповідь відредагована: {response_type}")
                
                return updated
                
        except Exception as e:
            self.logger.error(f"Помилка оновлення AI відповіді: {e}")
            return False
    
    def delete_ai_response(self, 
                          sentence_text: str,
                          video_filename: str,
                          start_time: float,
                          response_type: str,
                          custom_prompt: Optional[str] = None) -> bool:
        """Видаляє AI відповідь"""
        try:
            sentence_hash = self._get_sentence_hash(sentence_text, video_filename, start_time)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    DELETE FROM ai_responses 
                    WHERE sentence_hash = ? AND response_type = ? AND (custom_prompt = ? OR (custom_prompt IS NULL AND ? IS NULL))
                """, (sentence_hash, response_type, custom_prompt, custom_prompt))
                
                deleted = cursor.rowcount > 0
                conn.commit()
                
                if deleted:
                    self.logger.debug(f"AI відповідь видалена: {response_type}")
                
                return deleted
                
        except Exception as e:
            self.logger.error(f"Помилка видалення AI відповіді: {e}")
            return False
    
    def delete_ai_responses(self, 
                           sentence_text: str,
                           video_filename: str,
                           start_time: float) -> int:
        """Видаляє всі AI відповіді для речення"""
        try:
            sentence_hash = self._get_sentence_hash(sentence_text, video_filename, start_time)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    DELETE FROM ai_responses 
                    WHERE sentence_hash = ?
                """, (sentence_hash,))
                
                deleted_count = cursor.rowcount
                conn.commit()
                
                self.logger.debug(f"Видалено {deleted_count} AI відповідей")
                return deleted_count
                
        except Exception as e:
            self.logger.error(f"Помилка видалення AI відповідей: {e}")
            return 0
    
    # ====================================================================
    # USER NOTES METHODS
    # ====================================================================
    
    def save_user_note(self,
                      sentence_text: str,
                      video_filename: str,
                      start_time: float,
                      note_text: str = "",
                      image_data: Optional[bytes] = None,
                      image_filename: Optional[str] = None,
                      tags: Optional[str] = None) -> int:
        """Зберігає нотатку користувача"""
        try:
            sentence_hash = self._get_sentence_hash(sentence_text, video_filename, start_time)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Обробляємо зображення
                image_blob = None
                img_width = None
                img_height = None
                
                if image_data:
                    try:
                        # Конвертуємо в base64
                        image_blob = base64.b64encode(image_data).decode('utf-8')
                        
                        # Спробуємо отримати розміри зображення
                        from PIL import Image
                        import io
                        
                        with Image.open(io.BytesIO(image_data)) as img:
                            img_width, img_height = img.size
                            
                    except Exception as e:
                        self.logger.warning(f"Помилка обробки зображення: {e}")
                
                # Перевіряємо чи є вже нотатка
                cursor.execute("""
                    SELECT id FROM user_notes WHERE sentence_hash = ?
                """, (sentence_hash,))
                
                existing = cursor.fetchone()
                
                if existing:
                    # Оновлюємо існуючу нотатку
                    cursor.execute("""
                        UPDATE user_notes 
                        SET note_text = ?, image_data = ?, image_filename = ?, 
                            image_width = ?, image_height = ?, tags = ?, 
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (note_text, image_blob, image_filename, img_width, img_height, 
                          tags, existing[0]))
                    note_id = existing[0]
                else:
                    # Створюємо нову нотатку
                    cursor.execute("""
                        INSERT INTO user_notes 
                        (sentence_hash, video_filename, sentence_text, start_time, note_text, 
                         image_data, image_filename, image_width, image_height, tags)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (sentence_hash, video_filename, sentence_text, start_time, note_text,
                          image_blob, image_filename, img_width, img_height, tags))
                    note_id = cursor.lastrowid
                
                conn.commit()
                self.logger.debug(f"Нотатка збережена для {video_filename}")
                return note_id
                
        except Exception as e:
            self.logger.error(f"Помилка збереження нотатки: {e}")
            raise
    
    def get_user_note(self, sentence_text: str, video_filename: str, start_time: float) -> Optional[Dict]:
        """Отримує нотатку користувача"""
        try:
            sentence_hash = self._get_sentence_hash(sentence_text, video_filename, start_time)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT note_text, image_data, image_filename, image_width, 
                           image_height, tags, created_at, updated_at
                    FROM user_notes 
                    WHERE sentence_hash = ?
                """, (sentence_hash,))
                
                result = cursor.fetchone()
                if result:
                    # Декодуємо зображення якщо є
                    image_bytes = None
                    if result[1]:
                        try:
                            image_bytes = base64.b64decode(result[1])
                        except Exception as e:
                            self.logger.warning(f"Помилка декодування зображення: {e}")
                    
                    return {
                        "note_text": result[0],
                        "image_data": image_bytes,
                        "image_filename": result[2],
                        "image_width": result[3],
                        "image_height": result[4],
                        "tags": result[5],
                        "created_at": result[6],
                        "updated_at": result[7]
                    }
                return None
                
        except Exception as e:
            self.logger.error(f"Помилка отримання нотатки: {e}")
            return None
    
    def delete_user_note(self, 
                        sentence_text: str,
                        video_filename: str,
                        start_time: float) -> bool:
        """Видаляє нотатку користувача"""
        try:
            sentence_hash = self._get_sentence_hash(sentence_text, video_filename, start_time)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    DELETE FROM user_notes
                    WHERE sentence_hash = ?
                """, (sentence_hash,))
                
                deleted = cursor.rowcount > 0
                conn.commit()
                
                if deleted:
                    self.logger.info("Нотатка видалена")
                
                return deleted
                
        except Exception as e:
            self.logger.error(f"Помилка видалення нотатки: {e}")
            return False
    
    def search_user_notes(self, query: str, limit: int = 50) -> List[Dict]:
        """Пошук в нотатках користувача"""
        try:
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
                
        except Exception as e:
            self.logger.error(f"Помилка пошуку нотаток: {e}")
            return []
    
    def get_all_user_notes(self, video_filename: str = None) -> List[Dict]:
        """Отримує всі нотатки користувача"""
        try:
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
                
        except Exception as e:
            self.logger.error(f"Помилка отримання нотаток: {e}")
            return []
    
    # ====================================================================
    # NOTE INSERTS METHODS
    # ====================================================================
    
    def save_note_insert(self, 
                        user_note_id: int,
                        source_type: str,
                        source_text: str,
                        video_filename: str = None,
                        sentence_index: int = None,
                        ai_response_id: int = None) -> int:
        """Зберігає інформацію про вставку тексту в нотатку"""
        try:
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
                
        except Exception as e:
            self.logger.error(f"Помилка збереження вставки: {e}")
            raise
    
    def get_note_inserts(self, user_note_id: int) -> List[Dict]:
        """Отримує всі вставки для конкретної нотатки"""
        try:
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
                
        except Exception as e:
            self.logger.error(f"Помилка отримання вставок: {e}")
            return []
    
    # ====================================================================
    # VIDEO STATE METHODS
    # ====================================================================
    
    def save_video_state(self, 
                        video_filename: str,
                        video_path: str,
                        sentences_count: int = 0) -> int:
        """Зберігає стан обробки відео"""
        try:
            file_hash = self._get_file_hash(video_path)
            file_size = 0
            duration = 0.0
            
            try:
                file_path = Path(video_path)
                if file_path.exists():
                    file_size = file_path.stat().st_size
            except Exception as e:
                self.logger.warning(f"Помилка отримання інформації файлу {video_path}: {e}")
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Перевіряємо чи існує запис
                cursor.execute("""
                    SELECT id, file_hash FROM video_processing_state 
                    WHERE video_filename = ?
                """, (video_filename,))
                
                existing = cursor.fetchone()
                
                if existing:
                    # Перевіряємо чи змінився файл
                    if existing[1] != file_hash:
                        # Файл змінився, оновлюємо
                        cursor.execute("""
                            UPDATE video_processing_state 
                            SET video_path = ?, file_hash = ?, file_size = ?, duration = ?,
                                sentences_extracted = ?, sentences_with_ai = 0,
                                processing_completed = FALSE, last_modified = CURRENT_TIMESTAMP,
                                last_processed = CURRENT_TIMESTAMP
                            WHERE id = ?
                        """, (video_path, file_hash, file_size, duration, sentences_count, existing[0]))
                        self.logger.info(f"Відео {video_filename} змінилося, оновлено стан")
                    else:
                        # Файл не змінився, тільки оновлюємо кількість речень
                        cursor.execute("""
                            UPDATE video_processing_state 
                            SET sentences_extracted = ?, last_processed = CURRENT_TIMESTAMP
                            WHERE id = ?
                        """, (sentences_count, existing[0]))
                    
                    state_id = existing[0]
                else:
                    # Створюємо новий запис
                    cursor.execute("""
                        INSERT INTO video_processing_state 
                        (video_filename, video_path, file_hash, file_size, duration,
                         sentences_extracted, last_modified)
                        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """, (video_filename, video_path, file_hash, file_size, duration, sentences_count))
                    state_id = cursor.lastrowid
                    self.logger.info(f"Новий стан створено для {video_filename}")
                
                conn.commit()
                return state_id
                
        except Exception as e:
            self.logger.error(f"Помилка збереження стану відео: {e}")
            raise
    
    def get_video_state(self, video_filename: str) -> Optional[Dict]:
        """Отримує стан обробки відео"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT video_path, file_hash, file_size, duration, sentences_extracted,
                           sentences_with_ai, processing_completed, last_modified, last_processed
                    FROM video_processing_state 
                    WHERE video_filename = ?
                """, (video_filename,))
                
                result = cursor.fetchone()
                if result:
                    return {
                        "video_path": result[0],
                        "file_hash": result[1],
                        "file_size": result[2],
                        "duration": result[3],
                        "sentences_extracted": result[4],
                        "sentences_with_ai": result[5],
                        "processing_completed": bool(result[6]),
                        "last_modified": result[7],
                        "last_processed": result[8]
                    }
                return None
                
        except Exception as e:
            self.logger.error(f"Помилка отримання стану відео: {e}")
            return None
    
    def get_all_video_states(self) -> List[Dict]:
        """Отримує стан всіх відео"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT video_filename, video_path, file_hash, sentences_extracted,
                           sentences_with_ai, processing_completed, last_processed
                    FROM video_processing_state 
                    ORDER BY last_processed DESC
                """)
                
                results = []
                for row in cursor.fetchall():
                    results.append({
                        "video_filename": row[0],
                        "video_path": row[1],
                        "file_hash": row[2],
                        "sentences_extracted": row[3],
                        "sentences_with_ai": row[4],
                        "processing_completed": bool(row[5]),
                        "last_processed": row[6]
                    })
                
                return results
                
        except Exception as e:
            self.logger.error(f"Помилка отримання станів відео: {e}")
            return []
    
    # ====================================================================
    # UI SETTINGS METHODS
    # ====================================================================
    
    def save_ui_setting(self, key: str, value: Any, setting_type: str = "string"):
        """Зберігає налаштування UI"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Конвертуємо значення в рядок
                if setting_type == "json":
                    value_str = json.dumps(value)
                elif setting_type == "boolean":
                    value_str = str(bool(value))
                else:
                    value_str = str(value)
                
                cursor.execute("""
                    INSERT OR REPLACE INTO ui_settings (setting_key, setting_value, setting_type)
                    VALUES (?, ?, ?)
                """, (key, value_str, setting_type))
                
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"Помилка збереження налаштування UI: {e}")
    
    def get_ui_setting(self, key: str, default_value: Any = None) -> Any:
        """Отримує налаштування UI"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT setting_value, setting_type FROM ui_settings 
                    WHERE setting_key = ?
                """, (key,))
                
                result = cursor.fetchone()
                if result:
                    value_str, setting_type = result
                    
                    try:
                        if setting_type == "json":
                            return json.loads(value_str)
                        elif setting_type == "boolean":
                            return value_str.lower() in ('true', '1', 'yes')
                        else:
                            return value_str
                    except Exception:
                        return default_value
                
                return default_value
                
        except Exception as e:
            self.logger.error(f"Помилка отримання налаштування UI: {e}")
            return default_value
    
    # ====================================================================
    # STATISTICS METHODS
    # ====================================================================
    
    def get_ai_statistics(self) -> Dict:
        """Отримує статистику AI відповідей"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Загальна кількість відповідей
                cursor.execute("SELECT COUNT(*) FROM ai_responses")
                total_responses = cursor.fetchone()[0]
                
                # Відповіді по типах
                cursor.execute("""
                    SELECT response_type, COUNT(*) 
                    FROM ai_responses 
                    GROUP BY response_type
                """)
                responses_by_type = dict(cursor.fetchall())
                
                # Відредаговані відповіді
                cursor.execute("SELECT COUNT(*) FROM ai_responses WHERE is_edited = 1")
                edited_responses = cursor.fetchone()[0]
                
                # Відповіді по відео
                cursor.execute("""
                    SELECT video_filename, COUNT(*) as count
                    FROM ai_responses
                    GROUP BY video_filename
                    ORDER BY count DESC
                    LIMIT 10
                """)
                responses_by_video = cursor.fetchall()
                
                return {
                    "total_responses": total_responses,
                    "responses_by_type": responses_by_type,
                    "edited_responses": edited_responses,
                    "edit_percentage": round((edited_responses / total_responses * 100), 1) if total_responses > 0 else 0,
                    "responses_by_video": responses_by_video
                }
                
        except Exception as e:
            self.logger.error(f"Помилка отримання статистики AI: {e}")
            return {
                "total_responses": 0,
                "responses_by_type": {},
                "edited_responses": 0,
                "edit_percentage": 0,
                "responses_by_video": []
            }
    
    def get_notes_statistics(self) -> Dict:
        """Отримує статистику нотаток"""
        try:
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
                
                return {
                    "total_notes": total_notes,
                    "notes_with_text": notes_with_text,
                    "notes_with_images": notes_with_images,
                    "notes_with_tags": notes_with_tags
                }
                
        except Exception as e:
            self.logger.error(f"Помилка отримання статистики нотаток: {e}")
            return {
                "total_notes": 0,
                "notes_with_text": 0,
                "notes_with_images": 0,
                "notes_with_tags": 0
            }
    
    def get_statistics(self) -> Dict:
        """Отримує загальну статистику використання"""
        try:
            ai_stats = self.get_ai_statistics()
            notes_stats = self.get_notes_statistics()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Кількість відео
                cursor.execute("SELECT COUNT(*) FROM video_processing_state")
                videos_count = cursor.fetchone()[0]
                
                # Кількість вставок
                cursor.execute("SELECT COUNT(*) FROM note_inserts")
                inserts_count = cursor.fetchone()[0]
            
            return {
                "ai_responses": ai_stats["responses_by_type"],
                "user_notes": notes_stats["total_notes"],
                "edited_responses": ai_stats["edited_responses"],
                "videos_processed": videos_count,
                "note_inserts": inserts_count,
                "database_size": self.db_path.stat().st_size if self.db_path.exists() else 0
            }
            
        except Exception as e:
            self.logger.error(f"Помилка отримання загальної статистики: {e}")
            return {
                "ai_responses": {},
                "user_notes": 0,
                "edited_responses": 0,
                "videos_processed": 0,
                "note_inserts": 0,
                "database_size": 0
            }
    
    # ====================================================================
    # SEARCH METHODS
    # ====================================================================
    
    def search_ai_responses(self, query: str, response_type: str = None, limit: int = 50) -> List[Dict]:
        """Пошук в AI відповідях"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                base_query = """
                    SELECT sentence_text, video_filename, start_time, response_type,
                           ai_response, edited_text, is_edited
                    FROM ai_responses
                    WHERE (ai_response LIKE ? OR edited_text LIKE ? OR sentence_text LIKE ?)
                """
                
                params = [f"%{query}%", f"%{query}%", f"%{query}%"]
                
                if response_type:
                    base_query += " AND response_type = ?"
                    params.append(response_type)
                
                base_query += " ORDER BY updated_at DESC LIMIT ?"
                params.append(limit)
                
                cursor.execute(base_query, params)
                
                results = []
                for row in cursor.fetchall():
                    results.append({
                        "sentence_text": row[0],
                        "video_filename": row[1],
                        "start_time": row[2],
                        "response_type": row[3],
                        "ai_response": row[4],
                        "edited_text": row[5],
                        "is_edited": bool(row[6])
                    })
                
                self.logger.info(f"Знайдено {len(results)} AI відповідей для '{query}'")
                return results
                
        except Exception as e:
            self.logger.error(f"Помилка пошуку AI відповідей: {e}")
            return []
    
    def get_all_ai_responses(self, video_filename: str = None) -> List[Dict]:
        """Отримує всі AI відповіді"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if video_filename:
                    cursor.execute("""
                        SELECT sentence_text, video_filename, start_time, response_type,
                               ai_response, edited_text, is_edited, created_at
                        FROM ai_responses
                        WHERE video_filename = ?
                        ORDER BY start_time, response_type
                    """, (video_filename,))
                else:
                    cursor.execute("""
                        SELECT sentence_text, video_filename, start_time, response_type,
                               ai_response, edited_text, is_edited, created_at
                        FROM ai_responses
                        ORDER BY video_filename, start_time, response_type
                    """)
                
                responses = []
                for row in cursor.fetchall():
                    responses.append({
                        "sentence_text": row[0],
                        "video_filename": row[1],
                        "start_time": row[2],
                        "response_type": row[3],
                        "ai_response": row[4],
                        "edited_text": row[5],
                        "is_edited": bool(row[6]),
                        "created_at": row[7]
                    })
                
                return responses
                
        except Exception as e:
            self.logger.error(f"Помилка отримання AI відповідей: {e}")
            return []


# Приклад використання
if __name__ == "__main__":
    # Тестування DataManager
    data_manager = DataManager()
    
    # Тест збереження AI відповіді
    print("=== Тест збереження AI відповіді ===")
    response_id = data_manager.save_ai_response(
        sentence_text="Hello world",
        video_filename="test.mkv",
        start_time=10.5,
        end_time=15.0,
        response_type="translation",
        ai_response="Привіт світ",
        ai_client="llama3.1"
    )
    print(f"Збережено AI відповідь з ID: {response_id}")
    
    # Тест збереження нотатки
    print("\n=== Тест збереження нотатки ===")
    note_id = data_manager.save_user_note(
        sentence_text="Hello world",
        video_filename="test.mkv",
        start_time=10.5,
        note_text="Це важливе речення для вивчення",
        tags="#важливо, #базове"
    )
    print(f"Збережено нотатку з ID: {note_id}")
    
    # Тест отримання статистики
    print("\n=== Статистика ===")
    stats = data_manager.get_statistics()
    print(json.dumps(stats, indent=2, ensure_ascii=False))