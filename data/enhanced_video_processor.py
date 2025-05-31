"""
Enhanced Video Processor - розширений обробник відео з підтримкою Vision AI та розумного групування
Додає обробку відео кадрів, розумне групування по паузах та покращені AI пояснення
"""

import cv2
import numpy as np
import logging
import base64
import json
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import time
from datetime import datetime
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# Імпорти з існуючих модулів
from processing.audio_extractor import AudioExtractor
from processing.transcriber import Transcriber
from processing.database_manager import DatabaseManager
from data.data_manager import DataManager


class FrameExtractor:
    """Клас для витягування кадрів з відео та аналізу візуальної інформації"""

    def __init__(self, output_dir: str = "processed/frames"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)

    def extract_key_frames(self, video_path: str, segments: List[Dict],
                           max_frames_per_segment: int = 3) -> List[Dict]:
        """
        Витягує ключові кадри для кожного сегменту

        Args:
            video_path: Шлях до відео
            segments: Сегменти з часовими мітками
            max_frames_per_segment: Максимум кадрів на сегмент

        Returns:
            Список кадрів з метаданими
        """
        frames_data = []

        try:
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)

            for segment_idx, segment in enumerate(segments):
                start_time = segment['start_time']
                end_time = segment['end_time']
                duration = end_time - start_time

                # Визначаємо кількість кадрів для цього сегменту
                frames_to_extract = min(max_frames_per_segment, max(1, int(duration / 2)))

                # Розраховуємо позиції кадрів
                if frames_to_extract == 1:
                    frame_times = [start_time + duration / 2]  # Центральний кадр
                else:
                    step = duration / (frames_to_extract + 1)
                    frame_times = [start_time + step * (i + 1) for i in range(frames_to_extract)]

                for frame_idx, frame_time in enumerate(frame_times):
                    frame_number = int(frame_time * fps)
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)

                    ret, frame = cap.read()
                    if ret:
                        # Зберігаємо кадр
                        video_name = Path(video_path).stem
                        frame_filename = f"{video_name}_seg{segment_idx:03d}_frame{frame_idx:02d}.jpg"
                        frame_path = self.output_dir / frame_filename

                        cv2.imwrite(str(frame_path), frame)

                        # Створюємо мініатюру
                        thumbnail = self._create_thumbnail(frame)
                        thumbnail_b64 = self._frame_to_base64(thumbnail)

                        frames_data.append({
                            'segment_index': segment_idx,
                            'frame_index': frame_idx,
                            'timestamp': frame_time,
                            'frame_path': str(frame_path),
                            'thumbnail_b64': thumbnail_b64,
                            'segment_text': segment.get('text', ''),
                            'frame_number': frame_number
                        })

            cap.release()
            self.logger.info(f"Витягнуто {len(frames_data)} кадрів з відео")
            return frames_data

        except Exception as e:
            self.logger.error(f"Помилка витягування кадрів: {e}")
            return []

    def _create_thumbnail(self, frame: np.ndarray, size: Tuple[int, int] = (320, 240)) -> np.ndarray:
        """Створює мініатюру кадру"""
        return cv2.resize(frame, size, interpolation=cv2.INTER_AREA)

    def _frame_to_base64(self, frame: np.ndarray) -> str:
        """Конвертує кадр в base64 рядок"""
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return base64.b64encode(buffer).decode('utf-8')

    def analyze_frame_content(self, frame_path: str) -> Dict:
        """
        Аналізує вміст кадру (базовий аналіз)
        У майбутньому можна додати Vision API
        """
        try:
            frame = cv2.imread(frame_path)
            if frame is None:
                return {}

            # Базовий аналіз
            height, width = frame.shape[:2]
            mean_brightness = np.mean(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))

            # Детекція країв (показник складності зображення)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            edge_density = np.sum(edges > 0) / (width * height)

            # Колірний аналіз
            colors = cv2.split(frame)
            color_stats = {
                'mean_blue': float(np.mean(colors[0])),
                'mean_green': float(np.mean(colors[1])),
                'mean_red': float(np.mean(colors[2]))
            }

            return {
                'width': width,
                'height': height,
                'brightness': float(mean_brightness),
                'edge_density': float(edge_density),
                'color_analysis': color_stats,
                'complexity_score': float(edge_density * 100)  # Простий показник складності
            }

        except Exception as e:
            self.logger.error(f"Помилка аналізу кадру {frame_path}: {e}")
            return {}


