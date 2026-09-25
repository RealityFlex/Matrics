"""
Скрипт для импорта стандартных предметов из папки standard_items
Парсит названия файлов и создает предметы с наградами
"""
import os
import re
import base64
from pathlib import Path
from typing import Dict, Optional, Tuple

# Маппинг русских названий редкости на английские enum значения
RARITY_MAP = {
    "обычная": "common",
    "необычная": "uncommon",
    "редкая": "rare",
    "эпическая": "epic",
    "эпический": "epic",
    "эпические": "epic",
    "легендарная": "legendary"
}


def parse_item_filename(filename: str) -> Optional[Dict]:
    """
    Парсит название файла и извлекает данные о предмете
    
    Формат: РЕДКОСТЬ_НАЗВАНИЕ_[награды].png
    Награды: Nм (монеты), Nои (очки интеллекта), Nуд (удовлетворенность)
    
    Пример: Легендарная_Ключ логики_15ои_7м_9уд.png
    """
    # Убираем расширение
    name_without_ext = filename.rsplit('.', 1)[0]
    
    # Разбиваем по подчеркиваниям
    parts = name_without_ext.split('_')
    
    if len(parts) < 2:
        return None
    
    # Первая часть - редкость
    rarity_ru = parts[0].lower()
    if rarity_ru not in RARITY_MAP:
        print(f"Неизвестная редкость: {parts[0]} в файле {filename}")
        return None
    
    rarity = RARITY_MAP[rarity_ru]
    
    # Ищем где начинаются награды (части с цифрами и буквами типа "15ои")
    reward_pattern = re.compile(r'^\d+[а-яА-Я]+$')
    
    # Определяем индекс, с которого начинаются награды
    reward_start_idx = len(parts)
    for i in range(1, len(parts)):
        if reward_pattern.match(parts[i]):
            reward_start_idx = i
            break
    
    # Все между редкостью и наградами - это название
    item_name = ' '.join(parts[1:reward_start_idx])
    
    if not item_name:
        print(f"Не удалось извлечь название из файла {filename}")
        return None
    
    # Парсим награды
    coins = 0
    intelligence_points = 0
    satisfaction = 0
    
    reward_parts = parts[reward_start_idx:]
    for reward in reward_parts:
        # Извлекаем число и тип награды
        match = re.match(r'^(\d+)([а-яА-Я]+)$', reward)
        if match:
            amount = int(match.group(1))
            reward_type = match.group(2).lower()
            
            if reward_type == 'м':
                coins = amount
            elif reward_type == 'ои':
                intelligence_points = amount
            elif reward_type == 'уд':
                satisfaction = amount
            else:
                print(f"Неизвестный тип награды: {reward_type} в файле {filename}")
    
    return {
        "name": item_name,
        "rarity": rarity,
        "coins": coins,
        "intelligence_points": intelligence_points,
        "satisfaction": satisfaction,
        "filename": filename
    }


def encode_image_to_base64(image_path: Path) -> str:
    """Кодирует изображение в base64 для передачи через API"""
    with open(image_path, 'rb') as f:
        image_data = f.read()
    return base64.b64encode(image_data).decode('utf-8')


def get_items_from_directory(directory_path: str) -> list:
    """
    Сканирует директорию и возвращает список предметов для импорта
    """
    items = []
    directory = Path(directory_path)
    
    if not directory.exists():
        print(f"Директория {directory_path} не существует")
        return items
    
    # Поддерживаемые форматы изображений
    image_extensions = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}
    
    for file_path in directory.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in image_extensions:
            item_data = parse_item_filename(file_path.name)
            
            if item_data:
                # Добавляем полный путь к файлу
                item_data['file_path'] = str(file_path)
                # Кодируем изображение
                try:
                    item_data['image_base64'] = encode_image_to_base64(file_path)
                    items.append(item_data)
                    print(f"✓ Обработан: {file_path.name}")
                except Exception as e:
                    print(f"✗ Ошибка при обработке {file_path.name}: {e}")
    
    return items


def print_items_summary(items: list):
    """Выводит сводку по найденным предметам"""
    print(f"\n{'='*80}")
    print(f"Найдено предметов: {len(items)}")
    print(f"{'='*80}\n")
    
    # Группировка по редкости
    by_rarity = {}
    for item in items:
        rarity = item['rarity']
        if rarity not in by_rarity:
            by_rarity[rarity] = []
        by_rarity[rarity].append(item)
    
    for rarity in ['common', 'uncommon', 'rare', 'epic', 'legendary']:
        if rarity in by_rarity:
            print(f"{rarity.upper()}: {len(by_rarity[rarity])} предметов")
    
    print(f"\n{'='*80}")
    print("Примеры предметов:")
    print(f"{'='*80}\n")
    
    for item in items[:5]:
        print(f"Название: {item['name']}")
        print(f"Редкость: {item['rarity']}")
        rewards = []
        if item['coins'] > 0:
            rewards.append(f"{item['coins']} монет")
        if item['intelligence_points'] > 0:
            rewards.append(f"{item['intelligence_points']} ОИ")
        if item['satisfaction'] > 0:
            rewards.append(f"{item['satisfaction']} удовлетв.")
        print(f"Награды: {', '.join(rewards) if rewards else 'нет'}")
        print()


if __name__ == "__main__":
    # Путь к папке с предметами
    items_directory = Path(__file__).parent / "standard_items"
    
    # Получаем список предметов
    items = get_items_from_directory(str(items_directory))
    
    # Выводим сводку
    print_items_summary(items)


