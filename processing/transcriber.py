"""
Transcriber - модуль для транскрипції аудіо в текст використовуючи Whisper
Підтримує різні моделі Whisper та зберігає результати з часовими мітками
"""

import os
import json
import logging
import torch
import whisper
from pathlib import Path
from typing import Optional, Union, Dict, List
from datetime import datetime

class Transcriber:
    """Клас для транскрипції аудіо файлів в текст з часовими мітками"""
    
    def __init__(self, 
                 model_size: str = "base",
                 output_dir: str = "processed/subtitles",
                 device: str = "auto"):
        """
        Ініціалізація транскрибера
        
        Args:
            model_size: Розмір Whisper моделі (tiny, base, small, medium, large, large-v2, large-v3)
            output_dir: Папка для збереження транскрипцій
            device: Пристрій для обчислень (auto, cuda, cpu)
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Налаштування логування
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Автовизначення пристрою
        if device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
            
        self.logger.info(f"Використовується пристрій: {self.device}")
        
        # Завантаження моделі Whisper
        self.model_size = model_size
        self.model = None
        self._load_model()
        
        # Підтримувані мови
        self.supported_languages = {
            'en': 'English',
            'uk': 'Ukrainian', 
            'ru': 'Russian',
            'de': 'German',
            'fr': 'French',
            'es': 'Spanish'
        }
    
    def _load_model(self):
        """Завантажує модель Whisper"""
        try:
            self.logger.info(f"Завантаження Whisper модель: {self.model_size}")
            self.model = whisper.load_model(self.model_size, device=self.device)
            self.logger.info("Модель успішно завантажена!")
        except Exception as e:
            self.logger.error(f"Помилка завантаження моделі: {e}")
            raise
    
    def transcribe_audio(self, 
                        audio_path: Union[str, Path],
                        language: str = "en",
                        translate_to_english: bool = False) -> Optional[Dict]:
        """
        Транскрибує аудіо файл в текст
        
        Args:
            audio_path: Шлях до аудіо файлу
            language: Мова аудіо (en, uk, ru, etc.)
            translate_to_english: Чи перекладати на англійську
            
        Returns:
            Словник з результатами транскрипції
        """
        audio_path = Path(audio_path)
        
        if not audio_path.exists():
            self.logger.error(f"Аудіо файл не знайдено: {audio_path}")
            return None
        
        if not self.model:
            self.logger.error("Модель Whisper не завантажена")
            return None
        
        # Створення назви файлу для збереження
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"{audio_path.stem}_{timestamp}"
        
        try:
            self.logger.info(f"Початок транскрипції: {audio_path.name}")
            
            # Опції для Whisper
            options = {
                "language": language if not translate_to_english else None,
                "task": "translate" if translate_to_english else "transcribe",
                "verbose": False,
                "word_timestamps": True  # Часові мітки для слів
            }
            
            # Транскрипція
            result = self.model.transcribe(str(audio_path), **options)
            
            # Додаткова інформація
            transcription_data = {
                "audio_file": str(audio_path),
                "model_size": self.model_size,
                "language": result.get("language", language),
                "duration": self._get_audio_duration(result),
                "timestamp": datetime.now().isoformat(),
                "segments": result["segments"],
                "full_text": result["text"].strip()
            }
            
            # Збереження результатів
            self._save_transcription(transcription_data, output_filename)
            
            self.logger.info(f"Транскрипція завершена: {len(result['segments'])} сегментів")
            return transcription_data
            
        except Exception as e:
            self.logger.error(f"Помилка транскрипції: {e}")
            return None
    
    def _get_audio_duration(self, result: Dict) -> float:
        """Визначає тривалість аудіо з результатів Whisper"""
        if not result["segments"]:
            return 0.0
        return result["segments"][-1]["end"]
    
    def _save_transcription(self, data: Dict, filename: str):
        """Зберігає результати транскрипції в різних форматах"""
        # JSON формат (повна інформація)
        json_path = self.output_dir / f"{filename}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # SRT формат (субтитри)
        srt_path = self.output_dir / f"{filename}.srt"
        self._save_as_srt(data["segments"], srt_path)
        
        # TXT формат (тільки текст)
        txt_path = self.output_dir / f"{filename}.txt"
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(data["full_text"])
        
        self.logger.info(f"Збережено: {json_path.name}, {srt_path.name}, {txt_path.name}")
    
    def _save_as_srt(self, segments: List[Dict], srt_path: Path):
        """Зберігає сегменти як SRT субтитри"""
        with open(srt_path, 'w', encoding='utf-8') as f:
            for i, segment in enumerate(segments, 1):
                start_time = self._seconds_to_srt_time(segment["start"])
                end_time = self._seconds_to_srt_time(segment["end"])
                text = segment["text"].strip()
                
                f.write(f"{i}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{text}\n\n")
    
    def _seconds_to_srt_time(self, seconds: float) -> str:
        """Конвертує секунди в формат SRT часу"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    def transcribe_directory(self, 
                           audio_dir: Union[str, Path],
                           language: str = "en") -> List[Dict]:
        """
        Транскрибує всі аудіо файли в папці
        
        Args:
            audio_dir: Папка з аудіо файлами
            language: Мова аудіо файлів
            
        Returns:
            Список результатів транскрипції
        """
        audio_dir = Path(audio_dir)
        results = []
        
        if not audio_dir.exists():
            self.logger.error(f"Папка не знайдена: {audio_dir}")
            return results
        
        # Знаходимо всі аудіо файли
        audio_files = []
        for ext in ['.wav', '.flac', '.mp3', '.m4a']:
            audio_files.extend(audio_dir.glob(f"*{ext}"))
        
        self.logger.info(f"Знайдено {len(audio_files)} аудіо файлів")
        
        # Обробляємо кожен файл
        for audio_file in audio_files:
            result = self.transcribe_audio(audio_file, language)
            if result:
                results.append(result)
        
        self.logger.info(f"Успішно транскрибовано {len(results)} файлів")
        return results
    
    def search_in_transcriptions(self, 
                                query: str, 
                                transcription_dir: Union[str, Path] = None) -> List[Dict]:
        """
        Пошук фрази в транскрипціях
        
        Args:
            query: Фраза для пошуку
            transcription_dir: Папка з транскрипціями (за замовчуванням self.output_dir)
            
        Returns:
            Список знайдених сегментів
        """
        if transcription_dir is None:
            transcription_dir = self.output_dir
        
        transcription_dir = Path(transcription_dir)
        results = []
        
        # Знаходимо всі JSON файли з транскрипціями
        json_files = transcription_dir.glob("*.json")
        
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Пошук в сегментах
                for segment in data["segments"]:
                    if query.lower() in segment["text"].lower():
                        results.append({
                            "file": data["audio_file"],
                            "start": segment["start"],
                            "end": segment["end"],
                            "text": segment["text"],
                            "transcription_file": str(json_file)
                        })
            
            except Exception as e:
                self.logger.error(f"Помилка читання {json_file}: {e}")
        
        return results
    
    def get_model_info(self) -> Dict:
        """Повертає інформацію про поточну модель"""
        return {
            "model_size": self.model_size,
            "device": self.device,
            "languages": self.supported_languages,
            "loaded": self.model is not None
        }


# Приклад використання
if __name__ == "__main__":
    # Створюємо транскрибер
    transcriber = Transcriber(model_size="base")  # Або "large-v3" для кращої якості
    
    # Транскрибуємо один файл
    audio_path = "processed/audio/your_audio.wav"
    result = transcriber.transcribe_audio(audio_path, language="en")
    
    if result:
        print(f"Транскрипція завершена: {len(result['segments'])} сегментів")
        print(f"Повний текст: {result['full_text'][:100]}...")
    
    # Пошук фрази
    search_results = transcriber.search_in_transcriptions("hello world")
    print(f"Знайдено результатів: {len(search_results)}")