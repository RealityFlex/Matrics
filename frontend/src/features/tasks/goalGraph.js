/**
 * Граф дорожной карты цели: слои, рёбра зависимостей и прогресс шагов.
 */

export function normalizeDependsOn(task, allTasks) {
  const indexes = new Set(allTasks.map((item) => item.order_index));
  const raw = Array.isArray(task.depends_on) ? task.depends_on : [];
  const cleaned = raw
    .map((value) => Number(value))
    .filter((index) => indexes.has(index) && index !== task.order_index);
  if (cleaned.length) return [...new Set(cleaned)];
  const sorted = [...allTasks].sort((a, b) => a.order_index - b.order_index);
  const position = sorted.findIndex((item) => item.id === task.id);
  if (position > 0) return [sorted[position - 1].order_index];
  return [];
}

export function buildGoalGraph(goal) {
  const tasks = [...(goal?.tasks ?? [])].sort((a, b) => a.order_index - b.order_index);
  const nodes = tasks.map((task) => ({
    ...task,
    dependsOn: normalizeDependsOn(task, tasks)
  }));
  const byOrder = Object.fromEntries(nodes.map((node) => [node.order_index, node]));
  const depth = {};

  const getDepth = (node, stack = new Set()) => {
    if (depth[node.order_index] != null) return depth[node.order_index];
    if (stack.has(node.order_index)) return 0;
    stack.add(node.order_index);
    const next = node.dependsOn.length
      ? 1 + Math.max(...node.dependsOn.map((index) => (byOrder[index] ? getDepth(byOrder[index], stack) : 0)))
      : 0;
    depth[node.order_index] = next;
    return next;
  };

  nodes.forEach((node) => getDepth(node));
  const layers = [];
  nodes.forEach((node) => {
    const layer = depth[node.order_index] ?? 0;
    (layers[layer] ||= []).push(node);
  });

  nodes.forEach((node) => {
    const waiting = node.dependsOn.some((index) => byOrder[index] && byOrder[index].status !== 'completed');
    node.locked = node.status !== 'completed' && waiting;
    node.available = node.status !== 'completed' && node.status !== 'cancelled' && !node.locked;
  });

  const current = nodes.find((node) => node.available) ?? null;
  const completed = nodes.filter((node) => node.status === 'completed').length;
  return { nodes, layers, byOrder, current, completed, total: nodes.length };
}

function connectorPath(from, to, nodeW, nodeH) {
  const x1 = from.x + nodeW / 2;
  const y1 = from.y + nodeH;
  const x2 = to.x + nodeW / 2;
  const y2 = to.y;
  const mid = (y1 + y2) / 2;
  return `M ${x1} ${y1} C ${x1} ${mid}, ${x2} ${mid}, ${x2} ${y2}`;
}

export function layoutGoalGraph(graph, { width = 320, compact = false } = {}) {
  const padX = 12;
  const padY = compact ? 8 : 16;
  const gapX = compact ? 10 : 14;
  const gapY = compact ? 36 : 52;
  const nodeH = compact ? 44 : 76;
  const maxCols = Math.max(1, ...graph.layers.map((layer) => layer.length), 1);
  const available = Math.max(72, width - padX * 2 - gapX * (maxCols - 1));
  const nodeW = Math.min(compact ? 148 : 200, available / maxCols);
  const positions = {};
  let y = padY;

  graph.layers.forEach((layer) => {
    const totalW = layer.length * nodeW + (layer.length - 1) * gapX;
    let x = Math.max(padX, (width - totalW) / 2);
    layer.forEach((node) => {
      positions[node.id] = { x, y, w: nodeW, h: nodeH };
      x += nodeW + gapX;
    });
    y += nodeH + gapY;
  });

  const edges = [];
  graph.nodes.forEach((node) => {
    node.dependsOn.forEach((order) => {
      const source = graph.byOrder[order];
      if (!source || !positions[source.id] || !positions[node.id]) return;
      edges.push({
        from: source.id,
        to: node.id,
        done: source.status === 'completed',
        d: connectorPath(positions[source.id], positions[node.id], positions[source.id].w, positions[source.id].h)
      });
    });
  });

  return {
    positions,
    edges,
    width,
    height: Math.max(y - gapY + padY, padY * 2 + nodeH),
    nodeH
  };
}

export function nodeKind(node, currentId) {
  if (node.status === 'completed') return 'done';
  if (node.status === 'cancelled') return 'wait';
  if (node.locked) return 'wait';
  if (currentId && node.id === currentId) return 'now';
  if (node.available) return 'now';
  return 'todo';
}
