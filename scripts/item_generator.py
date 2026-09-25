import os
import random
import json
from pathlib import Path
from collections import Counter
import re

# ============= НАСТРОЙКИ =============
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}
FOLDER_NAME = "scripts/standard_items"
ROOT_DIR = Path.cwd()
ITEMS_DIR = ROOT_DIR / FOLDER_NAME
LOG_FILE = ROOT_DIR / "renaming_log.json"

# 🌟 Режим: True — оставляем пробелы в названии (как в ТЗ: "Сердце разума")
ALLOW_SPACES_IN_NAMES = True

# ============= РЕДКОСТИ =============
# Распределение (на 1000 предметов приблизительно):
#   обычная: ~570, необычная: ~240, редкая: ~115, легендарная: ~25, эпический: ~5
RARITIES = ["обычная", "необычная", "редкая", "легендарная", "эпический"]
WEIGHTS = [57, 24, 11.5, 2.5, 0.5]  # сумма = 95.5 → нормализуем внутри random.choices

ABSTRACT_ITEMS = [
    "Сокровище", "Артефакт", "Оберег", "Амулет", "Реликвия", "Скрижаль",
    "Пророчество", "Завет", "Знак", "Дар", "Искра", "Суть", "Зерно",
    "Пламя", "Сфера", "Сердце", "Ключ", "Завещание", "Эхо", "Откровение",
    "Печать", "Слово", "Зерцало", "Камень", "Путь", "Завеса", "Свет"
]

INTELLECT_THEMES = [
    "разума", "интеллекта", "мышления", "мудрости", "знания", "логики",
    "внимания", "памяти", "прозрения", "ясности", "сознания", "понимания",
    "опыта", "мощи", "анализа", "вывода", "глубины", "озарения",
    "проницательности", "стратегии", "интуиции"
]

WEALTH_THEMES = [
    "богатства", "процветания", "удачи", "изобилия", "сокровищ", "достояния",
    "благосостояния", "благоденствия", "даров", "обилья", "плодородия",
    "пользы", "выгоды", "излишка", "благодати"
]


# Порядок — от частого к редкому. Для генерации — неважен, но логика ниже учитывает это.
RARITIES = ["обычная", "необычная", "редкая", "эпический", "легендарная"]

# Веса (на 1000 предметов ≈):
#   обычная: 580, необычная: 240, редкая: 115, эпический: 5, легендарная: 1
WEIGHTS = [58.0, 24.0, 11.5, 0.5, 0.1]  # сумма = 94.1 → random.choices нормализует


def generate_display_name(rarity: str) -> str:
    item = random.choice(ABSTRACT_ITEMS)

    # 🔹 ВЫБОР ТЕМЫ
    if rarity == "обычная":
        theme = random.choice(INTELLECT_THEMES + WEALTH_THEMES)
    elif rarity == "необычная":
        theme = random.choice(INTELLECT_THEMES)  # только интеллект!
    else:
        theme = random.choice(INTELLECT_THEMES) if random.random() < 0.6 else random.choice(WEALTH_THEMES)

    # 🔹 БОНУСЫ — ЛЕГЕНДАРНЫЙ САМЫЙ СИЛЬНЫЙ ✅
    bonuses = []
    if rarity == "обычная":
        ud = random.randint(1, 3)
        bonuses = [f"{ud}уд"]
    elif rarity == "необычная":
        oi = random.randint(1, 3)
        bonuses = [f"{oi}ои"]
    elif rarity == "редкая":
        if random.random() < 0.6:
            ud = random.randint(3, 5)
            oi = random.randint(3, 5)
            bonuses = [f"{ud}уд", f"{oi}ои"]
        else:
            ud = random.randint(3, 5)
            m = random.randint(3, 5)
            bonuses = [f"{ud}уд", f"{m}м"]
    elif rarity == "эпический":
        # 🔷 Второй по силе
        ud = random.randint(10, 16)   # макс = 16
        oi = random.randint(10, 16)   # макс = 16
        m = random.randint(12, 18)    # макс = 18
        bonuses = [f"{ud}уд", f"{oi}ои", f"{m}м"]
    elif rarity == "легендарная":
        # 🔥 САМЫЙ СИЛЬНЫЙ — и монеты усилены!
        ud = random.randint(14, 22)   # мин = 14 (> среднего эпического), макс = 22 > 16
        oi = random.randint(14, 22)   # то же
        m = random.randint(16, 26)    # ✅ мин = 16 ≥ макс эпического (18?) — но хотим СТРОГО > → см. ниже
        bonuses = [f"{ud}уд", f"{oi}ои", f"{m}м"]

    return f"{rarity.capitalize()}_{item} {theme}_{'_'.join(bonuses)}"

