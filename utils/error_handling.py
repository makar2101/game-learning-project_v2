"""
Утиліти для безпечної обробки помилок та захисту від рекурсії
Додайте цей файл як utils/error_handling.py
"""

import sys
import functools
import threading
import time
import logging
from typing import Callable, Any, Optional, Dict
import tkinter as tk


class RecursionProtector:
    """Захист від рекурсії та зависання GUI"""
    
    def __init__(self, max_depth: int = 50):
        self.max_depth = max_depth
        self.call_stack = {}
        self.lock = threading.Lock()
    
    def protect(self, func: Callable) -> Callable:
        """Декоратор для захисту від рекурсії"""
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            thread_id = threading.get_ident()
            func_name = f"{func.__module__}.{func.__qualname__}"
            
            with self.lock:
                if thread_id not in self.call_stack:
                    self.call_stack[thread_id] = {}
                
                current_depth = self.call_stack[thread_id].get(func_name, 0)
                
                if current_depth >= self.max_depth:
                    logger = logging.getLogger(__name__)
                    logger.error(f"Рекурсія запобіжена для {func_name} (глибина: {current_depth})")
                    return None
                
                self.call_stack[thread_id][func_name] = current_depth + 1
            
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                with self.lock:
                    if thread_id in self.call_stack and func_name in self.call_stack[thread_id]:
                        self.call_stack[thread_id][func_name] -= 1
                        if self.call_stack[thread_id][func_name] <= 0:
                            del self.call_stack[thread_id][func_name]
                        if not self.call_stack[thread_id]:
                            del self.call_stack[thread_id]
        
        return wrapper


class SafeGUIManager:
    """Менеджер для безпечної роботи з GUI"""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.pending_updates = []
        self.update_scheduled = False
        self.logger = logging.getLogger(__name__)
    
    def safe_after(self, delay: int, func: Callable, *args, **kwargs):
        """Безпечний виклик after з перевіркою існування віджетів"""
        
        def safe_wrapper():
            try:
                if self.root and self.root.winfo_exists():
                    func(*args, **kwargs)
            except tk.TclError as e:
                if "invalid command name" not in str(e):
                    self.logger.error(f"TclError в safe_after: {e}")
            except Exception as e:
                self.logger.error(f"Помилка в safe_after: {e}")
        
        try:
            if self.root and self.root.winfo_exists():
                self.root.after(delay, safe_wrapper)
        except:
            pass
    
    def batch_update(self, func: Callable, *args, **kwargs):
        """Батчеві оновлення GUI для зменшення навантаження"""
        self.pending_updates.append((func, args, kwargs))
        
        if not self.update_scheduled:
            self.update_scheduled = True
            self.safe_after(10, self._process_batch_updates)
    
    def _process_batch_updates(self):
        """Обробляє батч оновлень"""
        try:
            updates_to_process = self.pending_updates[:10]  # Максимум 10 за раз
            self.pending_updates = self.pending_updates[10:]
            
            for func, args, kwargs in updates_to_process:
                try:
                    func(*args, **kwargs)
                except Exception as e:
                    self.logger.error(f"Помилка в batch update: {e}")
            
            # Якщо ще є оновлення, продовжуємо
            if self.pending_updates:
                self.safe_after(5, self._process_batch_updates)
            else:
                self.update_scheduled = False
                
        except Exception as e:
            self.logger.error(f"Помилка обробки batch updates: {e}")
            self.update_scheduled = False


