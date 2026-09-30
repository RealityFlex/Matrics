import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Check, Flag, GitFork, Lock, Pencil, X } from 'lucide-react';
import { Badge, Button, ProgressBar } from '../../../components/ui/index.jsx';
import { maxBackButton } from '../../../utils/maxBridge.js';
import { buildGoalGraph, layoutGoalGraph, nodeKind } from '../goalGraph.js';
import '../../../styles/goal-map.css';

const KIND_LABEL = {
  done: 'Сделано',
  now: 'Можно делать',
  wait: 'Ждёт предыдущие',
  todo: 'Дальше'
};

function MapCanvas({ goal, compact = false, selectedId, onSelect }) {
  const wrapRef = useRef(null);
  const [width, setWidth] = useState(320);
  const graph = useMemo(() => buildGoalGraph(goal), [goal]);
  const layout = useMemo(
    () => layoutGoalGraph(graph, { width, compact }),
    [graph, width, compact]
  );

  useEffect(() => {
    const node = wrapRef.current;
    if (!node) return undefined;
    const measure = () => setWidth(Math.max(240, node.clientWidth));
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  if (!graph.total) {
    return <p className="fc-muted">Подзадач пока нет — карту появится после разбора цели.</p>;
  }

  return (
    <div ref={wrapRef} className={`goal-map ${compact ? 'goal-map--compact' : ''}`} style={{ height: layout.height }}>
      <svg className="goal-map__edges" width={layout.width} height={layout.height} aria-hidden="true">
        {layout.edges.map((edge) => (
          <path
            key={`${edge.from}-${edge.to}`}
            d={edge.d}
            className={`goal-map__link ${edge.done ? 'is-done' : ''}`}
          />
        ))}
      </svg>
      {graph.nodes.map((node) => {
        const box = layout.positions[node.id];
        if (!box) return null;
        const kind = nodeKind(node, graph.current?.id);
        const Tag = compact ? 'div' : 'button';
        return (
          <Tag
            key={node.id}
            type={compact ? undefined : 'button'}
            className={`goal-map__node goal-map__node--${kind} ${selectedId === node.id ? 'is-selected' : ''}`}
            style={{ left: box.x, top: box.y, width: box.w, height: box.h }}
            onClick={compact ? undefined : () => onSelect?.(node)}
            aria-label={compact ? undefined : `${node.title}. ${KIND_LABEL[kind]}`}
          >
            <span className="goal-map__mark" aria-hidden="true">
              {kind === 'done' ? <Check size={compact ? 12 : 14} /> : kind === 'wait' ? <Lock size={compact ? 12 : 14} /> : node.order_index + 1}
            </span>
            <span className="goal-map__title">{node.title}</span>
          </Tag>
        );
      })}
    </div>
  );
}

export function GoalRoadmapPreview({ goal, onOpen }) {
  const graph = useMemo(() => buildGoalGraph(goal), [goal]);
  if (!graph.total) return null;
  return (
    <button type="button" className="goal-map-preview" onClick={onOpen} aria-label="Открыть дорожную карту цели">
      <div className="goal-map-preview__meta">
        <GitFork size={14} aria-hidden="true" />
        <span>Дорожная карта</span>
        <span className="tabular">{graph.completed}/{graph.total}</span>
      </div>
      <MapCanvas goal={goal} compact />
    </button>
  );
}

export function GoalRoadmapScreen({
  isOpen,
  onClose,
  goal,
  isGoalCompleted,
  onCompleteTask,
  onEditTask
}) {
  const graph = useMemo(() => buildGoalGraph(goal), [goal]);
  const [selectedId, setSelectedId] = useState(null);
  const selected = graph.nodes.find((node) => node.id === selectedId) ?? graph.current ?? graph.nodes[0] ?? null;

  useEffect(() => {
    if (!isOpen) return;
    setSelectedId(graph.current?.id ?? graph.nodes[0]?.id ?? null);
  }, [isOpen, goal?.id]);

  useEffect(() => {
    if (!isOpen) return undefined;
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const release = maxBackButton.push(onClose);
    const onKey = (event) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener('keydown', onKey);
      release();
    };
  }, [isOpen, onClose]);

  if (!isOpen || !goal) return null;

  const kind = selected ? nodeKind(selected, graph.current?.id) : 'todo';
  const percent = graph.total ? Math.round((graph.completed / graph.total) * 100) : 0;

  return createPortal(
    <div className="goal-map-screen" role="dialog" aria-modal="true" aria-label={`Дорожная карта: ${goal.title}`}>
      <header className="goal-map-screen__head">
        <div>
          <p className="goal-map-screen__kicker">Дорожная карта цели</p>
          <h2 className="goal-map-screen__title">{goal.title}</h2>
        </div>
        <button type="button" className="goal-map-screen__close" onClick={onClose} aria-label="Закрыть карту">
          <X size={20} />
        </button>
      </header>

      <div className="goal-map-screen__progress">
        <ProgressBar
          value={graph.completed}
          max={graph.total || 1}
          label={`${percent}% пути`}
          showValue
          tone={graph.completed === graph.total && graph.total ? 'success' : 'primary'}
        />
      </div>

      <div className="goal-map-screen__canvas">
        <MapCanvas goal={goal} selectedId={selected?.id} onSelect={(node) => setSelectedId(node.id)} />
      </div>

      <ul className="goal-map-legend">
        <li><span className="goal-map__swatch goal-map__swatch--done" /> Сделано</li>
        <li><span className="goal-map__swatch goal-map__swatch--now" /> Можно делать</li>
        <li><span className="goal-map__swatch goal-map__swatch--wait" /> Ждёт предыдущие</li>
      </ul>

      {selected ? (
        <div className="goal-map-detail">
          <div className="goal-map-detail__head">
            <div>
              <div className="goal-map-detail__title">{selected.title}</div>
              {selected.description ? <p className="goal-map-detail__desc">{selected.description}</p> : null}
            </div>
            <Badge tone={kind === 'done' ? 'success' : kind === 'now' ? 'info' : 'neutral'}>{KIND_LABEL[kind]}</Badge>
          </div>
          {selected.dependsOn.length ? (
            <p className="goal-map-detail__deps">
              Опирается на:{' '}
              {selected.dependsOn
                .map((index) => graph.byOrder[index]?.title)
                .filter(Boolean)
                .join(', ')}
            </p>
          ) : (
            <p className="goal-map-detail__deps">Стартовый шаг — можно начинать сразу.</p>
          )}
          {!isGoalCompleted ? (
            <div className="goal-map-detail__actions">
              {selected.status !== 'completed' ? (
                <Button
                  icon={selected.locked ? <Lock size={16} /> : <Check size={16} />}
                  disabled={selected.locked}
                  onClick={() => onCompleteTask?.(goal, selected)}
                >
                  {selected.locked ? 'Сначала предыдущие шаги' : 'Выполнить шаг'}
                </Button>
              ) : null}
              <Button variant="secondary" icon={<Pencil size={16} />} onClick={() => onEditTask?.(goal, selected)}>
                Изменить
              </Button>
            </div>
          ) : (
            <p className="goal-map-detail__deps">
              <Flag size={14} aria-hidden="true" /> Цель уже завершена.
            </p>
          )}
        </div>
      ) : null}
    </div>,
    document.body
  );
}
