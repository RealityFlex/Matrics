import * as THREE from 'three';
import avatarUrl from '../../assets/models/avatar_f.glb?url';
import scholarAvatarUrl from '../../assets/models/avatar_scholar_f.glb?url';
import nightOwlAvatarUrl from '../../assets/models/avatar_night_owl_f.glb?url';

export { avatarUrl };

const AVATAR_BY_KEY = {
  'character:student_basic': avatarUrl,
  'character:scholar': scholarAvatarUrl,
  'character:night_owl': nightOwlAvatarUrl
};

export function avatarUrlFor(characterKey) {
  return AVATAR_BY_KEY[characterKey] ?? avatarUrl;
}

/** Имена клипов в avatar_f.glb */
export const AVATAR_CLIP = {
  happyIdle: 'happy_idle',
  neutralIdle: 'neutral_idle',
  sadIdle: 'sad_idle',
  dance: 'cool_dance',
  jump: 'jump_cool',
  roll: 'roll_down',
  run: 'run'
};

const CLIP_ALIASES = {
  epic_dance: AVATAR_CLIP.dance
};

/** Целевой рост персонажа в единицах сцены (до множителя GROWTH_SCALE) */
export const AVATAR_HEIGHT = 3.075;

export function hideStaticAvatarMeshes(root) {
  root.traverse((child) => {
    if (child.isMesh && !child.isSkinnedMesh) {
      child.visible = false;
    }
  });
}

export function prepareAvatarMaterials(root, { shadows = true } = {}) {
  root.traverse((child) => {
    if (!child.isMesh) return;
    child.frustumCulled = false;
    if (shadows) {
      child.castShadow = true;
      child.receiveShadow = true;
    }
    const materials = Array.isArray(child.material) ? child.material : [child.material];
    materials.forEach((material) => {
      if (!material) return;
      material.transparent = false;
      material.opacity = 1;
      material.depthWrite = true;
      material.needsUpdate = true;
    });
  });
}

export function avatarSkinnedBox(root) {
  root.updateMatrixWorld(true);
  const box = new THREE.Box3();
  let found = false;
  root.traverse((child) => {
    if (!child.isSkinnedMesh) return;
    box.expandByObject(child);
    found = true;
  });
  if (!found) box.setFromObject(root);
  return box;
}

export function measureAvatarFitScale(root, targetHeight = AVATAR_HEIGHT) {
  hideStaticAvatarMeshes(root);
  root.scale.set(1, 1, 1);
  root.position.set(0, 0, 0);
  root.updateMatrixWorld(true);
  const size = avatarSkinnedBox(root).getSize(new THREE.Vector3());
  return targetHeight / (size.y || 1);
}

/** Ставит стопы на y = 0 и центр по XZ; scale = fitScale * growthScale. */
export function layoutAvatar(root, { fitScale, growthScale = 1, offset = { x: 0, y: 0, z: 0 } } = {}) {
  root.scale.setScalar(fitScale * growthScale);
  root.position.set(0, 0, 0);
  root.updateMatrixWorld(true);
  const box = avatarSkinnedBox(root);
  const center = box.getCenter(new THREE.Vector3());
  root.position.set(-center.x + (offset.x || 0), -box.min.y + (offset.y || 0), -center.z + (offset.z || 0));
  root.updateMatrixWorld(true);
}

export function collectAvatarActions(mixer, animations, { inPlace = false } = {}) {
  const actions = new Map();
  animations.forEach((clip) => {
    const name = clip.name?.trim();
    if (!name) return;
    const source = inPlace ? makeInPlaceClip(clip) : clip;
    source.name = name;
    actions.set(name, mixer.clipAction(source));
  });
  if (!actions.has(AVATAR_CLIP.jump) && actions.has('jump')) {
    actions.set(AVATAR_CLIP.jump, actions.get('jump'));
  }
  if (!actions.has(AVATAR_CLIP.dance)) {
    const fallback = actions.get(AVATAR_CLIP.happyIdle) ?? actions.get(AVATAR_CLIP.neutralIdle);
    if (fallback) actions.set(AVATAR_CLIP.dance, fallback);
  }
  return actions;
}

export function resolveAvatarAction(actions, name) {
  if (!actions?.size) return null;
  const wanted = CLIP_ALIASES[name] ?? name;
  if (actions.has(wanted)) return actions.get(wanted);
  const lower = String(wanted).toLowerCase();
  for (const [key, action] of actions) {
    if (key.toLowerCase() === lower) return action;
  }
  return actions.get(AVATAR_CLIP.neutralIdle) ?? actions.values().next().value;
}

/** Убирает трансляцию бёдер, чтобы клип Mixamo не уезжал с места (бег, прыжок, ролл). */
export function makeInPlaceClip(clip) {
  const cloned = clip.clone();
  cloned.tracks = cloned.tracks.filter((track) => !/Hips\.position$/i.test(track.name));
  return cloned;
}
