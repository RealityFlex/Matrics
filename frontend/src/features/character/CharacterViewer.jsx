import React, { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import roomUrl from '../../assets/models/room.glb?url';
import {
  DEFAULT_CHARACTER_KEY,
  DEFAULT_ENVIRONMENT_KEY,
  GROWTH_SCALE,
  characterPreset,
  environmentPreset,
  idleAnimationFor
} from './appearance/presets.js';
import {
  AVATAR_CLIP,
  avatarUrlFor,
  collectAvatarActions,
  hideStaticAvatarMeshes,
  layoutAvatar,
  measureAvatarFitScale,
  prepareAvatarMaterials,
  resolveAvatarAction
} from './avatarModel.js';

/** Аксессуар в «единицах головы» (1 = высота головы), крепится к кости HeadTop_End */
function buildAccessory(kind, color, accent) {
  const group = new THREE.Group();
  const main = new THREE.MeshStandardMaterial({ color, roughness: 0.6 });
  const detail = new THREE.MeshStandardMaterial({ color: accent, roughness: 0.4, metalness: 0.3 });
  if (kind === 'mortarboard') {
    const cap = new THREE.Mesh(new THREE.CylinderGeometry(0.55, 0.6, 0.35, 24), main);
    cap.position.y = 0.05;
    const board = new THREE.Mesh(new THREE.BoxGeometry(1.5, 0.08, 1.5), main);
    board.position.y = 0.26;
    board.rotation.y = Math.PI / 4;
    const tassel = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 0.5, 8), detail);
    tassel.position.set(0.55, 0.05, 0);
    group.add(cap, board, tassel);
  } else if (kind === 'beanie') {
    const hat = new THREE.Mesh(new THREE.SphereGeometry(0.62, 24, 16, 0, Math.PI * 2, 0, Math.PI / 2), main);
    hat.position.y = -0.12;
    const band = new THREE.Mesh(new THREE.TorusGeometry(0.6, 0.09, 10, 28), detail);
    band.rotation.x = Math.PI / 2;
    band.position.y = -0.1;
    const pompom = new THREE.Mesh(new THREE.SphereGeometry(0.16, 16, 12), detail);
    pompom.position.y = 0.52;
    group.add(hat, band, pompom);
  } else if (kind === 'crown') {
    const ring = new THREE.Mesh(new THREE.CylinderGeometry(0.5, 0.5, 0.3, 24, 1, true), detail);
    ring.material.side = THREE.DoubleSide;
    ring.position.y = 0.1;
    group.add(ring);
    for (let i = 0; i < 5; i += 1) {
      const spike = new THREE.Mesh(new THREE.ConeGeometry(0.1, 0.28, 8), main);
      const angle = (i / 5) * Math.PI * 2;
      spike.position.set(Math.cos(angle) * 0.5, 0.38, Math.sin(angle) * 0.5);
      group.add(spike);
    }
  } else if (kind === 'star') {
    const star = new THREE.Mesh(new THREE.OctahedronGeometry(0.3), detail);
    star.position.y = 0.9;
    star.userData.spin = true;
    const halo = new THREE.Mesh(new THREE.TorusGeometry(0.45, 0.04, 8, 32), main);
    halo.rotation.x = Math.PI / 2;
    halo.position.y = 0.55;
    group.add(star, halo);
  }
  group.traverse((child) => {
    if (child.isMesh) child.castShadow = true;
  });
  return group;
}

function disposeObject(object) {
  object?.traverse?.((child) => {
    if (child.isMesh) {
      child.geometry?.dispose();
      const materials = Array.isArray(child.material) ? child.material : [child.material];
      materials.forEach((material) => material?.dispose?.());
    }
  });
}

/**
 * 3D-персонаж и его окружение — визуальный центр продукта.
 *
 * Сцена создаётся один раз; настроение (satisfaction), стадия роста и сеты
 * кастомизации применяются к уже загруженной сцене без перезагрузки моделей.
 * Через ref доступен playReaction() — «танец» после отметки на занятии.
 */
