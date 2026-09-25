# Система хранения и отображения изображений предметов

## 📋 Обзор

Система автоматически сохраняет изображения предметов в базе данных в формате Base64 и использует их во всех компонентах интерфейса (инвентарь, магазин, обмены).

---

## 🗄️ База данных

### Модель Item
**Файл**: `services/shared/models/item.py`

```python
class Item(Base):
    # ... другие поля ...
    
    # Изображение предмета
    image_filename = Column(String(255), nullable=True)  # Имя файла для справки
    image_data = Column(Text, nullable=True)             # Base64 данные изображения
```

**Поля:**
- `image_filename` - имя оригинального файла (для справки)
- `image_data` - Base64-кодированное изображение (PNG)

---

## 🔄 Процесс импорта

### 1. Парсинг файлов
**Файл**: `scripts/import_standard_items.py`

```python
def encode_image_to_base64(image_path: Path) -> str:
    """Кодирует изображение в base64"""
    with open(image_path, 'rb') as f:
        image_data = f.read()
    return base64.b64encode(image_data).decode('utf-8')
```

### 2. Сохранение в БД
**Файл**: `services/user_service/main.py` (эндпоинт `/reset-db`)

```python
item_data = {
    "name": item_file_data['name'],
    "image_filename": source_image.name,
    "image_data": item_file_data.get('image_base64')  # Сохраняем base64 в БД
}
```

### 3. Размер данных
- **1 PNG изображение (~50KB)** ≈ **~67KB в Base64**
- **50 предметов** ≈ **~3.35MB в БД**

---

## 🎨 Frontend - Отображение изображений

### Утилита преобразования
**Файл**: `frontend/src/utils/itemPresentation.js`

```javascript
export function getItemImageSrc(item) {
  if (item.image_data) {
    if (item.image_data.startsWith('data:image')) {
      return item.image_data;
    }
    // Добавляем Data URL префикс
    return `data:image/png;base64,${item.image_data}`;
  }
  return null;  // Fallback на эмодзи
}
```

### Обновленные компоненты

#### 1. InventoryItemCard
**Файл**: `frontend/src/features/inventory/components/InventoryItemCard.jsx`

```jsx
const imageSrc = getItemImageSrc(item);

{imageSrc ? (
  <div className="item-icon-large">
    <img 
      src={imageSrc} 
      alt={item.name} 
      style={{ width: '100%', height: '100%', objectFit: 'contain' }} 
    />
  </div>
) : (
  <div className="item-icon-large">{icon}</div>
)}
```

#### 2. ShopListingCard
**Файл**: `frontend/src/features/shop/components/ShopListingCard.jsx`

```jsx
const imageSrc = item ? getItemImageSrc(item) : null;

{imageSrc ? (
  <img 
    src={imageSrc} 
    alt={itemName} 
    style={{ 
      width: '32px', 
      height: '32px', 
      objectFit: 'contain'
    }} 
  />
) : (
  <span>{itemIcon}</span>
)}
```

#### 3. TradeRequestCard
**Файл**: `frontend/src/features/inventory/components/TradeRequestCard.jsx`

```jsx
const initiatorItemImageSrc = initiatorItem ? getItemImageSrc(initiatorItem) : null;

{initiatorItemImageSrc ? (
  <img 
    src={initiatorItemImageSrc} 
    alt={initiatorItemName} 
    style={{ width: '24px', height: '24px', objectFit: 'contain' }} 
  />
) : (
  <span>{initiatorItemIcon}</span>
)}
```

---

## 📡 API

### ItemResponse Schema
**Файл**: `services/inventory_service/main.py`

```python
class ItemResponse(BaseModel):
    id: int
    name: str
    # ... другие поля ...
    image_filename: Optional[str]
    image_data: Optional[str]  # Base64 строка
    
    class Config:
        from_attributes = True
```

### Получение предметов
```bash
# Список всех предметов (с image_data)
GET /api/inventory/items/

# Конкретный предмет
GET /api/inventory/items/{item_id}

# Инвентарь пользователя (с image_data)
GET /api/inventory/users/{user_id}
```