class ErrorReporter:
    """Система звітування про помилки"""
    
    def __init__(self, log_file: str = "logs/errors.log"):
        self.log_file = log_file
        self.error_counts = {}
        self.last_errors = {}
        
        # Налаштовуємо логування помилок
        self.setup_error_logging()
    
    def setup_error_logging(self):
        """Налаштовує логування помилок"""
        try:
            from pathlib import Path
            Path(self.log_file).parent.mkdir(exist_ok=True)
            
            error_logger = logging.getLogger('error_reporter')
            error_logger.setLevel(logging.ERROR)
            
            handler = logging.FileHandler(self.log_file, encoding='utf-8')
            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            error_logger.addHandler(handler)
            
            self.logger = error_logger
            
        except Exception:
            self.logger = logging.getLogger(__name__)
    
    def report_error(self, error: Exception, context: str = "", 
                    suppress_duplicates: bool = True):
        """Звітує про помилку з контекстом"""
        
        error_key = f"{type(error).__name__}:{str(error)}"
        current_time = time.time()
        
        # Перевірка на дублікати
        if suppress_duplicates:
            if error_key in self.last_errors:
                if current_time - self.last_errors[error_key] < 60:  # 1 хвилина
                    self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
                    return
        
        self.last_errors[error_key] = current_time
        
        # Формуємо повідомлення
        count_info = ""
        if error_key in self.error_counts and self.error_counts[error_key] > 0:
            count_info = f" (повторилася {self.error_counts[error_key]} разів)"
            self.error_counts[error_key] = 0
        
        message = f"ПОМИЛКА{count_info}"
        if context:
            message += f" в {context}"
        
        message += f": {type(error).__name__}: {error}"
        
        # Логуємо
        self.logger.error(message)
        
        # Стек викликів для серйозних помилок
        if isinstance(error, (RecursionError, MemoryError, SystemError)):
            import traceback
            self.logger.error(f"Стек викликів:\n{traceback.format_exc()}")


class WidgetStateManager:
    """Менеджер для відстеження стану віджетів"""
    
    def __init__(self):
        self.widget_states = {}
        self.destroyed_widgets = set()
        self.lock = threading.Lock()
    
    def register_widget(self, widget_id: str, widget: tk.Widget):
        """Реєструє віджет для відстеження"""
        with self.lock:
            self.widget_states[widget_id] = {
                'widget': widget,
                'created_at': time.time(),
                'is_destroyed': False
            }
    
    def mark_destroyed(self, widget_id: str):
        """Позначає віджет як знищений"""
        with self.lock:
            if widget_id in self.widget_states:
                self.widget_states[widget_id]['is_destroyed'] = True
                self.destroyed_widgets.add(widget_id)
    
    def is_safe_to_use(self, widget_id: str) -> bool:
        """Перевіряє чи безпечно використовувати віджет"""
        with self.lock:
            if widget_id in self.destroyed_widgets:
                return False
            
            if widget_id not in self.widget_states:
                return False
            
            state = self.widget_states[widget_id]
            if state['is_destroyed']:
                return False
            
            try:
                widget = state['widget']
                return widget.winfo_exists()
            except:
                return False
    
    def safe_widget_call(self, widget_id: str, func: Callable, *args, **kwargs):
        """Безпечний виклик методу віджета"""
        if not self.is_safe_to_use(widget_id):
            return None
        
        try:
            state = self.widget_states[widget_id]
            widget = state['widget']
            return func(widget, *args, **kwargs)
        except tk.TclError:
            self.mark_destroyed(widget_id)
            return None
        except Exception as e:
            logging.getLogger(__name__).error(f"Помилка виклику віджета {widget_id}: {e}")
            return None


# Глобальні інстанси
recursion_protector = RecursionProtector(max_depth=30)
error_reporter = ErrorReporter()
widget_state_manager = WidgetStateManager()


def safe_gui_call(func: Callable) -> Callable:
    """Декоратор для безпечних викликів GUI"""
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except tk.TclError as e:
            if "invalid command name" not in str(e):
                error_reporter.report_error(e, f"GUI call {func.__name__}")
            return None
        except RecursionError as e:
            error_reporter.report_error(e, f"Recursion in {func.__name__}")
            return None
        except Exception as e:
            error_reporter.report_error(e, f"Unexpected error in {func.__name__}")
            return None
    
    return wrapper


def thread_safe_gui_update(root: tk.Tk, func: Callable, *args, **kwargs):
    """Безпечне оновлення GUI з іншого потоку"""
    
    def safe_update():
        try:
            if root and root.winfo_exists():
                func(*args, **kwargs)
        except Exception as e:
            error_reporter.report_error(e, "thread_safe_gui_update")
    
    try:
        if root and root.winfo_exists():
            root.after_idle(safe_update)
    except:
        pass