class SmartSegmentGrouper:
    """Клас для розумного групування сегментів по паузах та контексту"""

    def __init__(self, silence_threshold: float = 5.0, min_group_duration: float = 10.0):
        """
        Args:
            silence_threshold: Мінімальна тривалість тиші для розділення груп (секунди)
            min_group_duration: Мінімальна тривалість групи (секунди)
        """
        self.silence_threshold = silence_threshold
        self.min_group_duration = min_group_duration
        self.logger = logging.getLogger(__name__)

    def group_segments_by_silence(self, segments: List[Dict]) -> List[Dict]:
        """
        Групує сегменти по паузах між ними

        Args:
            segments: Список сегментів з часовими мітками

        Returns:
            Список груп сегментів
        """
        if not segments:
            return []

        groups = []
        current_group = []
        current_group_start = segments[0]['start_time']

        for i, segment in enumerate(segments):
            if not current_group:
                # Початок нової групи
                current_group = [segment]
                current_group_start = segment['start_time']
            else:
                # Перевіряємо паузу між попереднім і поточним сегментом
                prev_segment = segments[i - 1]
                pause_duration = segment['start_time'] - prev_segment['end_time']

                if pause_duration >= self.silence_threshold:
                    # Довга пауза - завершуємо поточну групу
                    group_data = self._create_group(current_group, current_group_start)
                    if group_data:
                        groups.append(group_data)

                    # Починаємо нову групу
                    current_group = [segment]
                    current_group_start = segment['start_time']
                else:
                    # Додаємо до поточної групи
                    current_group.append(segment)

        # Завершуємо останню групу
        if current_group:
            group_data = self._create_group(current_group, current_group_start)
            if group_data:
                groups.append(group_data)

        self.logger.info(f"Створено {len(groups)} груп з {len(segments)} сегментів")
        return groups

    def _create_group(self, segments: List[Dict], start_time: float) -> Optional[Dict]:
        """Створює групу з сегментів"""
        if not segments:
            return None

        end_time = segments[-1]['end_time']
        duration = end_time - start_time

        # Перевіряємо мінімальну тривалість
        if duration < self.min_group_duration:
            return None

        # Об'єднуємо текст всіх сегментів
        combined_text = ' '.join(segment.get('text', '').strip() for segment in segments)
        combined_text = ' '.join(combined_text.split())  # Нормалізуємо пробіли

        # Підраховуємо статистику
        avg_confidence = np.mean([seg.get('confidence', 0.0) for seg in segments])
        word_count = len(combined_text.split())

        return {
            'group_start_time': start_time,
            'group_end_time': end_time,
            'group_duration': duration,
            'segments_count': len(segments),
            'combined_text': combined_text,
            'word_count': word_count,
            'avg_confidence': float(avg_confidence),
            'segments': segments,
            'group_id': f"{start_time:.1f}_{end_time:.1f}",
            'pause_before': segments[0]['start_time'] - start_time if len(segments) > 1 else 0.0
        }

    def analyze_group_content(self, group: Dict) -> Dict:
        """Аналізує контент групи для подальшої обробки AI"""
        text = group['combined_text']

        # Базовий аналіз тексту
        sentences = text.split('. ')
        questions = [s for s in sentences if s.strip().endswith('?')]
        exclamations = [s for s in sentences if s.strip().endswith('!')]

        # Визначення складності
        complexity_indicators = {
            'long_sentences': len([s for s in sentences if len(s.split()) > 15]),
            'question_count': len(questions),
            'exclamation_count': len(exclamations),
            'unique_words': len(set(text.lower().split())),
            'avg_word_length': np.mean([len(word) for word in text.split()]),
            'sentence_count': len(sentences)
        }

        return {
            'content_analysis': complexity_indicators,
            'suggested_focus': self._suggest_learning_focus(text, complexity_indicators),
            'difficulty_level': self._estimate_difficulty(complexity_indicators)
        }

    def _suggest_learning_focus(self, text: str, indicators: Dict) -> List[str]:
        """Пропонує фокус для вивчення"""
        focus_areas = []

        if indicators['question_count'] > 0:
            focus_areas.append('question_formation')

        if indicators['long_sentences'] > 0:
            focus_areas.append('complex_grammar')

        if indicators['avg_word_length'] > 6:
            focus_areas.append('advanced_vocabulary')

        if 'will' in text.lower() or 'would' in text.lower():
            focus_areas.append('future_conditional')

        if indicators['sentence_count'] > 5:
            focus_areas.append('discourse_markers')

        return focus_areas

    def _estimate_difficulty(self, indicators: Dict) -> str:
        """Оцінює складність тексту"""
        score = 0

        score += indicators['long_sentences'] * 2
        score += indicators['unique_words'] / 10
        score += (indicators['avg_word_length'] - 4) * 2 if indicators['avg_word_length'] > 4 else 0

        if score < 5:
            return 'beginner'
        elif score < 15:
            return 'intermediate'
        else:
            return 'advanced'


