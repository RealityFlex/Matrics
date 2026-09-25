"""
Скрипт для создания базовых предметов
"""
import asyncio
import httpx

INVENTORY_SERVICE_URL = "http://localhost:8005"

default_items = [
    {"name": "Меч новичка", "description": "Простой меч для начинающих", "rarity": "common", "type": "consumable", "base_price": 10},
    {"name": "Щит защитника", "description": "Надёжный щит для защиты", "rarity": "common", "type": "consumable", "base_price": 15},
    {"name": "Зелье здоровья", "description": "Восстанавливает здоровье", "rarity": "common", "type": "consumable", "base_price": 20},
    {"name": "Свиток опыта", "description": "Даёт дополнительный опыт", "rarity": "uncommon", "type": "consumable", "base_price": 25},
    {"name": "Кольцо удачи", "description": "Увеличивает удачу", "rarity": "uncommon", "type": "special", "base_price": 30},
    {"name": "Амулет силы", "description": "Увеличивает силу персонажа", "rarity": "rare", "type": "special", "base_price": 50},
    {"name": "Ботинки скорости", "description": "Увеличивают скорость передвижения", "rarity": "rare", "type": "special", "base_price": 45},
]

async def create_items():
    """Создать предметы"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        created = 0
        skipped = 0
        
        for item_data in default_items:
            try:
                response = await client.post(f"{INVENTORY_SERVICE_URL}/items/", json=item_data)
                if response.status_code == 201:
                    print(f"✅ Создан: {item_data['name']}")
                    created += 1
                elif response.status_code == 400:
                    print(f"⏭️  Пропущен (уже существует): {item_data['name']}")
                    skipped += 1
                else:
                    print(f"❌ Ошибка {item_data['name']}: {response.status_code} - {response.text[:100]}")
            except Exception as e:
                print(f"❌ Ошибка {item_data['name']}: {e}")
        
        print(f"\n✅ Готово! Создано: {created}, Пропущено: {skipped}")

if __name__ == "__main__":
    asyncio.run(create_items())

