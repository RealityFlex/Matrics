"""
Каталог стандартных предметов (scripts/standard_items).

Раньше предметы попадали в БД только через «сброс базы» из админки, поэтому на
чистой установке каталог был пуст: не работали лутбоксы, стартовые предметы и магазин.
Теперь каталог заполняется при старте user-service, если таблица items пуста.
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.shared.models.item import Item, ItemRarity, ItemType

logger = logging.getLogger(__name__)

STANDARD_ITEMS_DIR = Path("/app/scripts/standard_items")
STATIC_IMAGES_DIR = Path("/app/static/items")


def _load_items_from_directory(path: Path) -> list:
    from scripts.import_standard_items import get_items_from_directory

    return get_items_from_directory(str(path))


async def seed_standard_items(session: AsyncSession, directory: Path = STANDARD_ITEMS_DIR) -> int:
    """Импортировать стандартные предметы, если каталог пуст. Возвращает число созданных."""
    if (await session.execute(select(func.count(Item.id)))).scalar():
        return 0
    if not directory.exists():
        logger.warning("Каталог стандартных предметов не найден: %s", directory)
        return 0

    created = 0
    seen = set()
    for data in _load_items_from_directory(directory):
        if data["name"] in seen:  # в папке встречаются одноимённые предметы разной редкости
            continue
        seen.add(data["name"])
        try:
            source = Path(data["file_path"])
            try:
                STATIC_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, STATIC_IMAGES_DIR / source.name)
            except OSError:
                pass  # копия картинки — только резерв, основная хранится в БД (base64)
            session.add(Item(
                name=data["name"],
                description=f"Редкость: {data['rarity']}",
                rarity=ItemRarity(data["rarity"]),
                type=ItemType.CONSUMABLE,
                base_price=data.get("coins", 0),
                reward_coins=data.get("coins", 0),
                reward_intelligence_points=data.get("intelligence_points", 0),
                reward_satisfaction=data.get("satisfaction", 0),
                image_filename=source.name,
                image_data=data.get("image_base64"),
            ))
            created += 1
        except Exception as exc:
            logger.warning("Предмет %s не импортирован: %s", data.get("name"), exc)
    await session.commit()
    logger.info("Каталог предметов заполнен: %s шт.", created)
    return created