**Пример ответа:**
```json
{
  "id": 1,
  "name": "Ключ логики",
  "rarity": "legendary",
  "reward_coins": 7,
  "reward_intelligence_points": 15,
  "reward_satisfaction": 9,
  "image_filename": "Легендарная_Ключ логики_15ои_7м_9уд.png",
  "image_data": "iVBORw0KGgoAAAANSUhEUgAA..."
}
```

---

## ⚡ Оптимизация

### Преимущества Base64 в БД:
✅ Изображения всегда доступны вместе с данными предмета  
✅ Нет необходимости в дополнительных HTTP запросах  
✅ Упрощенная синхронизация данных  
✅ Работает без файловой системы  

### Недостатки:
⚠️ Увеличенный размер ответов API (~33% больше чем binary)  
⚠️ Больший размер БД  
⚠️ Невозможность CDN кеширования  

### Рекомендации для production:
1. **Сжатие изображений** перед импортом (WebP, оптимизация PNG)
2. **Gzip compression** на уровне API
3. **Кеширование** на клиенте через Service Workers
4. **Lazy loading** для больших списков предметов

---

## 🔄 Миграция данных

### Обновление существующей БД:

```bash
# 1. Пересоздать БД с новой схемой
curl -X POST http://localhost/api/user/reset-db

# 2. Проверить импорт
curl http://localhost/api/inventory/items/ | jq '.[0].image_data' | head -c 100
```

### Результат:
```
✅ 50 предметов импортировано
✅ Каждый предмет содержит image_data
✅ Frontend автоматически отображает изображения
```

---

## 🎯 Использование в новых компонентах

```jsx
import { getItemImageSrc } from '../utils/itemPresentation.js';

function MyItemComponent({ item }) {
  const imageSrc = getItemImageSrc(item);
  
  return (
    <div>
      {imageSrc ? (
        <img src={imageSrc} alt={item.name} />
      ) : (
        <span>📦</span>  // Fallback эмодзи
      )}
    </div>
  );
}
```

---

## 📝 Проверка работы

### Backend:
```bash
# Проверить, что image_data сохраняется
curl -s http://localhost/api/inventory/items/1 | jq '.image_data' | head -c 50
# Ожидается: "iVBORw0KGgoAAAANSUhEUgAA..."
```

### Frontend:
1. Открыть инвентарь
2. Открыть Developer Tools → Network
3. Проверить response от `/api/inventory/users/{id}`
4. Убедиться что `image_data` присутствует в каждом предмете

### Browser Console:
```javascript
// Проверить, что изображения отображаются
document.querySelectorAll('img[src^="data:image"]').length
// Ожидается: количество предметов с изображениями
```

---

## 🐛 Troubleshooting

### Проблема: Изображения не отображаются

**Решение 1**: Проверить наличие image_data в API
```bash
curl http://localhost/api/inventory/items/1 | jq '.image_data'
```

**Решение 2**: Проверить console на ошибки
```javascript
// В Browser Console
console.log(getItemImageSrc(item))
```

**Решение 3**: Пересоздать БД
```bash
curl -X POST http://localhost/api/user/reset-db
```

### Проблема: БД слишком большая

**Решение**: Оптимизировать изображения перед импортом
```bash
# Установить imagemagick или аналог
cd scripts/standard_items
mogrify -resize 128x128 -quality 85 *.png
```

---

## ✅ Checklist

- [x] Модель Item содержит поле `image_data`
- [x] Парсер кодирует изображения в Base64
- [x] `/reset-db` сохраняет Base64 в БД
- [x] API возвращает `image_data` в ItemResponse
- [x] Frontend утилита `getItemImageSrc()` создана
- [x] InventoryItemCard использует изображения
- [x] ShopListingCard использует изображения
- [x] TradeRequestCard использует изображения
- [x] Fallback на эмодзи работает

---

## 📚 Связанные файлы

**Backend:**
- `services/shared/models/item.py` - модель Item
- `services/inventory_service/main.py` - API schemas
- `services/user_service/main.py` - импорт при reset-db
- `scripts/import_standard_items.py` - парсер

**Frontend:**
- `frontend/src/utils/itemPresentation.js` - утилиты
- `frontend/src/features/inventory/components/InventoryItemCard.jsx`
- `frontend/src/features/shop/components/ShopListingCard.jsx`
- `frontend/src/features/inventory/components/TradeRequestCard.jsx`