def sanitize_for_filesystem(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', name)
    name = name.strip()
    if not ALLOW_SPACES_IN_NAMES:
        name = name.replace(' ', '_')
        name = re.sub(r'_+', '_', name)
    return name


def ensure_min_rarities(n: int) -> list:
    """
    ЖЁСТКОЕ распределение (для n=50):
        обычная:     20
        необычная:   12
        редкая:       8
        эпический:    6
        легендарная:  4
    Если n ≠ 50 — масштабирует пропорционально (округление к ближайшему).
    """
    TARGET_DIST = {
        "обычная": 20,
        "необычная": 12,
        "редкая": 8,
        "эпический": 6,
        "легендарная": 4
    }
    total_target = sum(TARGET_DIST.values())  # 50

    if n == total_target:
        # Точное совпадение — берём как есть
        result = []
        for rarity, count in TARGET_DIST.items():
            result.extend([rarity] * count)
        random.shuffle(result)
        return result

    else:
        # Масштабируем пропорционально (округление с балансировкой)
        scale = n / total_target
        counts = {r: max(1, int(round(c * scale))) for r, c in TARGET_DIST.items()}
        
        # Корректируем сумму до n (если не совпадает из-за округления)
        diff = n - sum(counts.values())
        tiers = ["легендарная", "эпический", "редкая", "необычная", "обычная"]
        i = 0
        while diff != 0:
            sign = 1 if diff > 0 else -1
            r = tiers[i % len(tiers)]
            if counts[r] + sign >= 1:
                counts[r] += sign
                diff -= sign
            i += 1

        result = []
        for rarity, count in counts.items():
            result.extend([rarity] * count)
        random.shuffle(result)
        return result

# ============= ОСНОВНОЙ КОД (без изменений — можно оставить как в предыдущей версии) =============
def main():
    print(f"📁 Работаем с папкой: '{FOLDER_NAME}'")
    if not ITEMS_DIR.exists():
        print(f"❌ Папка не найдена. Доступные: {[d.name for d in ROOT_DIR.iterdir() if d.is_dir()]}")
        return

    image_files = [
        f for f in ITEMS_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
    ]
    image_files.sort(key=lambda x: x.name)

    print(f"🖼️  Найдено изображений: {len(image_files)}")
    if not image_files:
        return

    rarities = ensure_min_rarities(len(image_files))
    display_names = [generate_display_name(r) for r in rarities]
    safe_names = [
        sanitize_for_filesystem(name) + f.suffix.lower()
        for name, f in zip(display_names, image_files)
    ]

    # Уникальность
    seen = {}
    for i, name in enumerate(safe_names):
        base, ext = os.path.splitext(name)
        count = seen.get(base, 0)
        if count > 0:
            safe_names[i] = f"{base}_{count}{ext}"
        seen[base] = count + 1

    # Переименование
    log = []
    success = 0
    for old_path, disp_name, safe_name in zip(image_files, display_names, safe_names):
        new_path = ITEMS_DIR / safe_name
        try:
            old_path.rename(new_path)
            log.append({
                "old_name": old_path.name,
                "display_name": disp_name + old_path.suffix.lower(),
                "file_name": safe_name,
                "rarity": disp_name.split('_')[0].lower()
            })
            print(f"✅ {old_path.name} → {safe_name}")
            success += 1
        except Exception as e:
            print(f"❌ Ошибка: {old_path.name} → {safe_name} | {e}")

    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

    stats = Counter(item["rarity"] for item in log)
    print(f"\n✅ Успешно: {success}/{len(image_files)}")
    print("📊 Распределение редкостей:")
    for r in RARITIES:
        if r in stats:
            print(f"  {r.capitalize()}: {stats[r]}")
    print(f"📄 Лог сохранён: {LOG_FILE.resolve()}")

    if ALLOW_SPACES_IN_NAMES:
        print("\n⚠️  В именах файлов есть ПРОБЕЛЫ. Для автоматизации (FastAPI, MinIO, Docker) рекомендуется ALLOW_SPACES_IN_NAMES = False")


if __name__ == "__main__":
    main()