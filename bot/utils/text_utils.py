from typing import Optional
import re

def validate_full_name(full_name: str) -> bool:
    """
    Проверяет корректность полного имени
    
    Args:
        full_name: Полное имя для проверки
        
    Returns:
        bool: True если имя корректно, False в противном случае
    """
    # Удаляем лишние пробелы
    full_name = ' '.join(full_name.split())
    
    # Проверяем наличие имени и фамилии
    parts = full_name.split()
    if len(parts) < 2:
        return False
    
    # Проверяем, что каждая часть имени начинается с заглавной буквы
    return all(part.istitle() for part in parts)

def extract_issue_id(text: str) -> Optional[str]:
    """
    Извлекает ID задачи из текста
    
    Args:
        text: Текст, содержащий ID задачи
        
    Returns:
        Optional[str]: ID задачи или None
    """
    # Ищем ID задачи в формате #123 или [123]
    match = re.search(r'(?:#|\\[)(\d+)(?:\\])?', text)
    return match.group(1) if match else None

def truncate_text(text: str, max_length: int = 100) -> str:
    """
    Обрезает текст до указанной длины, добавляя многоточие
    
    Args:
        text: Исходный текст
        max_length: Максимальная длина результата
        
    Returns:
        str: Обрезанный текст
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length-3] + "..."