class EnhancedVideoProcessor:
    """Розширений обробник відео з підтримкою Vision та розумного групування"""

    def __init__(self,
                 videos_dir: str = "videos",
                 supported_formats: List[str] = None,
                 silence_threshold: float = 5.0):
        """
        Args:
            videos_dir: Папка з відео файлами
            supported_formats: Підтримувані формати відео
            silence_threshold: Поріг тиші для групування (секунди)
        """
        self.videos_dir = Path(videos_dir)
        self.supported_formats = supported_formats or ['.mkv', '.mp4', '.avi', '.mov', '.wmv']

        self.logger = logging.getLogger(__name__)

        # Ініціалізація компонентів
        self.audio_extractor = AudioExtractor()
        self.transcriber = Transcriber(model_size='base', device='cpu')
        self.db_manager = DatabaseManager()
        self.data_manager = DataManager()
        self.frame_extractor = FrameExtractor()
        self.segment_grouper = SmartSegmentGrouper(silence_threshold=silence_threshold)

        # Статистика обробки
        self.processing_stats = {
            "videos_found": 0,
            "videos_processed": 0,
            "groups_created": 0,
            "frames_extracted": 0,
            "processing_time": 0.0
        }

    def process_single_video_enhanced(self, video_info: Dict) -> Dict:
        """
        Розширена обробка одного відео з підтримкою Vision та групування

        Args:
            video_info: Інформація про відео

        Returns:
            Результат обробки з груп та кадрів
        """
        start_time = time.time()
        filename = video_info["filename"]
        filepath = video_info["filepath"]

        result = {
            "filename": filename,
            "success": False,
            "groups_count": 0,
            "frames_count": 0,
            "segments_count": 0,
            "processing_time": 0.0,
            "error": None
        }

        try:
            self.logger.info(f"Початок розширеної обробки: {filename}")

            # 1. Додаємо відео в основну БД
            video_file_info = self.audio_extractor.get_video_info(filepath)
            duration = float(video_file_info['format']['duration']) if video_file_info else None
            file_size = int(video_file_info['format']['size']) if video_file_info else None

            video_id = self.db_manager.add_video(
                filename=filename,
                filepath=filepath,
                duration=duration,
                file_size=file_size
            )

            # 2. Витягуємо аудіо
            self.logger.info(f"Витягування аудіо: {filename}")
            audio_path = self.audio_extractor.extract_audio(filepath)

            if not audio_path:
                raise Exception("Помилка витягування аудіо")

            # 3. Транскрипція
            self.logger.info(f"Транскрипція: {filename}")
            transcription_result = self.transcriber.transcribe_audio(audio_path, language='en')

            if not transcription_result:
                raise Exception("Помилка транскрипції")

            # 4. Додаємо транскрипцію в основну БД
            transcription_id = self.db_manager.add_transcription(video_id, transcription_result)

            segments = transcription_result.get("segments", [])

            # 5. НОВА ФУНКЦІЯ: Розумне групування по паузах
            self.logger.info(f"Розумне групування {len(segments)} сегментів...")
            groups = self.segment_grouper.group_segments_by_silence(segments)

            # 6. НОВА ФУНКЦІЯ: Витягування кадрів для кожної групи
            self.logger.info(f"Витягування кадрів для {len(groups)} груп...")
            all_frames = []

            with ThreadPoolExecutor(max_workers=3) as executor:
                frame_futures = []

                for group in groups:
                    # Витягуємо кадри для групи (беремо підвибірку сегментів)
                    group_segments = group['segments']
                    future = executor.submit(
                        self.frame_extractor.extract_key_frames,
                        filepath, group_segments, 2  # Максимум 2 кадри на сегмент
                    )
                    frame_futures.append(future)

                # Збираємо результати
                for future in as_completed(frame_futures):
                    try:
                        frames = future.result()
                        all_frames.extend(frames)
                    except Exception as e:
                        self.logger.error(f"Помилка витягування кадрів: {e}")

            # 7. Зберігаємо групи та кадри в розширену БД
            self._save_groups_and_frames(video_id, filename, groups, all_frames)

            # 8. Зберігаємо стан в data_manager
            state_id = self.data_manager.save_video_state(
                video_filename=filename,
                video_path=filepath,
                sentences_count=len(segments)  # Тепер це кількість оригінальних сегментів
            )

            result.update({
                "success": True,
                "video_id": video_id,
                "transcription_id": transcription_id,
                "state_id": state_id,
                "groups_count": len(groups),
                "frames_count": len(all_frames),
                "segments_count": len(segments)
            })

            self.processing_stats["videos_processed"] += 1
            self.processing_stats["groups_created"] += len(groups)
            self.processing_stats["frames_extracted"] += len(all_frames)

            self.logger.info(f"Розширена обробка завершена: {filename}")
            self.logger.info(f"  📊 Сегментів: {len(segments)}")
            self.logger.info(f"  📦 Груп створено: {len(groups)}")
            self.logger.info(f"  🖼️ Кадрів витягнуто: {len(all_frames)}")

        except Exception as e:
            error_msg = f"Помилка обробки {filename}: {str(e)}"
            self.logger.error(error_msg)
            result["error"] = error_msg

        finally:
            result["processing_time"] = time.time() - start_time
            self.processing_stats["processing_time"] += result["processing_time"]

        return result

    def _save_groups_and_frames(self, video_id: int, video_filename: str,
                                groups: List[Dict], frames: List[Dict]):
        """Зберігає групи та кадри в розширену базу даних"""
        try:
            # Створюємо розширені таблиці якщо потрібно
            self._create_extended_tables()

            import sqlite3
            with sqlite3.connect(self.db_manager.db_path) as conn:
                cursor = conn.cursor()

                # Зберігаємо групи
                for group_idx, group in enumerate(groups):
                    # Аналізуємо контент групи
                    content_analysis = self.segment_grouper.analyze_group_content(group)

                    cursor.execute("""
                                   INSERT INTO segment_groups
                                   (video_id, video_filename, group_index, group_start_time, group_end_time,
                                    group_duration, segments_count, combined_text, word_count, avg_confidence,
                                    content_analysis, difficulty_level)
                                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                   """, (
                                       video_id, video_filename, group_idx,
                                       group['group_start_time'], group['group_end_time'], group['group_duration'],
                                       group['segments_count'], group['combined_text'], group['word_count'],
                                       group['avg_confidence'], json.dumps(content_analysis),
                                       content_analysis.get('difficulty_level', 'intermediate')
                                   ))

                    group_db_id = cursor.lastrowid

                    # Зберігаємо сегменти групи
                    for seg_idx, segment in enumerate(group['segments']):
                        cursor.execute("""
                                       INSERT INTO group_segments
                                           (group_id, segment_index, start_time, end_time, text, confidence)
                                       VALUES (?, ?, ?, ?, ?, ?)
                                       """, (
                                           group_db_id, seg_idx,
                                           segment.get('start_time', segment.get('start', 0)),
                                           segment.get('end_time', segment.get('end', 0)),
                                           segment.get('text', ''),
                                           segment.get('confidence', 0.0)
                                       ))

                # Зберігаємо кадри
                for frame in frames:
                    # Знаходимо відповідну групу для кадру
                    frame_time = frame['timestamp']
                    group_id = None

                    cursor.execute("""
                                   SELECT id
                                   FROM segment_groups
                                   WHERE video_id = ?
                                     AND group_start_time <= ?
                                     AND group_end_time >= ?
                                   """, (video_id, frame_time, frame_time))

                    group_result = cursor.fetchone()
                    if group_result:
                        group_id = group_result[0]

                    # Аналізуємо кадр
                    frame_analysis = self.frame_extractor.analyze_frame_content(frame['frame_path'])

                    cursor.execute("""
                                   INSERT INTO video_frames
                                   (video_id, group_id, segment_index, frame_index, timestamp,
                                    frame_path, thumbnail_b64, frame_analysis)
                                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                   """, (
                                       video_id, group_id, frame['segment_index'], frame['frame_index'],
                                       frame['timestamp'], frame['frame_path'], frame['thumbnail_b64'],
                                       json.dumps(frame_analysis)
                                   ))

                conn.commit()

        except Exception as e:
            self.logger.error(f"Помилка збереження груп та кадрів: {e}")

    def _create_extended_tables(self):
        """Створює розширені таблиці для груп та кадрів"""
        with sqlite3.connect(self.db_manager.db_path) as conn:
            cursor = conn.cursor()

            # Таблиця груп сегментів
            cursor.execute("""
                           CREATE TABLE IF NOT EXISTS segment_groups
                           (
                               id
                               INTEGER
                               PRIMARY
                               KEY
                               AUTOINCREMENT,
                               video_id
                               INTEGER,
                               video_filename
                               TEXT
                               NOT
                               NULL,
                               group_index
                               INTEGER,
                               group_start_time
                               REAL
                               NOT
                               NULL,
                               group_end_time
                               REAL
                               NOT
                               NULL,
                               group_duration
                               REAL,
                               segments_count
                               INTEGER,
                               combined_text
                               TEXT,
                               word_count
                               INTEGER,
                               avg_confidence
                               REAL,
                               content_analysis
                               TEXT,
                               difficulty_level
                               TEXT
                               DEFAULT
                               'intermediate',
                               ai_analysis
                               TEXT,
                               created_at
                               TIMESTAMP
                               DEFAULT
                               CURRENT_TIMESTAMP,
                               FOREIGN
                               KEY
                           (
                               video_id
                           ) REFERENCES videos
                           (
                               id
                           )
                               )
                           """)

            # Таблиця сегментів в групах
            cursor.execute("""
                           CREATE TABLE IF NOT EXISTS group_segments
                           (
                               id
                               INTEGER
                               PRIMARY
                               KEY
                               AUTOINCREMENT,
                               group_id
                               INTEGER,
                               segment_index
                               INTEGER,
                               start_time
                               REAL,
                               end_time
                               REAL,
                               text
                               TEXT,
                               confidence
                               REAL,
                               FOREIGN
                               KEY
                           (
                               group_id
                           ) REFERENCES segment_groups
                           (
                               id
                           )
                               )
                           """)

            # Таблиця кадрів відео
            cursor.execute("""
                           CREATE TABLE IF NOT EXISTS video_frames
                           (
                               id
                               INTEGER
                               PRIMARY
                               KEY
                               AUTOINCREMENT,
                               video_id
                               INTEGER,
                               group_id
                               INTEGER,
                               segment_index
                               INTEGER,
                               frame_index
                               INTEGER,
                               timestamp
                               REAL
                               NOT
                               NULL,
                               frame_path
                               TEXT,
                               thumbnail_b64
                               TEXT,
                               frame_analysis
                               TEXT,
                               vision_description
                               TEXT,
                               created_at
                               TIMESTAMP
                               DEFAULT
                               CURRENT_TIMESTAMP,
                               FOREIGN
                               KEY
                           (
                               video_id
                           ) REFERENCES videos
                           (
                               id
                           ),
                               FOREIGN KEY
                           (
                               group_id
                           ) REFERENCES segment_groups
                           (
                               id
                           )
                               )
                           """)

            # Індекси для швидкого пошуку
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_groups_video ON segment_groups(video_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_groups_time ON segment_groups(group_start_time)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_frames_group ON video_frames(group_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_frames_time ON video_frames(timestamp)")

            conn.commit()

    def get_video_groups(self, video_filename: str) -> List[Dict]:
        """Отримує групи для конкретного відео"""
        try:
            import sqlite3
            with sqlite3.connect(self.db_manager.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                               SELECT id,
                                      group_index,
                                      group_start_time,
                                      group_end_time,
                                      group_duration,
                                      segments_count,
                                      combined_text,
                                      word_count,
                                      difficulty_level,
                                      content_analysis
                               FROM segment_groups
                               WHERE video_filename = ?
                               ORDER BY group_start_time
                               """, (video_filename,))

                groups = []
                for row in cursor.fetchall():
                    group_data = {
                        'id': row[0],
                        'group_index': row[1],
                        'group_start_time': row[2],
                        'group_end_time': row[3],
                        'group_duration': row[4],
                        'segments_count': row[5],
                        'combined_text': row[6],
                        'word_count': row[7],
                        'difficulty_level': row[8],
                        'content_analysis': json.loads(row[9]) if row[9] else {}
                    }

                    # Додаємо кадри для групи
                    cursor.execute("""
                                   SELECT timestamp, frame_path, thumbnail_b64, frame_analysis
                                   FROM video_frames
                                   WHERE group_id = ?
                                   ORDER BY timestamp
                                   """, (row[0],))

                    frames = []
                    for frame_row in cursor.fetchall():
                        frames.append({
                            'timestamp': frame_row[0],
                            'frame_path': frame_row[1],
                            'thumbnail_b64': frame_row[2],
                            'frame_analysis': json.loads(frame_row[3]) if frame_row[3] else {}
                        })

                    group_data['frames'] = frames
                    groups.append(group_data)

                return groups

        except Exception as e:
            self.logger.error(f"Помилка отримання груп: {e}")
            return []

    def get_processing_statistics(self) -> Dict:
        """Повертає статистику обробки"""
        return self.processing_stats.copy()


# Приклад використання
if __name__ == "__main__":
    # Налаштування логування
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Створення розширеного процесора
    processor = EnhancedVideoProcessor(silence_threshold=3.0)  # 3 секунди тиші

    # Тест обробки відео
    test_video = {
        "filename": "test_video.mkv",
        "filepath": "videos/test_video.mkv",
        "size": 1024000
    }

    print("=== Тест розширеної обробки відео ===")
    result = processor.process_single_video_enhanced(test_video)

    print(f"Результат: {result}")

    if result['success']:
        print(f"✅ Створено {result['groups_count']} груп")
        print(f"✅ Витягнуто {result['frames_count']} кадрів")

        # Тест отримання груп
        groups = processor.get_video_groups(test_video["filename"])
        print(f"📦 Отримано {len(groups)} груп з бази даних")

        for i, group in enumerate(groups[:3]):  # Показуємо перші 3 групи
            print(f"  Група {i + 1}: {group['group_duration']:.1f}с, "
                  f"{group['word_count']} слів, {len(group['frames'])} кадрів")

    # Статистика
    stats = processor.get_processing_statistics()
    print(f"\n📊 Статистика: {stats}")