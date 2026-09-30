/**
 * Движок раннера «Забег до пары» (three.js).
 *
 * Мир движется навстречу игроку: персонаж стоит в z = 0 и бежит в сторону −z,
 * препятствия и монеты рождаются впереди (SPAWN_AHEAD) и уезжают за камеру.
 * Трасса строится детерминированно из seed, который выдаёт сервер.
 *
 * Бегун — тот же 3D-аватар, что на главном экране. Клипы из модели:
 * run, jump_cool, roll_down, neutral_idle.
 *
 * Правила, общие с сервером (services/competition_service/minigame.py):
 * очки = дистанция + монеты × SCORE_PER_COIN, скорость ≤ MAX_SPEED, монеты не плотнее 2 м.
 */
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import {
  AVATAR_CLIP,
  avatarUrlFor,
  collectAvatarActions,
  layoutAvatar,
  measureAvatarFitScale,
  prepareAvatarMaterials
} from '../character/avatarModel.js';

export const RUNNER = {
  LANES: [-2.2, 0, 2.2],
  START_SPEED: 12,
  MAX_SPEED: 30,
  ACCELERATION: 0.2, // м/с за секунду забега
  SCORE_PER_COIN: 5,
  COIN_SPACING: 2.4,
  SPAWN_AHEAD: 120,
  DESPAWN_BEHIND: 10,
  JUMP_VELOCITY: 10.5,
  GRAVITY: 30,
  SLIDE_TIME: 0.75,
  LANE_SWITCH_SPEED: 14,
  PLAYER_HEIGHT: 1.6,
  SLIDE_HEIGHT: 0.7,
  JUMP_ANIM_SCALE: 0.58,
  ROLL_ANIM_SCALE: 1.95
};

const COLORS = {
  background: 0x0e1116,
  ground: 0x1b222c,
  sidewalk: 0x232b35,
  grass: 0x13241e,
  laneMark: 0x2dd4bf,
  post: 0x3a4553,
  barrier: 0xf59e0b,
  banner: 0x818cf8,
  block: 0x2a3441,
  blockAccent: 0x5eead4,
  coin: 0xfbbf24,
  lamp: 0xfff1c1,
  building: 0x18202a,
  window: 0x2dd4bf
};

// Габариты препятствий: занимаемая высота [низ, верх] и глубина вдоль трассы
const OBSTACLES = {
  barrier: { bottom: 0, top: 0.9, depth: 0.5 },   // перепрыгнуть
  banner: { bottom: 1.05, top: 2.6, depth: 0.5 },  // пригнуться (подкат)
  block: { bottom: 0, top: 2.6, depth: 3.6 }       // сменить полосу
};

const standard = (color, extra = {}) => new THREE.MeshStandardMaterial({ color, roughness: 0.75, metalness: 0.05, ...extra });

