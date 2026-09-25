import { createElement } from 'react';
import { FlaskConical, Gem, Shield, Sparkles } from 'lucide-react';
// Заглушка для предметов без картинки — линейная иконка по типу предмета (без эмодзи)
const TYPE_ICONS = {
  consumable: FlaskConical,
  equipment: Shield,
  decoration: Gem,
  special: Sparkles
};

const RARITY_COLORS = {
  common: '#94a3b8',
  uncommon: '#10b981',
  rare: '#3b82f6',
  epic: '#8b5cf6',
  legendary: '#f59e0b'
};

const RARITY_LABELS = {
  common: 'Обычный',
  uncommon: 'Необычный',
  rare: 'Редкий',
  epic: 'Эпический',
  legendary: 'Легендарный'
};

const TYPE_LABELS = {
  consumable: 'Расходуемый',
  equipment: 'Экипировка',
  decoration: 'Декорация',
  special: 'Специальный'
};

export function getItemIcon(itemType, _itemId, size = 48) {
  const Icon = TYPE_ICONS[itemType] || TYPE_ICONS.special;
  return createElement(Icon, { size, strokeWidth: 1.5, 'aria-hidden': true });
}

// Получить изображение предмета (base64); без картинки — иконка типа (getItemIcon)
export function getItemImageSrc(item) {
  if (item.image_data) {
    // Если image_data уже содержит data:image префикс, возвращаем как есть
    if (item.image_data.startsWith('data:image')) {
      return item.image_data;
    }
    // Иначе добавляем префикс (предполагаем PNG)
    return `data:image/png;base64,${item.image_data}`;
  }
  // Fallback на null если нет изображения
  return null;
}

export function getRarityColor(rarity) {
  return RARITY_COLORS[rarity] || RARITY_COLORS.common;
}

export function getRarityLabel(rarity) {
  return RARITY_LABELS[rarity] || rarity;
}

export function getTypeLabel(type) {
  return TYPE_LABELS[type] || type;
}

