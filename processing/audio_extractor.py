"""
Audio Extractor - модуль для витягування аудіо з відео файлів
Підтримує формати: MKV, MP4, AVI та інші
"""

import os
import subprocess
import logging
from pathlib import Path
from typing import Optional, Union

class AudioExtractor:
    """Клас для витягування аудіо з відео файлів використовуючи FFmpeg"""
    
    def __init__(self, output_dir: str = "processed/audio"):
        """
        Ініціалізація екстрактора
        
        Args:
            output_dir: Папка для збереження аудіо файлів
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Налаштування логування
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Підтримувані формати відео
        self.supported_formats = {'.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv'}
    
    def check_ffmpeg(self) -> bool:
        """Перевіряє чи встановлений FFmpeg"""
        try:
            result = subprocess.run(['ffmpeg', '-version'], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=10)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def extract_audio(self, 
                     video_path: Union[str, Path], 
                     output_format: str = 'wav',
                     sample_rate: int = 16000,
                     channels: int = 1) -> Optional[Path]:
        """
        Витягує аудіо з відео файлу
        
        Args:
            video_path: Шлях до відео файлу
            output_format: Формат аудіо (wav, flac, mp3)
            sample_rate: Частота дискретизації (16000 для Whisper)
            channels: Кількість каналів (1 = моно, 2 = стерео)
            
        Returns:
            Path до створеного аудіо файлу або None при помилці
        """
        video_path = Path(video_path)
        
        # Перевірки
        if not video_path.exists():
            self.logger.error(f"Відео файл не знайдено: {video_path}")
            return None
            
        if video_path.suffix.lower() not in self.supported_formats:
            self.logger.error(f"Непідтримуваний формат: {video_path.suffix}")
            return None
            
        if not self.check_ffmpeg():
            self.logger.error("FFmpeg не знайдено! Встанови FFmpeg")
            return None
        
        # Створення назви аудіо файлу
        audio_filename = f"{video_path.stem}.{output_format}"
        audio_path = self.output_dir / audio_filename
        
        # Якщо аудіо вже існує, пропускаємо
        if audio_path.exists():
            self.logger.info(f"Аудіо вже існує: {audio_path}")
            return audio_path
        
        # FFmpeg команда для витягування аудіо
        ffmpeg_cmd = [
            'ffmpeg',
            '-i', str(video_path),           # Вхідний файл
            '-vn',                           # Без відео
            '-acodec', 'pcm_s16le',         # Аудіо кодек
            '-ar', str(sample_rate),         # Частота дискретизації
            '-ac', str(channels),            # Кількість каналів
            '-y',                            # Перезаписати якщо існує
            str(audio_path)                  # Вихідний файл
        ]
        
        try:
            self.logger.info(f"Початок витягування аудіо з {video_path.name}")
            
            # Виконання FFmpeg
            result = subprocess.run(ffmpeg_cmd, 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=3600)  # 1 година таймаут
            
            if result.returncode == 0:
                self.logger.info(f"Аудіо успішно витягнуто: {audio_path}")
                return audio_path
            else:
                self.logger.error(f"Помилка FFmpeg: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            self.logger.error("Таймаут витягування аудіо")
            return None
        except Exception as e:
            self.logger.error(f"Неочікувана помилка: {e}")
            return None
    
    def get_video_info(self, video_path: Union[str, Path]) -> Optional[dict]:
        """
        Отримує інформацію про відео файл
        
        Args:
            video_path: Шлях до відео файлу
            
        Returns:
            Словник з інформацією про відео
        """
        video_path = Path(video_path)
        
        if not video_path.exists():
            return None
        
        ffprobe_cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            str(video_path)
        ]
        
        try:
            result = subprocess.run(ffprobe_cmd, 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=30)
            
            if result.returncode == 0:
                import json
                return json.loads(result.stdout)
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"Помилка отримання інформації: {e}")
            return None
    
    def extract_from_directory(self, video_dir: Union[str, Path]) -> list:
        """
        Витягує аудіо з усіх відео файлів в папці
        
        Args:
            video_dir: Папка з відео файлами
            
        Returns:
            Список шляхів до створених аудіо файлів
        """
        video_dir = Path(video_dir)
        extracted_files = []
        
        if not video_dir.exists():
            self.logger.error(f"Папка не знайдена: {video_dir}")
            return extracted_files
        
        # Знаходимо всі відео файли
        video_files = []
        for ext in self.supported_formats:
            video_files.extend(video_dir.glob(f"*{ext}"))
        
        self.logger.info(f"Знайдено {len(video_files)} відео файлів")
        
        # Обробляємо кожен файл
        for video_file in video_files:
            audio_path = self.extract_audio(video_file)
            if audio_path:
                extracted_files.append(audio_path)
        
        self.logger.info(f"Успішно оброблено {len(extracted_files)} файлів")
        return extracted_files


# Приклад використання
if __name__ == "__main__":
    # Створюємо екстрактор
    extractor = AudioExtractor()
    
    # Витягуємо аудіо з одного файлу
    video_path = "videos/your_video.mkv"
    audio_path = extractor.extract_audio(video_path)
    
    if audio_path:
        print(f"Аудіо збережено: {audio_path}")
    else:
        print("Помилка витягування аудіо")
    
    # Або обробляємо всю папку
    # extracted_files = extractor.extract_from_directory("videos/")
    # print(f"Оброблено файлів: {len(extracted_files)}")