def memory_usage_monitor(threshold_mb: int = 500):
    """Моніторинг використання пам'яті"""
    
    try:
        import psutil
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        
        if memory_mb > threshold_mb:
            logger = logging.getLogger(__name__)
            logger.warning(f"Високе використання пам'яті: {memory_mb:.1f} MB")
            
            # Примусове збирання сміття
            import gc
            collected = gc.collect()
            logger.info(f"Garbage collector: зібрано {collected} об'єктів")
            
            return memory_mb
            
    except ImportError:
        # psutil не встановлений
        return 0
    except Exception as e:
        error_reporter.report_error(e, "memory_usage_monitor")
        return 0


class PerformanceMonitor:
    """Моніторинг продуктивності операцій"""
    
    def __init__(self):
        self.operation_times = {}
        self.slow_operations = []
    
    def time_operation(self, operation_name: str):
        """Декоратор для вимірювання часу операції"""
        
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    elapsed = time.time() - start_time
                    self._record_operation_time(operation_name, elapsed)
            return wrapper
        return decorator
    
    def _record_operation_time(self, operation_name: str, elapsed_time: float):
        """Записує час операції"""
        if operation_name not in self.operation_times:
            self.operation_times[operation_name] = []
        
        self.operation_times[operation_name].append(elapsed_time)
        
        # Попередження про повільні операції
        if elapsed_time > 2.0:  # Більше 2 секунд
            logger = logging.getLogger(__name__)
            logger.warning(f"Повільна операція {operation_name}: {elapsed_time:.2f}s")
            self.slow_operations.append((operation_name, elapsed_time, time.time()))
    
    def get_stats(self) -> Dict[str, Dict[str, float]]:
        """Отримує статистику продуктивності"""
        stats = {}
        
        for operation, times in self.operation_times.items():
            if times:
                stats[operation] = {
                    'count': len(times),
                    'total': sum(times),
                    'average': sum(times) / len(times),
                    'max': max(times),
                    'min': min(times)
                }
        
        return stats


# Глобальний монітор продуктивності
performance_monitor = PerformanceMonitor()


def cleanup_resources():
    """Очищення ресурсів при закритті програми"""
    try:
        # Очистка глобальних інстансів
        if hasattr(recursion_protector, 'call_stack'):
            recursion_protector.call_stack.clear()
        
        if hasattr(widget_state_manager, 'widget_states'):
            widget_state_manager.widget_states.clear()
            widget_state_manager.destroyed_widgets.clear()
        
        # Збирання сміття
        import gc
        collected = gc.collect()
        
        logger = logging.getLogger(__name__)
        logger.info(f"Ресурси очищено, зібрано {collected} об'єктів")
        
        # Статистика продуктивності
        stats = performance_monitor.get_stats()
        if stats:
            logger.info("Статистика продуктивності:")
            for operation, data in stats.items():
                logger.info(f"  {operation}: {data['count']} викликів, "
                           f"середній час: {data['average']:.3f}s")
        
    except Exception as e:
        try:
            logging.getLogger(__name__).error(f"Помилка очищення ресурсів: {e}")
        except:
            pass


class WidgetCreationOptimizer:
    """Оптимізатор для створення великої кількості віджетів"""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.creation_queue = []
        self.is_processing = False
        self.batch_size = 5
        self.delay_ms = 50
        self.max_widgets_per_frame = 10
        self.logger = logging.getLogger(__name__)
    
    def add_widget_creation(self, create_func: Callable, *args, **kwargs):
        """Додає віджет до черги створення"""
        self.creation_queue.append((create_func, args, kwargs))
        
        if not self.is_processing:
            self._start_processing()
    
    def _start_processing(self):
        """Запускає обробку черги"""
        if self.is_processing or not self.creation_queue:
            return
        
        self.is_processing = True
        self._process_next_batch()
    
    def _process_next_batch(self):
        """Обробляє наступний батч віджетів"""
        if not self.creation_queue:
            self.is_processing = False
            return
        
        # Беремо батч для обробки
        batch = self.creation_queue[:self.batch_size]
        self.creation_queue = self.creation_queue[self.batch_size:]
        
        widgets_created = 0
        
        for create_func, args, kwargs in batch:
            try:
                # Перевіряємо ліміт віджетів на кадр
                if widgets_created >= self.max_widgets_per_frame:
                    # Повертаємо решту назад у чергу
                    remaining = batch[widgets_created:]
                    self.creation_queue = remaining + self.creation_queue
                    break
                
                # Створюємо віджет
                result = create_func(*args, **kwargs)
                if result is not None:
                    widgets_created += 1
                
                # Перевіряємо пам'ять кожні 5 віджетів
                if widgets_created % 5 == 0:
                    memory_mb = memory_usage_monitor(threshold_mb=800)
                    if memory_mb > 800:
                        self.logger.warning("Зупинка створення віджетів через високе використання пам'яті")
                        break
                
            except Exception as e:
                error_reporter.report_error(e, f"widget creation batch {widgets_created}")
                continue
        
        # Оновлюємо GUI
        try:
            self.root.update_idletasks()
        except:
            pass
        
        # Плануємо наступний батч
        if self.creation_queue:
            try:
                self.root.after(self.delay_ms, self._process_next_batch)
            except:
                self.is_processing = False
        else:
            self.is_processing = False
            self.logger.info("Створення всіх віджетів завершено")
    
    def clear_queue(self):
        """Очищає чергу створення"""
        self.creation_queue.clear()
        self.is_processing = False


