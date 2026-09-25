/**
 * Визуальные пресеты сетов кастомизации.
 *
 * Ключ = asset_key сета из character-service (например 'character:scholar').
 * Сейчас сеты процедурные: аксессуар на голове + цветное кольцо под персонажем,
 * окружение — свет, туман, фон и перекраска материалов комнаты.
 * Чтобы подключить готовую модель, добавьте в пресет поле `glb` (URL модели) —
 * CharacterViewer загрузит её вместо базовой (персонаж должен содержать те же
 * анимации: epic_dance, happy_idle, neutral_idle, sad_idle).
 */

export const CHARACTER_PRESETS = {
  'character:student_basic': { ring: null, accessory: null },
  'character:scholar': { ring: '#5eead4', accessory: 'mortarboard', accessoryColor: '#1f2937', accentColor: '#facc15' },
  'character:night_owl': { ring: '#818cf8', accessory: 'beanie', accessoryColor: '#312e81', accentColor: '#a5b4fc' },
  'character:champion': { ring: '#ffa94d', accessory: 'crown', accessoryColor: '#f59e0b', accentColor: '#fde68a' },
  'character:mentor': { ring: '#4ade80', accessory: 'star', accessoryColor: '#fbbf24', accentColor: '#fef3c7' }
};

export const ENVIRONMENT_PRESETS = {
  'environment:dorm_room': {
    background: '#2d3f63',
    fog: [7, 28],
    hemi: ['#f3f4ff', '#3a3f58', 1.25],
    key: ['#ffffff', 1.4],
    materials: {}
  },
  'environment:library': {
    background: '#3a2a1f',
    fog: [6, 24],
    hemi: ['#ffe8c7', '#3a2a1f', 1.1],
    key: ['#ffd9a0', 1.5],
    materials: { floor: '#5b3a24', 'Material.010': '#d9c3a0', 'Material.014': '#6b4a2f' }
  },
  'environment:campus_park': {
    background: '#9cc9ef',
    fog: [9, 34],
    hemi: ['#ffffff', '#4d7a3a', 1.35],
    key: ['#fff6df', 1.6],
    materials: { floor: '#4f8a3c', 'Material.010': '#e8f1e4', 'Material.014': '#6fa35a' }
  },
  'environment:lab': {
    background: '#10262d',
    fog: [6, 22],
    hemi: ['#d7fbff', '#12303a', 1.2],
    key: ['#bff6ff', 1.3],
    materials: { floor: '#dfe7ea', 'Material.010': '#c9d8de', 'Material.014': '#2dd4bf' }
  },
  'environment:auditorium': {
    background: '#141a3a',
    fog: [8, 30],
    hemi: ['#c7d2fe', '#1e1b4b', 1.0],
    key: ['#fff1c1', 1.8],
    materials: { floor: '#3b2f5c', 'Material.010': '#8c86b8', 'Material.014': '#5b4b8a' }
  }
};

export const DEFAULT_CHARACTER_KEY = 'character:student_basic';
export const DEFAULT_ENVIRONMENT_KEY = 'environment:dorm_room';

export function characterPreset(assetKey) {
  return CHARACTER_PRESETS[assetKey] ?? CHARACTER_PRESETS[DEFAULT_CHARACTER_KEY];
}

function mix(hex, target, amount) {
  const parse = (value) => [1, 3, 5].map((i) => parseInt(value.slice(i, i + 2), 16));
  const [r, g, b] = parse(hex);
  const [tr, tg, tb] = parse(target);
  const channel = (a, t) => Math.round(a + (t - a) * amount).toString(16).padStart(2, '0');
  return `#${channel(r, tr)}${channel(g, tg)}${channel(b, tb)}`;
}

/**
 * Брендированная локация организации (asset_key 'environment:brand'):
 * палитра строится из фирменного цвета вуза (theme_id сета = #RRGGBB).
 */
export function brandEnvironmentPreset(brandColor) {
  const color = /^#[0-9a-fA-F]{6}$/.test(brandColor || '') ? brandColor : '#0b7a70';
  return {
    background: mix(color, '#0b0f14', 0.55),
    fog: [8, 30],
    hemi: ['#ffffff', mix(color, '#000000', 0.4), 1.2],
    key: ['#ffffff', 1.5],
    materials: { floor: mix(color, '#ffffff', 0.25), 'Material.010': mix(color, '#ffffff', 0.8), 'Material.014': color }
  };
}

export function environmentPreset(assetKey, themeColor) {
  if (assetKey === 'environment:brand') {
    return brandEnvironmentPreset(themeColor);
  }
  return ENVIRONMENT_PRESETS[assetKey] ?? ENVIRONMENT_PRESETS[DEFAULT_ENVIRONMENT_KEY];
}

/** Масштаб персонажа по стадии роста (уровень интеллекта) */
export const GROWTH_SCALE = { baby: 0.66, teen: 0.75, adult: 0.84 };

/** Анимация «в покое» по удовлетворению — те же пороги, что в shared/character_mood.py */
export function idleAnimationFor(satisfaction) {
  if (typeof satisfaction !== 'number') return 'neutral_idle';
  if (satisfaction >= 85) return 'epic_dance';
  if (satisfaction >= 65) return 'happy_idle';
  if (satisfaction >= 40) return 'neutral_idle';
  return 'sad_idle';
}
