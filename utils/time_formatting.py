"""
Утиліти для форматування часових міток у зручному форматі
"""

def format_time(seconds: float, short: bool = False) -> str:
    """
    Форматує час з секунд у зручний формат
    
    Args:
        seconds: Час у секундах (може бути float)
        short: Якщо True, використовує короткий формат (1х 18с)
    
    Returns:
        Відформатований рядок часу
    
    Examples:
        format_time(78) -> "1 хв 18 сек"
        format_time(78, short=True) -> "1х 18с"
        format_time(3661.5) -> "1 год 1 хв 1.5 сек"
        format_time(45.2) -> "45.2 сек"
    """
    if seconds < 0:
        return "0 сек" if not short else "0с"
    
    # Розбиваємо на компоненти
    total_seconds = int(seconds)
    milliseconds = seconds - total_seconds
    
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    remaining_seconds = total_seconds % 60
    
    # Додаємо мілісекунди назад до секунд
    final_seconds = remaining_seconds + milliseconds
    
    parts = []
    
    if short:
        # Короткий формат
        if hours > 0:
            parts.append(f"{hours}г")
        if minutes > 0:
            parts.append(f"{minutes}х")
        if final_seconds > 0 or not parts:  # Показуємо секунди якщо це єдине значення
            if final_seconds == int(final_seconds):
                parts.append(f"{int(final_seconds)}с")
            else:
                parts.append(f"{final_seconds:.1f}с")
    else:
        # Повний формат
        if hours > 0:
            parts.append(f"{hours} год")
        if minutes > 0:
            parts.append(f"{minutes} хв")
        if final_seconds > 0 or not parts:  # Показуємо секунди якщо це єдине значення
            if final_seconds == int(final_seconds):
                parts.append(f"{int(final_seconds)} сек")
            else:
                parts.append(f"{final_seconds:.1f} сек")
    
    return " ".join(parts)


def format_time_range(start_seconds: float, end_seconds: float, short: bool = False) -> str:
    """
    Форматує часовий діапазон
    
    Args:
        start_seconds: Початковий час у секундах
        end_seconds: Кінцевий час у секундах
        short: Використовувати короткий формат
    
    Returns:
        Відформатований діапазон часу
    
    Examples:
        format_time_range(78, 125) -> "1 хв 18 сек - 2 хв 5 сек"
        format_time_range(78, 125, short=True) -> "1х 18с - 2х 5с"
    """
    start_formatted = format_time(start_seconds, short)
    end_formatted = format_time(end_seconds, short)
    
    separator = " - " if not short else "-"
    return f"{start_formatted}{separator}{end_formatted}"


def format_duration(duration_seconds: float, short: bool = False) -> str:
    """
    Форматує тривалість (різниця між часами)
    
    Args:
        duration_seconds: Тривалість у секундах
        short: Використовувати короткий формат
    
    Returns:
        Відформатована тривалість
    
    Examples:
        format_duration(47) -> "47 сек"
        format_duration(125.5) -> "2 хв 5.5 сек"
    """
    return format_time(duration_seconds, short)


def parse_time_to_seconds(time_string: str) -> float:
    """
    Парсить рядок часу назад у секунди
    
    Args:
        time_string: Рядок типу "1 хв 18 сек" або "1х 18с"
    
    Returns:
        Час у секундах
    
    Examples:
        parse_time_to_seconds("1 хв 18 сек") -> 78.0
        parse_time_to_seconds("1х 18с") -> 78.0
        parse_time_to_seconds("45.2 сек") -> 45.2
    """
    import re
    
    total_seconds = 0.0
    
    # Patterns для різних форматів
    patterns = [
        (r'(\d+(?:\.\d+)?)\s*г(?:од)?', 3600),  # години
        (r'(\d+(?:\.\d+)?)\s*х(?:в)?', 60),     # хвилини
        (r'(\d+(?:\.\d+)?)\s*с(?:ек)?', 1),     # секунди
    ]
    
    for pattern, multiplier in patterns:
        matches = re.findall(pattern, time_string.lower())
        for match in matches:
            total_seconds += float(match) * multiplier
    
    return total_seconds