def apply_error_handling_to_main_window(main_window_class):
    """Застосовує обробку помилок до головного вікна"""
    
    # Декоруємо критичні методи
    original_display_sentences = main_window_class.display_sentences
    original_create_widgets_in_batches = main_window_class.create_widgets_in_batches
    original_clear_sentences = main_window_class.clear_sentences
    
    @performance_monitor.time_operation("display_sentences")
    @safe_gui_call
    @recursion_protector.protect
    def safe_display_sentences(self, sentences, filename):
        return original_display_sentences(self, sentences, filename)
    
    @performance_monitor.time_operation("create_widgets_in_batches")
    @safe_gui_call
    @recursion_protector.protect
    def safe_create_widgets_in_batches(self, sentences, filename, batch_size=5):
        return original_create_widgets_in_batches(self, sentences, filename, batch_size)
    
    @safe_gui_call
    def safe_clear_sentences(self):
        return original_clear_sentences(self)
    
    # Замінюємо методи
    main_window_class.display_sentences = safe_display_sentences
    main_window_class.create_widgets_in_batches = safe_create_widgets_in_batches
    main_window_class.clear_sentences = safe_clear_sentences
    
    return main_window_class


# ==============================================================
# EXAMPLE USAGE
# ==============================================================

if __name__ == "__main__":
    """Приклад використання утиліт обробки помилок"""
    
    import tkinter as tk
    
    # Створюємо тестове вікно
    root = tk.Tk()
    root.title("Тест обробки помилок")
    
    # Створюємо менеджери
    gui_manager = SafeGUIManager(root)
    optimizer = WidgetCreationOptimizer(root)
    
    # Тест захисту від рекурсії
    @recursion_protector.protect
    def test_recursion(depth=0):
        print(f"Глибина рекурсії: {depth}")
        if depth < 100:  # Спроба глибокої рекурсії
            return test_recursion(depth + 1)
        return depth
    
    # Тест безпечного GUI виклику
    @safe_gui_call
    def test_gui_operation():
        label = tk.Label(root, text="Тестовий лейбл")
        label.pack()
        
        # Імітуємо помилку
        raise tk.TclError("Test error")
    
    # Тест оптимізатора створення віджетів
    def create_test_widget(index):
        label = tk.Label(root, text=f"Віджет {index}")
        label.pack()
        return label
    
    # Запускаємо тести
    print("Тест захисту від рекурсії:")
    result = test_recursion()
    print(f"Результат: {result}")
    
    print("\nТест безпечного GUI:")
    test_gui_operation()
    
    print("\nТест оптимізатора віджетів:")
    for i in range(20):
        optimizer.add_widget_creation(create_test_widget, i)
    
    # Моніторинг пам'яті
    def monitor_memory():
        memory_mb = memory_usage_monitor(threshold_mb=100)
        print(f"Використання пам'яті: {memory_mb:.1f} MB")
        root.after(5000, monitor_memory)
    
    monitor_memory()
    
    # Обробник закриття
    def on_closing():
        cleanup_resources()
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    print("Запуск тестового вікна...")
    root.mainloop()