export const CharacterViewer = forwardRef(function CharacterViewer(
  {
    satisfaction = null,
    growthStage = 'teen',
    characterKey = DEFAULT_CHARACTER_KEY,
    environmentKey = DEFAULT_ENVIRONMENT_KEY,
    environmentTheme = null,
    isActive = true,
    compact = false
  },
  ref
) {
  const containerRef = useRef(null);
  const canvasRef = useRef(null);
  const sceneRef = useRef({});
  const reactionRef = useRef({ until: 0, pulse: 0 });
  const isActiveRef = useRef(isActive);
  const satisfactionRef = useRef(satisfaction);
  const growthStageRef = useRef(growthStage);

  const [status, setStatus] = useState('loading');
  const [attempt, setAttempt] = useState(0);

  isActiveRef.current = isActive;
  satisfactionRef.current = satisfaction;
  growthStageRef.current = growthStage;

  const playAnimation = useCallback((name, { once = false } = {}) => {
    const { actions } = sceneRef.current;
    const next = resolveAvatarAction(actions, name);
    const current = sceneRef.current.activeAction;
    if (!next || (current === next && !once)) return;
    next.reset();
    next.enabled = true;
    next.setLoop(once ? THREE.LoopOnce : THREE.LoopRepeat, once ? 1 : Infinity);
    next.clampWhenFinished = Boolean(once);
    if (current && current !== next) {
      next.setEffectiveWeight(1).fadeIn(0.3).play();
      current.fadeOut(0.3);
    } else {
      next.setEffectiveWeight(1).play();
    }
    sceneRef.current.activeAction = next;
  }, []);

  useImperativeHandle(
    ref,
    () => ({
      /** Реакция персонажа на награду: танец + «пульс» масштаба */
      playReaction() {
        reactionRef.current = { until: performance.now() + 4200, pulse: performance.now() };
        playAnimation(AVATAR_CLIP.dance);
      }
    }),
    [playAnimation]
  );

  // ---------- Сцена: создаётся один раз (и при повторной попытке после ошибки) ----------
  useEffect(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;
    if (!container || !canvas) return undefined;

    setStatus('loading');
    let disposed = false;
    let frameId = null;

    const scene = new THREE.Scene();
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 1000);
    camera.position.set(0, 2.25, 7.4);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enablePan = false;
    controls.enableDamping = true;
    controls.minPolarAngle = Math.PI / 4;
    controls.maxPolarAngle = Math.PI / 2;
    controls.minDistance = 3.4;
    controls.maxDistance = 8.5;
    controls.target.set(0, 1.05, 0);
    const initialAzimuth = controls.getAzimuthalAngle();
    controls.minAzimuthAngle = initialAzimuth - THREE.MathUtils.degToRad(25);
    controls.maxAzimuthAngle = initialAzimuth + THREE.MathUtils.degToRad(90);
    controls.update();

    const hemi = new THREE.HemisphereLight(0xf3f4ff, 0x3a3f58, 1.25);
    const keyLight = new THREE.DirectionalLight(0xffffff, 1.4);
    keyLight.position.set(4, 6, 4);
    keyLight.castShadow = true;
    keyLight.shadow.mapSize.set(2048, 2048);
    keyLight.shadow.camera.near = 0.5;
    keyLight.shadow.camera.far = 35;
    const fillLight = new THREE.DirectionalLight(0xb8c7ff, 0.85);
    fillLight.position.set(-3.5, 3.5, -2);
    const rimLight = new THREE.DirectionalLight(0xfff2d9, 0.65);
    rimLight.position.set(2, 2.5, -4);
    const ambient = new THREE.AmbientLight(0xbcc8e6, 0.35);
    scene.add(hemi, keyLight, fillLight, rimLight, ambient);

    sceneRef.current = { scene, renderer, camera, controls, hemi, keyLight, actions: new Map() };

    const resize = () => {
      const { clientWidth, clientHeight } = container;
      if (!clientWidth || !clientHeight) return;
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      renderer.setSize(clientWidth, clientHeight, false);
      camera.aspect = clientWidth / clientHeight;
      camera.updateProjectionMatrix();
    };
    resize();
    const resizeObserver = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(resize) : null;
    resizeObserver?.observe(container);

    const loader = new GLTFLoader();
    const load = (url) => new Promise((resolve, reject) => loader.load(url, resolve, undefined, reject));

    const recenter = (object) => {
      object.updateMatrixWorld(true);
      const box = new THREE.Box3().setFromObject(object);
      const center = box.getCenter(new THREE.Vector3());
      const size = box.getSize(new THREE.Vector3());
      object.position.sub(center);
      object.position.y += size.y / 2;
      object.updateMatrixWorld(true);
    };

    const prepareMeshes = (object) => {
      object.traverse((child) => {
        if (child.isMesh) {
          child.castShadow = true;
          child.receiveShadow = true;
          const materials = Array.isArray(child.material) ? child.material : [child.material];
          materials.forEach((material) => {
            if (!material) return;
            material.transparent = false;
            material.opacity = 1;
            material.depthWrite = true;
            material.needsUpdate = true;
          });
        }
      });
    };

    const installCharacter = (characterGltf, url) => {
      const state = sceneRef.current;
      if (state.accessory) {
        state.accessory.parent?.remove(state.accessory);
        disposeObject(state.accessory);
        state.accessory = null;
      }
      if (state.model) {
        state.scene.remove(state.model);
        disposeObject(state.model);
      }
      const model = characterGltf.scene;
      hideStaticAvatarMeshes(model);
      prepareAvatarMaterials(model);
      const fitScale = measureAvatarFitScale(model);
      const growthScale = GROWTH_SCALE[growthStageRef.current] ?? GROWTH_SCALE.teen;
      layoutAvatar(model, {
        fitScale,
        growthScale,
        offset: { x: -0.5, z: 0.35 }
      });
      state.scene.add(model);
      const mixer = new THREE.AnimationMixer(model);
      const actions = collectAvatarActions(mixer, characterGltf.animations);
      mixer.addEventListener('finished', () => {
        if (performance.now() < reactionRef.current.until) return;
        playAnimation(idleAnimationFor(satisfactionRef.current));
      });
      let headTop = null;
      model.traverse((child) => {
        if (!headTop && child.isBone && /HeadTop_End$/i.test(child.name)) headTop = child;
      });
      Object.assign(state, {
        model,
        mixer,
        actions,
        headTop,
        fitScale,
        avatarUrl: url,
        activeAction: null,
        baseScale: fitScale * growthScale
      });
    };

    const initialUrl = avatarUrlFor(characterKey);
    Promise.all([load(roomUrl), load(initialUrl)])
      .then(([roomGltf, characterGltf]) => {
        if (disposed) return;
        const room = roomGltf.scene;
        prepareMeshes(room);
        recenter(room);
        scene.add(room);

        const roomMaterials = new Map();
        room.traverse((child) => {
          if (!child.isMesh) return;
          const materials = Array.isArray(child.material) ? child.material : [child.material];
          materials.forEach((material) => {
            if (material?.name && material.color && !roomMaterials.has(material.name)) {
              roomMaterials.set(material.name, { material, original: material.color.clone() });
            }
          });
        });

        const ring = new THREE.Mesh(
          new THREE.RingGeometry(0.55, 0.75, 48),
          new THREE.MeshBasicMaterial({ color: 0x5eead4, transparent: true, opacity: 0.55, side: THREE.DoubleSide })
        );
        ring.rotation.x = -Math.PI / 2;
        ring.visible = false;
        scene.add(ring);

        Object.assign(sceneRef.current, { room, roomMaterials, ring, installCharacter });
        installCharacter(characterGltf, initialUrl);
        if (sceneRef.current.model) {
          ring.position.set(sceneRef.current.model.position.x, 0.02, sceneRef.current.model.position.z);
        }
        playAnimation(idleAnimationFor(satisfactionRef.current));
        setStatus('ready');

        const clock = new THREE.Clock();
        const animate = () => {
          frameId = requestAnimationFrame(animate);
          if (!isActiveRef.current || document.hidden) {
            clock.getDelta();
            return;
          }
          const delta = clock.getDelta();
          const state = sceneRef.current;
          state.mixer?.update(delta);
          controls.update();

          const now = performance.now();
          const { pulse, until } = reactionRef.current;
          const baseScale = state.baseScale;
          const model = state.model;
          if (until > 0 && now >= until) {
            reactionRef.current.until = 0;
            playAnimation(idleAnimationFor(satisfactionRef.current));
          }
          if (model && baseScale && now < until) {
            const t = (now - pulse) / 1000;
            model.scale.setScalar(baseScale * (1 + 0.06 * Math.max(0, Math.sin(t * 6)) * Math.exp(-t * 0.8)));
          } else if (model && baseScale && Math.abs(model.scale.x - baseScale) > 1e-4) {
            model.scale.setScalar(baseScale);
          }
          state.accessory?.traverse((child) => {
            if (child.userData.spin) child.rotation.y += delta * 1.5;
          });
          renderer.render(scene, camera);
        };
        animate();
        sceneRef.current.applyAll?.();
      })
      .catch((error) => {
        console.error('[CharacterViewer] Ошибка загрузки моделей:', error);
        if (!disposed) setStatus('error');
      });

    return () => {
      disposed = true;
      if (frameId) cancelAnimationFrame(frameId);
      resizeObserver?.disconnect();
      controls.dispose();
      disposeObject(scene);
      renderer.dispose();
      sceneRef.current = {};
    };
  }, [attempt, playAnimation]);

  // ---------- Смена GLB при выборе сета («Эрудит», «Полуночник» и т.п.) ----------
  useEffect(() => {
    const state = sceneRef.current;
    if (status !== 'ready' || !state.installCharacter) return undefined;
    const url = avatarUrlFor(characterKey);
    if (state.avatarUrl === url) return undefined;
    let cancelled = false;
    const loader = new GLTFLoader();
    loader.load(
      url,
      (gltf) => {
        if (cancelled || !sceneRef.current.installCharacter) return;
        sceneRef.current.installCharacter(gltf, url);
        playAnimation(idleAnimationFor(satisfactionRef.current));
        sceneRef.current.applyAll?.();
      },
      undefined,
      (error) => console.error('[CharacterViewer] Не удалось сменить модель:', error)
    );
    return () => {
      cancelled = true;
    };
  }, [characterKey, status, playAnimation]);

  // ---------- Настроение → анимация в покое ----------
  useEffect(() => {
    if (status !== 'ready') return;
    if (performance.now() < reactionRef.current.until) return;
    playAnimation(idleAnimationFor(satisfaction));
  }, [satisfaction, status, playAnimation]);

  // ---------- Стадия роста и сеты кастомизации ----------
  useEffect(() => {
    const apply = () => {
      const state = sceneRef.current;
      if (!state.model) return;

      const growthScale = GROWTH_SCALE[growthStage] ?? GROWTH_SCALE.teen;
      const fitScale = state.fitScale ?? 1;
      state.baseScale = fitScale * growthScale;
      if (state.model && fitScale) {
        layoutAvatar(state.model, {
          fitScale,
          growthScale,
          offset: { x: -0.5, z: 0.35 }
        });
      }

      const env = environmentPreset(environmentKey, environmentTheme);
      const background = new THREE.Color(env.background);
      state.scene.background = background;
      state.scene.fog = new THREE.Fog(background, env.fog[0], env.fog[1]);
      state.renderer.setClearColor(background, 1);
      state.hemi.color.set(env.hemi[0]);
      state.hemi.groundColor.set(env.hemi[1]);
      state.hemi.intensity = env.hemi[2];
      state.keyLight.color.set(env.key[0]);
      state.keyLight.intensity = env.key[1];
      state.roomMaterials?.forEach(({ material, original }, name) => {
        const override = env.materials?.[name];
        material.color.copy(override ? new THREE.Color(override) : original);
      });

      const preset = characterPreset(characterKey);
      if (state.accessory) {
        state.accessory.parent?.remove(state.accessory);
        disposeObject(state.accessory);
        state.accessory = null;
      }
      if (preset.accessory && state.headTop) {
        const head = new THREE.Vector3();
        const neck = new THREE.Vector3();
        state.model.updateMatrixWorld(true);
        state.headTop.getWorldPosition(head);
        state.headTop.parent?.getWorldPosition(neck);
        const headSize = Math.max(0.05, head.distanceTo(neck));
        const worldScale = new THREE.Vector3();
        state.headTop.getWorldScale(worldScale);
        const accessory = buildAccessory(preset.accessory, preset.accessoryColor, preset.accentColor);
        // Аксессуар в «единицах головы»: чуть меньше головы и приподнят над макушкой
        accessory.scale.setScalar((headSize * 0.55) / (worldScale.x || 1));
        accessory.position.y = (headSize * 0.12) / (worldScale.y || 1);
        state.headTop.add(accessory);
        state.accessory = accessory;
      }
      if (state.ring) {
        state.ring.visible = Boolean(preset.ring);
        if (preset.ring) state.ring.material.color.set(preset.ring);
        state.ring.position.set(state.model.position.x, 0.02, state.model.position.z);
      }
    };
    sceneRef.current.applyAll = apply;
    apply();
  }, [characterKey, environmentKey, environmentTheme, growthStage, status]);

  return (
    <div
      ref={containerRef}
      className={`character-viewer ${compact ? 'character-viewer--compact' : ''} ${status === 'loading' ? 'loading' : ''}`}
    >
      <canvas ref={canvasRef} id="characterCanvas" aria-label="3D-персонаж" />
      {status === 'loading' ? (
        <div className="character-viewer__overlay" role="status">
          <span className="ui-spinner__circle" aria-hidden="true" />
          <span>Загружаем персонажа…</span>
        </div>
      ) : null}
      {status === 'error' ? (
        <div className="character-viewer__overlay" role="alert">
          <span>Не удалось загрузить 3D-сцену</span>
          <button type="button" className="ui-btn ui-btn--secondary ui-btn--sm" onClick={() => setAttempt((n) => n + 1)}>
            Повторить
          </button>
        </div>
      ) : null}
    </div>
  );
});
