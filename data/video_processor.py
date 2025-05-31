"""
Video Processor - автоматична обробка відео файлів
Сканує папку, перевіряє зміни, витягує аудіо та створює транскрипції
"""

import os
import re
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import time
from datetime import datetime

# Імпорти з існуючих модулів
from processing.audio_extractor import AudioExtractor
from processing.transcriber import Transcriber
from processing.database_manager import DatabaseManager
from data.data_manager import DataManager

class VideoProcessor:
    """Автоматична обробка відео файлів"""
    
    def __init__(self, 
                 videos_dir: str = "videos",
                 supported_formats: List[str] = None):
        """
        Ініціалізація Video Processor
        
        Args:
            videos_dir: Папка з відео файлами
            supported_formats: Підтримувані формати відео
        """
        self.videos_dir = Path(videos_dir)
        self.supported_formats = supported_formats or ['.mkv', '.mp4', '.avi', '.mov', '.wmv']
        
        self.logger = logging.getLogger(__name__)
        
        # Ініціалізація компонентів
        self.audio_extractor = AudioExtractor()
        self.transcriber = Transcriber(model_size='tiny', device='cpu')
        self.db_manager = DatabaseManager()
        self.data_manager = DataManager()
        
        # Статистика обробки
        self.processing_stats = {
            "videos_found": 0,
            "videos_new": 0,
            "videos_changed": 0,
            "videos_processed": 0,
            "videos_failed": 0,
            "sentences_extracted": 0,
            "processing_time": 0.0
        }
    
    def scan_videos_directory(self) -> List[Dict]:
        """
        Сканує папку з відео та повертає список файлів
        
        Returns:
            Список словників з інформацією про відео
        """
        video_files = []
        
        if not self.videos_dir.exists():
            self.logger.warning(f"Папка з відео не існує: {self.videos_dir}")
            return video_files
        
        # Шукаємо всі відео файли
        for file_path in self.videos_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in self.supported_formats:
                try:
                    stat = file_path.stat()
                    
                    video_info = {
                        "filename": file_path.name,
                        "filepath": str(file_path),
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime),
                        "extension": file_path.suffix.lower()
                    }
                    
                    video_files.append(video_info)
                    
                except Exception as e:
                    self.logger.error(f"Помилка читання файлу {file_path}: {e}")
        
        self.processing_stats["videos_found"] = len(video_files)
        self.logger.info(f"Знайдено {len(video_files)} відео файлів")
        
        return sorted(video_files, key=lambda x: x["modified"], reverse=True)
    
    def check_video_changes(self, video_info: Dict) -> str:
        """
        Перевіряє стан відео файлу
        
        Args:
            video_info: Інформація про відео
            
        Returns:
            'new', 'changed', 'processed', 'failed'
        """
        filename = video_info["filename"]
        
        # Перевіряємо стан в data_manager
        video_state = self.data_manager.get_video_state(filename)
        
        if not video_state:
            return 'new'
        
        # Перевіряємо чи змінився файл
        current_hash = self.data_manager._get_file_hash(video_info["filepath"])
        
        if current_hash != video_state["file_hash"]:
            return 'changed'
        
        # Перевіряємо чи завершена обробка
        if video_state["processing_completed"]:
            return 'processed'
        
        return 'failed'

    def split_text_into_sentences(self, segments: List[Dict]) -> List[Dict]:
        """
        Розбиває сегменти транскрипції на окремі речення з дедуплікацією
        
        Args:
            segments: Сегменти з Whisper або БД
            
        Returns:
            Список речень з часовими мітками без дублікатів
        """
        sentences = []
        seen_sentences = set()  # Для відстеження унікальних речень
        
        for segment in segments:
            text = segment['text'].strip()
            
            # УНІВЕРСАЛЬНЕ ВИПРАВЛЕННЯ: підтримуємо обидва формати
            if 'start_time' in segment:
                # Формат з БД
                start_time = segment['start_time']
                end_time = segment['end_time']
            elif 'start' in segment:
                # Формат з Whisper
                start_time = segment['start']
                end_time = segment['end']
            else:
                self.logger.error(f"Сегмент не має полів часу: {list(segment.keys())}")
                continue
            
            # Простий розподіл по реченнях
            # Розбиваємо по '.', '!', '?' але зберігаємо ці символи
            sentence_pattern = r'([.!?]+)'
            parts = re.split(sentence_pattern, text)
            
            current_sentence = ""
            sentence_start = start_time
            
            for i, part in enumerate(parts):
                if part.strip():
                    current_sentence += part
                    
                    # Якщо це кінець речення (пунктуація)
                    if re.match(sentence_pattern, part):
                        if current_sentence.strip():
                            # Обчислюємо приблизний час кінця речення
                            progress = (i + 1) / len(parts)
                            sentence_end = sentence_start + (end_time - sentence_start) * progress
                            
                            # НОВА ФУНКЦІЯ: Перевіряємо на дублікати
                            normalized_text = self._normalize_sentence_for_comparison(current_sentence.strip())
                            
                            if normalized_text not in seen_sentences:
                                seen_sentences.add(normalized_text)
                                
                                sentences.append({
                                    'text': current_sentence.strip(),
                                    'start_time': float(sentence_start),
                                    'end_time': float(min(sentence_end, end_time)),
                                    'confidence': segment.get('confidence', 0.0),
                                    'normalized_text': normalized_text  # Для подальшої перевірки
                                })
                            else:
                                self.logger.debug(f"Пропущено дублікат: {current_sentence.strip()[:30]}...")
                            
                            # Підготовка до наступного речення
                            current_sentence = ""
                            sentence_start = sentence_end
            
            # Якщо залишився текст без кінцевої пунктуації
            if current_sentence.strip():
                normalized_text = self._normalize_sentence_for_comparison(current_sentence.strip())
                
                if normalized_text not in seen_sentences:
                    seen_sentences.add(normalized_text)
                    
                    sentences.append({
                        'text': current_sentence.strip(),
                        'start_time': float(sentence_start),
                        'end_time': float(end_time),
                        'confidence': segment.get('confidence', 0.0),
                        'normalized_text': normalized_text
                    })
                else:
                    self.logger.debug(f"Пропущено дублікат (кінцевий): {current_sentence.strip()[:30]}...")
        
        # Фільтруємо дуже короткі речення
        filtered_sentences = []
        for sentence in sentences:
            text = sentence['text'].strip()
            # Пропускаємо речення коротші за 10 символів або що містять тільки пунктуацію
            if len(text) >= 10 and not re.match(r'^[.!?\s]+$', text):
                # Видаляємо normalized_text перед поверненням (не потрібен у UI)
                del sentence['normalized_text']
                filtered_sentences.append(sentence)
        
        self.logger.info(f"Дедуплікація: {len(sentences)} → {len(filtered_sentences)} речень")
        
        return filtered_sentences

    def _normalize_sentence_for_comparison(self, text: str) -> str:
        """
        Нормалізує речення для порівняння на дублікати
        
        Args:
            text: Оригінальний текст речення
            
        Returns:
            Нормалізований текст для порівняння
        """
        import re
        
        # Приводимо до нижнього регістру
        normalized = text.lower()
        
        # Видаляємо зайві пробіли
        normalized = ' '.join(normalized.split())
        
        # Видаляємо пунктуацію з кінців
        normalized = re.sub(r'^[^\w]+|[^\w]+$', '', normalized)
        
        # Замінюємо множинні пробіли одним
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Видаляємо деякі слова-паразити що можуть відрізнятися
        filler_words = ['um', 'uh', 'er', 'ah', 'like', 'you know']
        words = normalized.split()
        words = [w for w in words if w not in filler_words]
        
        return ' '.join(words).strip()

    def deduplicate_with_existing_sentences(self, new_sentences: List[Dict], 
                                        video_filename: str) -> List[Dict]:
        """
        Дедуплікує нові речення з вже існуючими в базі даних
        
        Args:
            new_sentences: Нові речення для перевірки
            video_filename: Назва відео файлу
            
        Returns:
            Список речень з підтягнутими AI відповідями
        """
        try:
            # Отримуємо всі існуючі речення з бази даних
            existing_sentences_map = self._get_existing_sentences_map()
            
            deduplicated_sentences = []
            duplicates_found = 0
            ai_reused = 0
            
            for sentence in new_sentences:
                normalized_text = self._normalize_sentence_for_comparison(sentence['text'])
                
                # Перевіряємо чи є таке речення в базі
                if normalized_text in existing_sentences_map:
                    existing_data = existing_sentences_map[normalized_text]
                    
                    # Створюємо нове речення з часовими мітками з поточного відео
                    # але з AI відповідями з існуючого речення
                    enhanced_sentence = sentence.copy()
                    enhanced_sentence['has_existing_ai'] = True
                    enhanced_sentence['existing_ai_source'] = existing_data['video_filename']
                    enhanced_sentence['ai_responses_count'] = existing_data['ai_count']
                    
                    duplicates_found += 1
                    if existing_data['ai_count'] > 0:
                        ai_reused += 1
                    
                    self.logger.debug(f"Знайдено дублікат з AI: {sentence['text'][:30]}... "
                                    f"(джерело: {existing_data['video_filename']})")
                else:
                    enhanced_sentence = sentence.copy()
                    enhanced_sentence['has_existing_ai'] = False
                    
                deduplicated_sentences.append(enhanced_sentence)
            
            self.logger.info(f"Глобальна дедуплікація: знайдено {duplicates_found} дублікатів, "
                            f"підтягнуто {ai_reused} речень з AI")
            
            return deduplicated_sentences
            
        except Exception as e:
            self.logger.error(f"Помилка глобальної дедуплікації: {e}")
            # Повертаємо оригінальні речення без enhancment'у
            return new_sentences

    def _get_existing_sentences_map(self) -> Dict[str, Dict]:
        """
        Отримує мапу всіх існуючих речень з бази даних
        
        Returns:
            Словник {normalized_text: {video_filename, ai_count}}
        """
        try:
            sentences_map = {}
            
            # Отримуємо всі відео з бази даних
            from processing.database_manager import DatabaseManager
            db_manager = DatabaseManager()
            
            videos = db_manager.get_all_videos()
            
            for video in videos:
                try:
                    # Отримуємо сегменти для кожного відео
                    segments = db_manager.get_video_segments(video['id'])
                    
                    # ВИПРАВЛЕННЯ: Використовуємо простий розбір без дедуплікації
                    video_sentences = self._split_text_simple(segments)
                    
                    for sentence in video_sentences:
                        normalized_text = self._normalize_sentence_for_comparison(sentence['text'])
                        
                        if normalized_text not in sentences_map:
                            # Перевіряємо скільки AI відповідей є для цього речення
                            ai_count = self._count_ai_responses_for_sentence(
                                sentence['text'], video['filename'], sentence['start_time']
                            )
                            
                            sentences_map[normalized_text] = {
                                'video_filename': video['filename'],
                                'ai_count': ai_count,
                                'original_text': sentence['text'],
                                'start_time': sentence['start_time']
                            }
                    
                except Exception as e:
                    self.logger.warning(f"Помилка обробки відео {video['filename']}: {e}")
                    continue
            
            self.logger.debug(f"Завантажено {len(sentences_map)} унікальних речень з бази")
            return sentences_map
            
        except Exception as e:
            self.logger.error(f"Помилка завантаження існуючих речень: {e}")
            return {}

    def _split_text_simple(self, segments: List[Dict]) -> List[Dict]:
        """
        Простий розбір тексту на речення БЕЗ дедуплікації (для внутрішнього використання)
        
        Args:
            segments: Сегменти з БД
            
        Returns:
            Список речень без дедуплікації
        """
        sentences = []
        
        for segment in segments:
            text = segment['text'].strip()
            
            # Визначаємо формат часових міток
            if 'start_time' in segment:
                start_time = segment['start_time']
                end_time = segment['end_time']
            elif 'start' in segment:
                start_time = segment['start']
                end_time = segment['end']
            else:
                continue
            
            # Простий розподіл по реченнях
            sentence_pattern = r'([.!?]+)'
            parts = re.split(sentence_pattern, text)
            
            current_sentence = ""
            sentence_start = start_time
            
            for i, part in enumerate(parts):
                if part.strip():
                    current_sentence += part
                    
                    # Якщо це кінець речення
                    if re.match(sentence_pattern, part):
                        if current_sentence.strip():
                            progress = (i + 1) / len(parts)
                            sentence_end = sentence_start + (end_time - sentence_start) * progress
                            
                            sentences.append({
                                'text': current_sentence.strip(),
                                'start_time': float(sentence_start),
                                'end_time': float(min(sentence_end, end_time)),
                                'confidence': segment.get('confidence', 0.0)
                            })
                            
                            current_sentence = ""
                            sentence_start = sentence_end
            
            # Текст без кінцевої пунктуації
            if current_sentence.strip():
                sentences.append({
                    'text': current_sentence.strip(),
                    'start_time': float(sentence_start),
                    'end_time': float(end_time),
                    'confidence': segment.get('confidence', 0.0)
                })
        
        # Фільтруємо короткі речення
        return [s for s in sentences if len(s['text'].strip()) >= 10 
                and not re.match(r'^[.!?\s]+$', s['text'])]

    def _count_ai_responses_for_sentence(self, sentence_text: str, 
                                    video_filename: str, start_time: float) -> int:
        """
        Підраховує кількість AI відповідей для речення
        
        Returns:
            Кількість AI відповідей (translation + grammar + custom)
        """
        try:
            ai_count = 0
            
            # Перевіряємо переклад
            translation = self.data_manager.get_ai_response(
                sentence_text=sentence_text,
                video_filename=video_filename,
                start_time=start_time,
                response_type='translation'
            )
            if translation:
                ai_count += 1
            
            # Перевіряємо граматику
            grammar = self.data_manager.get_ai_response(
                sentence_text=sentence_text,
                video_filename=video_filename,
                start_time=start_time,
                response_type='grammar'
            )
            if grammar:
                ai_count += 1
            
            # Можна додати перевірку кастомних запитів, але це складніше
            # через різні промпти
            
            return ai_count
            
        except Exception as e:
            self.logger.debug(f"Помилка підрахунку AI відповідей: {e}")
            return 0

    def process_single_video(self, video_info: Dict) -> Dict:
        """
        Обробляє один відео файл з дедуплікацією речень
        
        Args:
            video_info: Інформація про відео
            
        Returns:
            Результат обробки з статистикою дедуплікації
        """
        start_time = time.time()
        filename = video_info["filename"]
        filepath = video_info["filepath"]
        
        result = {
            "filename": filename,
            "success": False,
            "sentences_count": 0,
            "unique_sentences": 0,
            "duplicates_found": 0,
            "ai_reused": 0,
            "processing_time": 0.0,
            "error": None
        }
        
        try:
            self.logger.info(f"Початок обробки: {filename}")
            
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
            
            # ДІАГНОСТИКА: Логуємо структуру сегментів
            segments = transcription_result.get("segments", [])
            if segments:
                self.logger.info(f"Приклад сегменту: {segments[0]}")
                self.logger.info(f"Ключі сегменту: {list(segments[0].keys())}")
            
            # 4. Додаємо транскрипцію в основну БД
            transcription_id = self.db_manager.add_transcription(video_id, transcription_result)
            
            # 5. Розбиваємо на речення з локальною дедуплікацією
            self.logger.info(f"Розбивка на речення: {len(segments)} сегментів")
            sentences = self.split_text_into_sentences(segments)
            self.logger.info(f"Отримано {len(sentences)} унікальних речень після локальної дедуплікації")
            
            # 6. НОВА ФУНКЦІЯ: Глобальна дедуплікація з існуючими реченнями
            self.logger.info("Глобальна дедуплікація з існуючими реченнями...")
            enhanced_sentences = self.deduplicate_with_existing_sentences(sentences, filename)
            
            # Підраховуємо статистику
            duplicates_found = sum(1 for s in enhanced_sentences if s.get('has_existing_ai', False))
            ai_reused = sum(1 for s in enhanced_sentences 
                        if s.get('has_existing_ai', False) and s.get('ai_responses_count', 0) > 0)
            
            result.update({
                "sentences_count": len(enhanced_sentences),
                "unique_sentences": len(enhanced_sentences) - duplicates_found,
                "duplicates_found": duplicates_found,
                "ai_reused": ai_reused
            })
            
            # ДІАГНОСТИКА: Логуємо приклад речення
            if enhanced_sentences:
                self.logger.info(f"Приклад речення: {enhanced_sentences[0]}")
            
            # 7. НОВА ФУНКЦІЯ: Копіюємо AI відповіді для дублікатів
            self.copy_ai_responses_for_duplicates(enhanced_sentences, filename)
            
            # 8. Зберігаємо стан в data_manager
            state_id = self.data_manager.save_video_state(
                video_filename=filename,
                video_path=filepath,
                sentences_count=len(enhanced_sentences)
            )
            
            # 9. Позначаємо як завершену обробку
            import sqlite3
            with sqlite3.connect(self.data_manager.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE video_processing_state 
                    SET processing_completed = TRUE, sentences_extracted = ?
                    WHERE video_filename = ?
                """, (len(enhanced_sentences), filename))
                conn.commit()
            
            result.update({
                "success": True,
                "video_id": video_id,
                "transcription_id": transcription_id,
                "state_id": state_id
            })
            
            self.processing_stats["videos_processed"] += 1
            self.processing_stats["sentences_extracted"] += len(enhanced_sentences)
            
            self.logger.info(f"Обробка завершена: {filename}")
            self.logger.info(f"  📊 Всього речень: {len(enhanced_sentences)}")
            self.logger.info(f"  🆕 Нових речень: {len(enhanced_sentences) - duplicates_found}")
            self.logger.info(f"  🔄 Дублікатів знайдено: {duplicates_found}")
            self.logger.info(f"  🤖 AI відповідей підтягнуто: {ai_reused}")
            
        except Exception as e:
            error_msg = f"Помилка обробки {filename}: {str(e)}"
            self.logger.error(error_msg)
            
            # ДІАГНОСТИКА: Більше деталей помилки
            import traceback
            self.logger.error(f"Деталі помилки:\n{traceback.format_exc()}")
            
            result["error"] = error_msg
            self.processing_stats["videos_failed"] += 1
            
            # Зберігаємо інформацію про невдалу обробку
            try:
                self.data_manager.save_video_state(
                    video_filename=filename,
                    video_path=filepath,
                    sentences_count=0
                )
            except Exception:
                pass
        
        finally:
            result["processing_time"] = time.time() - start_time
            self.processing_stats["processing_time"] += result["processing_time"]

        return result

    def copy_ai_responses_for_duplicates(self, enhanced_sentences: List[Dict], 
                                    target_video_filename: str):
        """
        Копіює AI відповіді для речень-дублікатів у нове відео
        
        Args:
            enhanced_sentences: Речення з інформацією про дублікати
            target_video_filename: Назва цільового відео
        """
        try:
            copied_responses = 0
            
            for sentence in enhanced_sentences:
                if sentence.get('has_existing_ai', False) and sentence.get('ai_responses_count', 0) > 0:
                    source_video = sentence['existing_ai_source']
                    
                    # Знаходимо оригінальне речення в базі
                    original_sentence_data = self._find_original_sentence(
                        sentence['text'], source_video
                    )
                    
                    if original_sentence_data:
                        # Копіюємо переклад
                        translation = self.data_manager.get_ai_response(
                            sentence_text=original_sentence_data['text'],
                            video_filename=source_video,
                            start_time=original_sentence_data['start_time'],
                            response_type='translation'
                        )
                        
                        if translation:
                            self.data_manager.save_ai_response(
                                sentence_text=sentence['text'],
                                video_filename=target_video_filename,
                                start_time=sentence['start_time'],
                                end_time=sentence['end_time'],
                                response_type='translation',
                                ai_response=translation['ai_response'],
                                ai_client=translation['ai_client']
                            )
                            copied_responses += 1
                        
                        # Копіюємо граматику
                        grammar = self.data_manager.get_ai_response(
                            sentence_text=original_sentence_data['text'],
                            video_filename=source_video,
                            start_time=original_sentence_data['start_time'],
                            response_type='grammar'
                        )
                        
                        if grammar:
                            self.data_manager.save_ai_response(
                                sentence_text=sentence['text'],
                                video_filename=target_video_filename,
                                start_time=sentence['start_time'],
                                end_time=sentence['end_time'],
                                response_type='grammar',
                                ai_response=grammar['ai_response'],
                                ai_client=grammar['ai_client']
                            )
                            copied_responses += 1
            
            if copied_responses > 0:
                self.logger.info(f"Скопійовано {copied_responses} AI відповідей для дублікатів")
                
        except Exception as e:
            self.logger.error(f"Помилка копіювання AI відповідей: {e}")

    def _find_original_sentence(self, sentence_text: str, source_video: str) -> Optional[Dict]:
        """
        Знаходить оригінальне речення в базі для копіювання AI відповідей
        
        Returns:
            Словник з інформацією про оригінальне речення або None
        """
        try:
            from processing.database_manager import DatabaseManager
            db_manager = DatabaseManager()
            
            # Знаходимо відео
            videos = db_manager.get_all_videos()
            video = next((v for v in videos if v['filename'] == source_video), None)
            
            if not video:
                return None
            
            # Отримуємо сегменти та розбиваємо на речення
            segments = db_manager.get_video_segments(video['id'])
            # ВИПРАВЛЕННЯ: Використовуємо простий розбір
            sentences = self._split_text_simple(segments)
            
            # Шукаємо найбільш схоже речення
            normalized_target = self._normalize_sentence_for_comparison(sentence_text)
            
            for sentence in sentences:
                normalized_source = self._normalize_sentence_for_comparison(sentence['text'])
                if normalized_source == normalized_target:
                    return sentence
            
            return None
            
        except Exception as e:
            self.logger.error(f"Помилка пошуку оригінального речення: {e}")
            return None
    
    def process_all_videos(self, force_reprocess: bool = False) -> Dict:
        """
        Обробляє всі відео файли
        
        Args:
            force_reprocess: Чи перепроцесувати всі файли
            
        Returns:
            Загальний результат обробки
        """
        start_time = time.time()
        
        # Скидаємо статистику
        self.processing_stats = {
            "videos_found": 0,
            "videos_new": 0,
            "videos_changed": 0,
            "videos_processed": 0,
            "videos_failed": 0,
            "sentences_extracted": 0,
            "processing_time": 0.0
        }
        
        self.logger.info("Початок обробки всіх відео")
        
        # Скануємо папку з відео
        video_files = self.scan_videos_directory()
        
        if not video_files:
            return {
                "success": True,
                "message": "Відео файли не знайдені",
                "stats": self.processing_stats
            }
        
        # Результати обробки
        processing_results = []
        
        # Обробляємо кожен файл
        for video_info in video_files:
            filename = video_info["filename"]
            
            # Перевіряємо стан файлу
            if not force_reprocess:
                status = self.check_video_changes(video_info)
                
                if status == 'processed':
                    self.logger.info(f"Пропущено (вже оброблено): {filename}")
                    continue
                elif status == 'new':
                    self.processing_stats["videos_new"] += 1
                elif status == 'changed':
                    self.processing_stats["videos_changed"] += 1
                    self.logger.info(f"Файл змінився: {filename}")
            
            # Обробляємо відео
            result = self.process_single_video(video_info)
            processing_results.append(result)
        
        # Підсумковий результат
        total_time = time.time() - start_time
        self.processing_stats["processing_time"] = total_time
        
        success_count = len([r for r in processing_results if r["success"]])
        total_sentences = sum(r["sentences_count"] for r in processing_results)
        
        summary = {
            "success": True,
            "message": f"Оброблено {success_count}/{len(processing_results)} відео",
            "stats": self.processing_stats,
            "total_sentences": total_sentences,
            "total_time": total_time,
            "results": processing_results
        }
        
        self.logger.info(f"Обробка завершена: {success_count}/{len(processing_results)} успішно")
        self.logger.info(f"Загальний час: {total_time:.1f} секунд")
        self.logger.info(f"Речень витягнуто: {total_sentences}")
        
        return summary
    
    def get_processed_videos_summary(self) -> List[Dict]:
        """
        Отримує зведення по всіх оброблених відео
        
        Returns:
            Список відео зі статистикою
        """
        video_states = self.data_manager.get_all_video_states()
        summary = []
        
        for state in video_states:
            filename = state["video_filename"]
            
            # Отримуємо кількість AI відповідей
            with self.data_manager.db_path.open() as conn:
                import sqlite3
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT COUNT(DISTINCT sentence_hash) as sentences_with_ai
                    FROM ai_responses 
                    WHERE video_filename = ?
                """, (filename,))
                
                ai_count = cursor.fetchone()[0] if cursor.fetchone() else 0
            
            summary.append({
                "filename": filename,
                "sentences_total": state["sentences_extracted"],
                "sentences_with_ai": ai_count,
                "processing_completed": state["processing_completed"],
                "last_processed": state["last_processed"],
                "ai_coverage": round((ai_count / state["sentences_extracted"]) * 100, 1) if state["sentences_extracted"] > 0 else 0
            })
        
        return sorted(summary, key=lambda x: x["last_processed"], reverse=True)
    
    def cleanup_temp_files(self):
        """Очищає тимчасові файли"""
        temp_dir = Path("temp")
        if temp_dir.exists():
            for file_path in temp_dir.iterdir():
                try:
                    if file_path.is_file():
                        file_path.unlink()
                except Exception as e:
                    self.logger.warning(f"Не вдалося видалити {file_path}: {e}")

# Приклад використання
if __name__ == "__main__":
    # Налаштування логування
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Створення процесора
    processor = VideoProcessor()
    
    # Тест сканування
    print("=== Сканування відео ===")
    videos = processor.scan_videos_directory()
    for video in videos:
        print(f"📹 {video['filename']} ({video['size']/1024/1024:.1f} MB)")
    
    # Тест обробки всіх відео
    print("\n=== Обробка всіх відео ===")
    result = processor.process_all_videos()
    
    print(f"Результат: {result['message']}")
    print(f"Статистика: {result['stats']}")
    
    # Зведення
    print("\n=== Зведення по відео ===")
    summary = processor.get_processed_videos_summary()
    for item in summary:
        print(f"📹 {item['filename']}: {item['sentences_total']} речень, "
              f"{item['sentences_with_ai']} з AI ({item['ai_coverage']}%)")