function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export class RunnerEngine {
  constructor(container, callbacks = {}, { characterKey } = {}) {
    this.container = container;
    this.callbacks = callbacks;
    this.modelUrl = avatarUrlFor(characterKey);
    this.state = 'idle'; // idle | countdown | running | paused | crashed
    this.disposables = [];
    this.pools = { barrier: [], banner: [], block: [], coin: [], mark: [], prop: [] };
    this.active = [];
    this.rng = mulberry32(1);

    this.#setupRenderer();
    this.#setupWorld();
    this.#setupPlayer();
    this.#bindInput();
    this.reset(1);

    this.clock = new THREE.Clock();
    this.frame = requestAnimationFrame(this.#loop);
  }

  // ---------- Публичное API ----------

  reset(seed) {
    this.rng = mulberry32(seed || 1);
    this.seed = seed;
    this.active.forEach((obj) => this.#release(obj));
    this.active = [];
    this.distance = 0;
    this.coins = 0;
    this.speed = RUNNER.START_SPEED;
    this.activeMs = 0;
    this.nextRowAt = 34;
    this.lane = 1;
    this.player.position.set(RUNNER.LANES[1], 0, 0);
    this.player.rotation.set(0, 0, 0);
    this.velocityY = 0;
    this.slideLeft = 0;
    this.crashTime = 0;
    this.lastHud = 0;
    this.animName = null;
    this.#playAction(AVATAR_CLIP.neutralIdle, { loop: true, fade: 0.2 });
    this.#spawnAhead();
    this.#emitHud(true);
  }

  start() {
    this.state = 'running';
    this.clock.getDelta();
  }

  setCountdown() {
    this.state = 'countdown';
  }

  pause() {
    if (this.state === 'running') this.state = 'paused';
  }

  resume() {
    if (this.state === 'paused') {
      this.state = 'running';
      this.clock.getDelta();
    }
  }

  input(action) {
    if (this.state !== 'running') return;
    if (action === 'left' && this.lane > 0) this.lane -= 1;
    if (action === 'right' && this.lane < RUNNER.LANES.length - 1) this.lane += 1;
    if (action === 'up' && this.player.position.y <= 0.001) {
      this.velocityY = RUNNER.JUMP_VELOCITY;
      this.slideLeft = 0;
    }
    if (action === 'down') {
      // В прыжке — быстрое приземление, на земле — подкат
      if (this.player.position.y > 0.001) this.velocityY = -RUNNER.JUMP_VELOCITY * 1.2;
      this.slideLeft = RUNNER.SLIDE_TIME;
    }
  }

  /** Завершить забег досрочно (из меню паузы) — результат засчитывается */
  finishNow() {
    if (this.state === 'running' || this.state === 'paused') this.#crash();
  }

  result() {
    return {
      distance: Math.floor(this.distance),
      coins: this.coins,
      durationMs: Math.round(this.activeMs),
      score: Math.floor(this.distance) + this.coins * RUNNER.SCORE_PER_COIN
    };
  }

  dispose() {
    cancelAnimationFrame(this.frame);
    this.resizeObserver?.disconnect();
    window.removeEventListener('keydown', this.onKey);
    document.removeEventListener('visibilitychange', this.onVisibility);
    this.container.removeEventListener('pointerdown', this.onPointerDown);
    this.container.removeEventListener('pointermove', this.onPointerMove);
    this.container.removeEventListener('pointerup', this.onPointerUp);
    this.container.removeEventListener('pointercancel', this.onPointerUp);
    this.scene.traverse((child) => {
      if (child.isMesh) {
        child.geometry?.dispose();
        const materials = Array.isArray(child.material) ? child.material : [child.material];
        materials.forEach((material) => material?.dispose());
      }
    });
    this.disposables.forEach((item) => item.dispose?.());
    this.renderer.dispose();
    this.renderer.domElement.remove();
  }

  // ---------- Сцена ----------

  #setupRenderer() {
    const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.domElement.className = 'runner-canvas';
    this.container.appendChild(renderer.domElement);
    this.renderer = renderer;

    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(COLORS.background);
    this.scene.fog = new THREE.Fog(COLORS.background, 30, 115);

    this.camera = new THREE.PerspectiveCamera(58, 1, 0.1, 220);
    this.camera.position.set(0, 3.3, 6.2);
    this.camera.lookAt(0, 1.1, -8);

    const resize = () => {
      const { clientWidth: w, clientHeight: h } = this.container;
      if (!w || !h) return;
      renderer.setSize(w, h, false);
      this.camera.aspect = w / h;
      // На узких экранах отодвигаем камеру, чтобы были видны все три полосы
      this.camera.fov = w / h < 0.7 ? 68 : 58;
      this.camera.updateProjectionMatrix();
    };
    resize();
    this.resizeObserver = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(resize) : null;
    this.resizeObserver?.observe(this.container);
  }

  #setupWorld() {
    const { scene } = this;
    scene.add(new THREE.HemisphereLight(0xdfe9ff, 0x1b222c, 1.4));
    const sun = new THREE.DirectionalLight(0xffffff, 1.6);
    sun.position.set(4, 10, 6);
    scene.add(sun);

    const plane = (width, length, color, x) => {
      const mesh = new THREE.Mesh(new THREE.PlaneGeometry(width, length), standard(color));
      mesh.rotation.x = -Math.PI / 2;
      mesh.position.set(x, 0, -length / 2 + 20);
      scene.add(mesh);
      return mesh;
    };
    plane(7.2, 260, COLORS.ground, 0);
    plane(1.6, 260, COLORS.sidewalk, -4.4).position.y = 0.02;
    plane(1.6, 260, COLORS.sidewalk, 4.4).position.y = 0.02;
    plane(40, 260, COLORS.grass, -25.2).position.y = -0.01;
    plane(40, 260, COLORS.grass, 25.2).position.y = -0.01;

    // Общие геометрии и материалы пулов
    this.geo = {
      box: new THREE.BoxGeometry(1, 1, 1),
      coin: new THREE.CylinderGeometry(0.32, 0.32, 0.09, 24),
      mark: new THREE.BoxGeometry(0.08, 0.02, 1.6)
    };
    this.mat = {
      post: standard(COLORS.post),
      barrier: standard(COLORS.barrier, { emissive: 0x3a2400 }),
      banner: standard(COLORS.banner, { emissive: 0x15173a }),
      block: standard(COLORS.block),
      blockAccent: standard(COLORS.blockAccent, { emissive: COLORS.blockAccent, emissiveIntensity: 0.6 }),
      coin: standard(COLORS.coin, { metalness: 0.5, roughness: 0.35, emissive: 0x5c3d00 }),
      mark: new THREE.MeshBasicMaterial({ color: COLORS.laneMark, transparent: true, opacity: 0.35 }),
      lamp: new THREE.MeshBasicMaterial({ color: COLORS.lamp }),
      building: standard(COLORS.building),
      window: new THREE.MeshBasicMaterial({ color: COLORS.window, transparent: true, opacity: 0.35 })
    };
    Object.values(this.geo).forEach((g) => this.disposables.push(g));
    Object.values(this.mat).forEach((m) => this.disposables.push(m));

    // Разметка полос и декорации по краям — бесконечно прокручиваются
    for (let z = 10; z > -RUNNER.SPAWN_AHEAD; z -= 4) {
      [-1.1, 1.1].forEach((x) => {
        const mark = new THREE.Mesh(this.geo.mark, this.mat.mark);
        mark.position.set(x, 0.015, z);
        scene.add(mark);
        this.pools.mark.push(mark);
      });
    }
    for (let z = 8; z > -RUNNER.SPAWN_AHEAD - 10; z -= 12) {
      [-1, 1].forEach((side) => {
        const lamp = this.#makeLamp();
        lamp.position.set(side * 4.3, 0, z);
        scene.add(lamp);
        this.pools.prop.push(lamp);
      });
    }
    const buildingRng = mulberry32(7);
    for (let z = 0; z > -RUNNER.SPAWN_AHEAD - 30; z -= 16) {
      [-1, 1].forEach((side) => {
        const building = this.#makeBuilding(buildingRng);
        building.position.set(side * (9 + buildingRng() * 4), 0, z - buildingRng() * 6);
        scene.add(building);
        this.pools.prop.push(building);
      });
    }
  }

  #makeLamp() {
    const group = new THREE.Group();
    const post = new THREE.Mesh(this.geo.box, this.mat.post);
    post.scale.set(0.1, 3.2, 0.1);
    post.position.y = 1.6;
    const head = new THREE.Mesh(this.geo.box, this.mat.lamp);
    head.scale.set(0.5, 0.08, 0.22);
    head.position.set(0, 3.2, 0);
    group.add(post, head);
    return group;
  }

  #makeBuilding(rng) {
    const group = new THREE.Group();
    const height = 5 + rng() * 9;
    const width = 4 + rng() * 3;
    const body = new THREE.Mesh(this.geo.box, this.mat.building);
    body.scale.set(width, height, 6);
    body.position.y = height / 2;
    group.add(body);
    // Окна-полосы: минималистичный силуэт кампуса
    for (let y = 2; y < height - 1; y += 2.2) {
      const strip = new THREE.Mesh(this.geo.box, this.mat.window);
      strip.scale.set(width * 0.8, 0.35, 0.05);
      strip.position.set(0, y, 3.03);
      group.add(strip);
    }
    return group;
  }

  #makeObstacle(kind) {
    const group = new THREE.Group();
    const add = (material, sx, sy, sz, x, y, z = 0) => {
      const mesh = new THREE.Mesh(this.geo.box, material);
      mesh.scale.set(sx, sy, sz);
      mesh.position.set(x, y, z);
      group.add(mesh);
    };
    if (kind === 'barrier') {
      // Турникет-барьер: перепрыгнуть
      add(this.mat.post, 0.12, 0.9, 0.12, -0.85, 0.45);
      add(this.mat.post, 0.12, 0.9, 0.12, 0.85, 0.45);
      add(this.mat.barrier, 1.9, 0.3, 0.2, 0, 0.72);
      add(this.mat.barrier, 1.9, 0.1, 0.12, 0, 0.3);
    } else if (kind === 'banner') {
      // Растяжка «Дедлайн»: пригнуться
      add(this.mat.post, 0.12, 2.6, 0.12, -0.95, 1.3);
      add(this.mat.post, 0.12, 2.6, 0.12, 0.95, 1.3);
      add(this.mat.banner, 1.9, 1.0, 0.1, 0, 1.75);
    } else {
      // Шкаф-стеллаж: только сменить полосу
      add(this.mat.block, 1.9, 2.4, 3.6, 0, 1.2);
      add(this.mat.blockAccent, 1.92, 0.06, 3.62, 0, 2.43);
      add(this.mat.blockAccent, 0.04, 2.0, 0.02, 0, 1.1, 1.81);
    }
    return group;
  }

  #setupPlayer() {
    this.player = new THREE.Group();
    this.scene.add(this.player);
    this.actions = new Map();
    this.animName = null;

    const shadow = new THREE.Mesh(
      new THREE.CircleGeometry(0.5, 24),
      new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.35, depthWrite: false })
    );
    shadow.rotation.x = -Math.PI / 2;
    shadow.position.y = 0.02;
    this.scene.add(shadow);
    this.shadow = shadow;

    const placeholder = new THREE.Mesh(new THREE.CapsuleGeometry(0.35, 0.9, 6, 12), standard(0x5eead4));
    placeholder.position.y = 0.8;
    this.player.add(placeholder);
    this.placeholder = placeholder;

    new GLTFLoader().load(
      this.modelUrl,
      (gltf) => {
        if (!this.renderer) return;
        const model = gltf.scene;
        prepareAvatarMaterials(model, { shadows: false });
        const fitScale = measureAvatarFitScale(model, RUNNER.PLAYER_HEIGHT);
        layoutAvatar(model, { fitScale, growthScale: 1 });
        const holder = new THREE.Group();
        holder.rotation.y = Math.PI;
        holder.add(model);
        this.player.remove(this.placeholder);
        this.player.add(holder);
        this.model = holder;

        this.mixer = new THREE.AnimationMixer(model);
        this.actions = collectAvatarActions(this.mixer, gltf.animations, { inPlace: true });
        this.animName = null;
        this.#playAction(AVATAR_CLIP.neutralIdle, { loop: true, fade: 0 });
        this.callbacks.onReady?.();
      },
      undefined,
      () => this.callbacks.onReady?.()
    );
  }

  #playAction(name, { loop = true, fade = 0.12 } = {}) {
    if (!this.actions?.size || this.animName === name) return;
    const next = this.actions.get(name) ?? this.actions.get(AVATAR_CLIP.neutralIdle);
    if (!next) return;
    next.reset();
    next.enabled = true;
    next.timeScale = name === AVATAR_CLIP.jump
      ? RUNNER.JUMP_ANIM_SCALE
      : name === AVATAR_CLIP.roll
        ? RUNNER.ROLL_ANIM_SCALE
        : 1;
    next.setLoop(loop ? THREE.LoopRepeat : THREE.LoopOnce, loop ? Infinity : 1);
    next.clampWhenFinished = !loop;
    const current = this.activeAction;
    if (current && current !== next) {
      next.setEffectiveWeight(1).fadeIn(fade).play();
      current.fadeOut(fade);
    } else {
      next.setEffectiveWeight(1).play();
    }
    this.activeAction = next;
    this.animName = name;
  }

  #bindInput() {
    const keyMap = {
      ArrowLeft: 'left', KeyA: 'left', ArrowRight: 'right', KeyD: 'right',
      ArrowUp: 'up', KeyW: 'up', Space: 'up', ArrowDown: 'down', KeyS: 'down'
    };
    this.onKey = (event) => {
      const action = keyMap[event.code];
      if (!action || this.state !== 'running') return;
      event.preventDefault();
      this.input(action);
    };
    window.addEventListener('keydown', this.onKey);

    // Свайпы: срабатывают сразу при прохождении порога, без ожидания отпускания
    let start = null;
    this.onPointerDown = (event) => {
      start = { x: event.clientX, y: event.clientY };
    };
    this.onPointerMove = (event) => {
      if (!start) return;
      const dx = event.clientX - start.x;
      const dy = event.clientY - start.y;
      if (Math.max(Math.abs(dx), Math.abs(dy)) < 28) return;
      if (Math.abs(dx) > Math.abs(dy)) this.input(dx > 0 ? 'right' : 'left');
      else this.input(dy > 0 ? 'down' : 'up');
      start = null;
    };
    this.onPointerUp = () => {
      start = null;
    };
    this.container.addEventListener('pointerdown', this.onPointerDown);
    this.container.addEventListener('pointermove', this.onPointerMove);
    this.container.addEventListener('pointerup', this.onPointerUp);
    this.container.addEventListener('pointercancel', this.onPointerUp);

    this.onVisibility = () => {
      if (document.hidden && this.state === 'running') {
        this.pause();
        this.callbacks.onAutoPause?.();
      }
    };
    document.addEventListener('visibilitychange', this.onVisibility);
  }

  // ---------- Трасса ----------

  #acquire(kind) {
    const pool = this.pools[kind];
    let mesh = pool.pop();
    if (!mesh) {
      mesh = kind === 'coin' ? new THREE.Mesh(this.geo.coin, this.mat.coin) : this.#makeObstacle(kind);
      if (kind === 'coin') {
        // Диск смотрит на игрока и вращается вокруг вертикали
        mesh.rotation.order = 'YXZ';
        mesh.rotation.x = Math.PI / 2;
      }
      this.scene.add(mesh);
    }
    mesh.visible = true;
    return mesh;
  }

  #release(obj) {
    obj.mesh.visible = false;
    this.pools[obj.kind].push(obj.mesh);
  }

  #difficulty() {
    return Math.min(1, (this.speed - RUNNER.START_SPEED) / (RUNNER.MAX_SPEED - RUNNER.START_SPEED));
  }

  #spawnAhead() {
    while (this.nextRowAt - this.distance < RUNNER.SPAWN_AHEAD) {
      this.#spawnRow(-(this.nextRowAt - this.distance));
      const difficulty = this.#difficulty();
      this.nextRowAt += 22 - difficulty * 8 + this.rng() * 6;
    }
  }

  #spawnRow(z) {
    const rng = this.rng;
    const difficulty = this.#difficulty();
    const lanes = [0, 1, 2].sort(() => rng() - 0.5);
    const roll = rng();
    const count = roll < 0.5 - difficulty * 0.25 ? 1 : roll < 0.92 ? 2 : 3;
    const kinds = [];
    for (let i = 0; i < count; i += 1) {
      const r = rng();
      kinds.push(r < 0.38 ? 'barrier' : r < 0.68 ? 'banner' : 'block');
    }
    // Всегда есть путь: при трёх занятых полосах хотя бы одна проходима прыжком или подкатом
    if (count === 3 && kinds.every((kind) => kind === 'block')) kinds[2] = rng() < 0.5 ? 'barrier' : 'banner';
    if (count === 3 && kinds.filter((kind) => kind === 'block').length === 2) {
      const index = kinds.findIndex((kind) => kind !== 'block');
      if (lanes[index] !== 1 && rng() < 0.5) kinds[index] = rng() < 0.5 ? 'barrier' : 'banner';
    }

    const blocked = new Map();
    for (let i = 0; i < count; i += 1) {
      const kind = kinds[i];
      const lane = lanes[i];
      const mesh = this.#acquire(kind);
      mesh.position.set(RUNNER.LANES[lane], 0, z);
      this.active.push({ kind, lane, mesh, ...OBSTACLES[kind] });
      blocked.set(lane, kind);
    }

    // Монеты: линия по свободной полосе или дуга над барьером
    const free = [0, 1, 2].filter((lane) => !blocked.has(lane));
    const barrierLane = [...blocked.entries()].find(([, kind]) => kind === 'barrier')?.[0];
    let coinLane = null;
    let arc = false;
    if (free.length && rng() < 0.8) {
      coinLane = free[Math.floor(rng() * free.length)];
    } else if (barrierLane !== undefined) {
      coinLane = barrierLane;
      arc = true;
    }
    if (coinLane === null) return;
    const n = 4 + Math.floor(rng() * 3);
    for (let k = 0; k < n; k += 1) {
      const mesh = this.#acquire('coin');
      let coinZ;
      let y = 0.75;
      if (arc) {
        const offset = (k - (n - 1) / 2) * RUNNER.COIN_SPACING;
        coinZ = z + offset;
        const half = ((n - 1) / 2) * RUNNER.COIN_SPACING || 1;
        y = 0.75 + 1.1 * (1 - (offset / half) ** 2);
      } else {
        coinZ = z + 6 - k * RUNNER.COIN_SPACING;
      }
      mesh.position.set(RUNNER.LANES[coinLane], y, coinZ);
      this.active.push({ kind: 'coin', lane: coinLane, mesh });
    }
  }

  // ---------- Игровой цикл ----------

  #loop = () => {
    this.frame = requestAnimationFrame(this.#loop);
    const dt = Math.min(this.clock.getDelta(), 0.05);
    if (this.state === 'running') this.#update(dt);
    this.#animatePlayer(dt);
    this.active.forEach((obj) => {
      if (obj.kind === 'coin') obj.mesh.rotation.y += dt * 3;
    });
    this.renderer.render(this.scene, this.camera);
  };

  #update(dt) {
    this.activeMs += dt * 1000;
    this.speed = Math.min(RUNNER.MAX_SPEED, RUNNER.START_SPEED + RUNNER.ACCELERATION * (this.activeMs / 1000));
    const dz = this.speed * dt;
    this.distance += dz;

    // Сдвиг мира
    for (let i = this.active.length - 1; i >= 0; i -= 1) {
      const obj = this.active[i];
      obj.mesh.position.z += dz;
      if (obj.mesh.position.z - (obj.depth ?? 0) / 2 > RUNNER.DESPAWN_BEHIND || (obj.kind === 'coin' && !obj.mesh.visible)) {
        if (obj.mesh.visible) this.#release(obj);
        else this.pools.coin.push(obj.mesh);
        this.active.splice(i, 1);
      }
    }
    this.pools.mark.forEach((mark) => {
      mark.position.z += dz;
      if (mark.position.z > 12) mark.position.z -= Math.ceil((RUNNER.SPAWN_AHEAD + 12) / 4) * 4;
    });
    this.pools.prop.forEach((prop) => {
      prop.position.z += dz;
      if (prop.position.z > 14) prop.position.z -= RUNNER.SPAWN_AHEAD + 40;
    });
    this.#spawnAhead();

    // Физика игрока
    const p = this.player.position;
    const targetX = RUNNER.LANES[this.lane];
    p.x += Math.sign(targetX - p.x) * Math.min(Math.abs(targetX - p.x), RUNNER.LANE_SWITCH_SPEED * dt);
    if (p.y > 0 || this.velocityY > 0) {
      this.velocityY -= RUNNER.GRAVITY * dt;
      p.y = Math.max(0, p.y + this.velocityY * dt);
      if (p.y === 0) this.velocityY = 0;
    }
    this.slideLeft = Math.max(0, this.slideLeft - dt);

    // Столкновения и монеты
    const sliding = this.slideLeft > 0 && p.y < 0.3;
    const top = p.y + (sliding ? RUNNER.SLIDE_HEIGHT : RUNNER.PLAYER_HEIGHT);
    for (const obj of this.active) {
      const dxAbs = Math.abs(obj.mesh.position.x - p.x);
      const dzAbs = Math.abs(obj.mesh.position.z);
      if (obj.kind === 'coin') {
        if (obj.mesh.visible && dxAbs < 0.8 && dzAbs < 0.8 && Math.abs(obj.mesh.position.y - (p.y + 0.8)) < 1.0) {
          obj.mesh.visible = false;
          this.coins += 1;
        }
        continue;
      }
      if (dxAbs < 0.9 + 0.35 && dzAbs < obj.depth / 2 + 0.3 && p.y < obj.top && top > obj.bottom) {
        this.#crash();
        return;
      }
    }
    this.#emitHud();
  }

  #crash() {
    this.state = 'crashed';
    this.crashTime = 0;
    this.#emitHud(true);
    this.callbacks.onCrash?.(this.result());
  }

  #emitHud(force = false) {
    const now = performance.now();
    if (!force && now - this.lastHud < 100) return;
    this.lastHud = now;
    this.callbacks.onHud?.({ ...this.result(), speed: this.speed });
  }

  #animatePlayer(dt) {
    const p = this.player.position;
    this.shadow.position.set(p.x, 0.02, 0);
    this.shadow.scale.setScalar(Math.max(0.4, 1 - p.y * 0.3));

    this.camera.position.x += (p.x * 0.55 - this.camera.position.x) * Math.min(1, dt * 6);
    this.camera.lookAt(this.camera.position.x * 0.4, 1.1, -8);

    if (this.state === 'paused') return;
    this.mixer?.update(dt);

    const sliding = this.slideLeft > 0 && p.y < 0.3;
    const airborne = p.y > 0.05 || this.velocityY > 1;
    if (this.state === 'crashed') {
      this.crashTime += dt;
      this.#playAction(AVATAR_CLIP.roll, { loop: false, fade: 0.08 });
      return;
    }
    if (this.state === 'running') {
      if (airborne) {
        this.#playAction(AVATAR_CLIP.jump, { loop: false, fade: 0.08 });
      } else if (sliding) {
        this.#playAction(AVATAR_CLIP.roll, { loop: false, fade: 0.08 });
      } else {
        this.#playAction(AVATAR_CLIP.run, { loop: true, fade: 0.12 });
        if (this.activeAction) {
          this.activeAction.timeScale = 0.85 + (this.speed / RUNNER.MAX_SPEED) * 0.55;
        }
      }
      return;
    }
    this.#playAction(AVATAR_CLIP.neutralIdle, { loop: true, fade: 0.2 });
  }
}
