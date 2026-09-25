import React, { useEffect, useState } from 'react';
import { adminApi } from '../api.js';
import { Badge, Button } from '../../components/ui/index.jsx';

const SAMPLE_CSV = `name,start_time,duration_minutes,location,group,reward_coins,reward_intelligence,reward_satisfaction
Математический анализ,2026-10-05T09:00:00,90,А-250,КРСО-15-22,5,15,8
Основы программирования,2026-10-05T10:40:00,90,Б-114,КРСО-15-22,5,15,8
История России,2026-10-06T09:00:00,90,В-301,КРСО-15-22,5,10,5`;

/**
 * Тестовая интеграция расписания: имитация выгрузки из вузовской системы (CSV).
 * Все занятия помечаются как смоделированные данные — требование ТЗ (п. 10 ограничений).
 */
export function ScheduleImportSection({ isActive }) {
  const [csvText, setCsvText] = useState(SAMPLE_CSV);
  const [createdBy, setCreatedBy] = useState('');
  const [groups, setGroups] = useState([]);
  const [demoGroupId, setDemoGroupId] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(null);

  useEffect(() => {
    if (!isActive) return;
    adminApi
      .listGroups()
      .then((list) => {
        const items = Array.isArray(list) ? list : [];
        setGroups(items);
        if (items[0]) {
          setDemoGroupId((value) => value || String(items[0].id));
          setCreatedBy((value) => value || String(items[0].creator_id ?? ''));
        }
      })
      .catch(() => setGroups([]));
  }, [isActive]);

  const run = async (kind, action) => {
    setBusy(kind);
    setError(null);
    try {
      setResult({ kind, data: await action() });
    } catch (runError) {
      setError(runError?.message ?? 'Операция не выполнена');
    } finally {
      setBusy(null);
    }
  };

  const createdById = Number(createdBy);

  return (
    <section className={`admin-section ${isActive ? 'active' : ''}`}>
      <div className="section-header">
        <h2>Тестовое расписание</h2>
        <Badge tone="warning">Смоделированные данные</Badge>
      </div>
      <p className="curator-note">
        Реальной интеграции с системой вуза в MVP нет. Здесь можно загрузить CSV, имитирующий выгрузку расписания: занятия
        получают пометку «Тестовые данные» в приложении и в отчётах. Время — местное (APP_UTC_OFFSET_HOURS).
      </p>

      <div className="curator-card" style={{ marginBottom: 16 }}>
        <h3>Демо для защиты</h3>
        <p className="curator-note">Создаёт пару, идущую прямо сейчас (для отметки), и пару, закончившуюся 20 минут назад (для пропуска и «дня без штрафа»).</p>
        <div className="curator-toolbar">
          <label>
            Группа:{' '}
            <select value={demoGroupId} onChange={(e) => setDemoGroupId(e.target.value)}>
              {groups.map((group) => (
                <option key={group.id} value={group.id}>
                  {group.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            ID создателя:{' '}
            <input className="admin-login__input" style={{ width: 90 }} value={createdBy} onChange={(e) => setCreatedBy(e.target.value.replace(/\D/g, ''))} />
          </label>
          <Button
            size="sm"
            loading={busy === 'demo'}
            disabled={!demoGroupId || !createdById}
            onClick={() => run('demo', () => adminApi.seedDemoLessons(Number(demoGroupId), createdById))}
          >
            Создать демо-пары
          </Button>
        </div>
      </div>

      <div className="curator-card">
        <h3>Импорт CSV</h3>
        <textarea
          className="admin-login__input"
          style={{ width: '100%', minHeight: 160, padding: 12, fontFamily: 'monospace', fontSize: 13 }}
          value={csvText}
          onChange={(e) => setCsvText(e.target.value)}
          aria-label="CSV расписания"
        />
        <div className="curator-toolbar" style={{ marginTop: 12 }}>
          <Button
            size="sm"
            variant="secondary"
            loading={busy === 'dry'}
            disabled={!createdById}
            onClick={() => run('dry', () => adminApi.importSchedule({ created_by: createdById, csv_text: csvText, dry_run: true }))}
          >
            Проверить
          </Button>
          <Button
            size="sm"
            loading={busy === 'import'}
            disabled={!createdById}
            onClick={() => run('import', () => adminApi.importSchedule({ created_by: createdById, csv_text: csvText }))}
          >
            Импортировать
          </Button>
          {result?.data?.batch_id ? (
            <Button
              size="sm"
              variant="danger"
              loading={busy === 'delete'}
              onClick={() => run('delete', () => adminApi.deleteImportBatch(result.data.batch_id))}
            >
              Удалить эту выгрузку
            </Button>
          ) : null}
        </div>
      </div>

      {error ? (
        <div className="inline-error" role="alert">
          {error}
        </div>
      ) : null}
      {result ? (
        <pre className="curator-card" style={{ marginTop: 16, whiteSpace: 'pre-wrap', fontSize: 13 }}>
          {JSON.stringify(result.data, null, 2)}
        </pre>
      ) : null}
    </section>
  );
}