def format_timestamp(seconds: float, include_ms: bool = True) -> str:
    """
    Форматує час у форматі timestamp (HH:MM:SS або MM:SS)
    
    Args:
        seconds: Час у секундах
        include_ms: Включати мілісекунди
    
    Returns:
        Timestamp формат
    
    Examples:
        format_timestamp(78) -> "01:18"
        format_timestamp(3661.5) -> "01:01:01.5"
        format_timestamp(45.2, include_ms=False) -> "00:45"
    """
    total_seconds = int(seconds)
    milliseconds = seconds - total_seconds
    
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    remaining_seconds = total_seconds % 60
    
    if hours > 0:
        if include_ms and milliseconds > 0:
            return f"{hours:02d}:{minutes:02d}:{remaining_seconds:02d}.{int(milliseconds*10)}"
        else:
            return f"{hours:02d}:{minutes:02d}:{remaining_seconds:02d}"
    else:
        if include_ms and milliseconds > 0:
            return f"{minutes:02d}:{remaining_seconds:02d}.{int(milliseconds*10)}"
        else:
            return f"{minutes:02d}:{remaining_seconds:02d}"


# ==============================================================
# ОНОВЛЕНІ ФУНКЦІЇ ДЛЯ ІНТЕГРАЦІЇ В ПРОЕКТ
# ==============================================================

def update_sentence_widget_time_display():
    """
    Приклад того, як оновити відображення часу в SentenceWidget
    Додайте цей код до вашого sentence_widget.py
    """
    return """
    # У методі create_english_section() замініть:
    # time_text = f"{self.sentence_data['start_time']:.1f}s"
    # НА:
    time_text = format_time(self.sentence_data['start_time'], short=True)
    
    # Для діапазону часу:
    time_range_text = format_time_range(
        self.sentence_data['start_time'], 
        self.sentence_data['end_time'], 
        short=True
    )
    
    # Для тривалості:
    duration = self.sentence_data['end_time'] - self.sentence_data['start_time']
    duration_text = format_duration(duration, short=True)
    """


def update_main_window_time_display():
    """
    Приклад того, як оновити відображення часу в MainWindow
    Додайте цей код до вашого main_window.py
    """
    return """
    # У методі display_sentences() замініть:
    # self.sentences_title.config(text=f"📖 {filename}")
    # НА:
    total_duration = sum(s['end_time'] - s['start_time'] for s in sentences)
    duration_text = format_duration(total_duration)
    self.sentences_title.config(text=f"📖 {filename} • {duration_text}")
    
    # Для статистики:
    stats_text = f"{len(sentences)} речень • {duration_text}"
    self.sentences_stats.config(text=stats_text)
    """


# ==============================================================
# ТЕСТУВАННЯ ФУНКЦІЙ
# ==============================================================

if __name__ == "__main__":
    """Тестування функцій форматування часу"""
    
    test_cases = [
        0,        # 0 сек
        5.5,      # 5.5 сек
        45,       # 45 сек
        78,       # 1 хв 18 сек
        125.7,    # 2 хв 5.7 сек
        3661.5,   # 1 год 1 хв 1.5 сек
        7200,     # 2 год
        3600,     # 1 год
        60,       # 1 хв
        90.25,    # 1 хв 30.25 сек
    ]
    
    print("Тестування форматування часу:")
    print("=" * 60)
    
    for seconds in test_cases:
        full_format = format_time(seconds, short=False)
        short_format = format_time(seconds, short=True)
        timestamp = format_timestamp(seconds)
        
        print(f"{seconds:>8.1f} сек -> {full_format:<20} | {short_format:<10} | {timestamp}")
    
    print("\nТестування діапазонів часу:")
    print("=" * 60)
    
    ranges = [
        (10, 45),      # 10с - 45с
        (78, 125),     # 1х18с - 2х5с
        (3600, 3720),  # 1г - 1г2х
    ]
    
    for start, end in ranges:
        full_range = format_time_range(start, end, short=False)
        short_range = format_time_range(start, end, short=True)
        duration = format_duration(end - start, short=True)
        
        print(f"{start}-{end} -> {full_range} (тривалість: {duration})")
    
    print("\nТестування парсингу:")
    print("=" * 60)
    
    parse_tests = [
        "45 сек",
        "1 хв 18 сек", 
        "1х 18с",
        "2 год 5 хв 30 сек",
        "1г 5х 30с"
    ]
    
    for test_string in parse_tests:
        parsed_seconds = parse_time_to_seconds(test_string)
        back_to_string = format_time(parsed_seconds)
        print(f"'{test_string}' -> {parsed_seconds} сек -> '{back_to_string}'")