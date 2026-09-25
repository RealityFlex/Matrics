import React, { useCallback, useEffect, useState } from 'react';
import { adminApi } from '../api.js';
import { Badge, Button, StateView } from '../../components/ui/index.jsx';

const FLAG_LABELS = {
  satisfaction_drop: { text: 'Падает настроение', tone: 'danger' },
  low_satisfaction: { text: 'Низкое настроение', tone: 'danger' },
  low_attendance_14d: { text: 'Мало посещений', tone: 'warning' },
  recent_penalty: { text: 'Пропуск без «заморозки»', tone: 'warning' }
};

function percent(value) {
  return value == null ? '—' : `${Math.round(value * 100)}%`;
}

function WeeklyChart({ weeks }) {
  if (!weeks?.length) return null;
  return (
    <div className="curator-bars" role="img" aria-label="Посещаемость группы по неделям">
      {weeks.map((week) => {
        const rate = week.attendance_rate;
        return (
          <div key={week.week_start} className="curator-bar" title={`Неделя с ${week.week_start}: ${percent(rate)}`}>
            <span className="curator-bar__value">{percent(rate)}</span>
            <div
              className={`curator-bar__fill ${rate == null ? 'curator-bar__fill--empty' : ''}`}
              style={{ height: `${Math.max(2, (rate ?? 0) * 100)}%` }}
            />
            <span className="curator-bar__label">
              {new Date(week.week_start).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/**
 * Дашборд куратора: посещаемость группы, риск-лист по вовлечённости, динамика по неделям.
 * Только чтение поверх существующих данных (посещения, снимки персонажей, журнал наград).
 */
export function CuratorSection({ isActive }) {
  const [groups, setGroups] = useState([]);
  const [groupId, setGroupId] = useState(null);
  const [period, setPeriod] = useState(30);
  const [data, setData] = useState(null);
  const [state, setState] = useState('loading');

  const loadGroups = useCallback(async () => {
    setState('loading');
    try {
      const response = await adminApi.curatorGroups();
      const list = response?.groups ?? [];
      setGroups(list);
      setGroupId((current) => current ?? list[0]?.id ?? null);
      setState(list.length ? 'loading' : 'empty');
    } catch {
      setState('error');
    }
  }, []);

  const loadGroupData = useCallback(async () => {
    if (!groupId) return;
    setState('loading');
    try {
      const [attendance, atRisk, weekly] = await Promise.all([
        adminApi.curatorAttendance(groupId, period),
        adminApi.curatorAtRisk(groupId, 7),
        adminApi.curatorWeekly(groupId, 8)
      ]);
      setData({ attendance, atRisk, weekly });
      setState('ready');
    } catch {
      setState('error');
    }
  }, [groupId, period]);

  useEffect(() => {
    if (isActive) loadGroups();
  }, [isActive, loadGroups]);

  useEffect(() => {
    if (isActive && groupId) loadGroupData();
  }, [isActive, groupId, period, loadGroupData]);

  return (
    <section className={`admin-section ${isActive ? 'active' : ''}`}>
      <div className="section-header">
        <h2>Кабинет куратора</h2>
      </div>
      <p className="curator-note">
        Сводка по учебной группе: кто ходит на пары, у кого падает вовлечённость. Это сигнал для разговора со студентом, а не
        оценка — сложные ситуации передаются специалисту (психологу, тьютору).
      </p>

      <div className="curator-toolbar">
        <label>
          Группа:{' '}
          <select value={groupId ?? ''} onChange={(e) => setGroupId(Number(e.target.value))} disabled={!groups.length}>
            {groups.map((group) => (
              <option key={group.id} value={group.id}>
                {group.name} ({group.members})
              </option>
            ))}
          </select>
        </label>
        <label>
          Период:{' '}
          <select value={period} onChange={(e) => setPeriod(Number(e.target.value))}>
            <option value={7}>7 дней</option>
            <option value={30}>30 дней</option>
            <option value={90}>90 дней</option>
          </select>
        </label>
        <Button size="sm" variant="secondary" onClick={groupId ? loadGroupData : loadGroups}>
          Обновить
        </Button>
      </div>

      {state === 'loading' ? <StateView state="loading" message="Собираем сводку…" /> : null}
      {state === 'error' ? (
        <StateView state="error" title="Не удалось загрузить данные" message="Проверьте токен администратора или права куратора." onRetry={groupId ? loadGroupData : loadGroups} />
      ) : null}
      {state === 'empty' ? <StateView state="empty" title="Нет доступных групп" message="Создайте учебную группу и назначьте куратора (запрос PUT /api/users/{id}/role с ролью куратора и списком групп) или запустите scripts/seed_demo.py." /> : null}

      {state === 'ready' && data ? (
        <>
          <div className="curator-kpis">
            <div className="curator-kpi">
              <div className="curator-kpi__value">{percent(data.attendance.attendance_rate)}</div>
              <div className="curator-kpi__label">Посещаемость за {period} дн.</div>
            </div>
            <div className="curator-kpi">
              <div className="curator-kpi__value">{data.attendance.lessons_total}</div>
              <div className="curator-kpi__label">Прошедших пар</div>
            </div>
            <div className="curator-kpi">
              <div className="curator-kpi__value">{data.attendance.members_total}</div>
              <div className="curator-kpi__label">Студентов в группе</div>
            </div>
            <div className="curator-kpi">
              <div className="curator-kpi__value">{data.atRisk.students.length}</div>
              <div className="curator-kpi__label">В зоне риска</div>
            </div>
          </div>

          <div className="curator-grid">
            <div className="curator-card">
              <h3>Требуют внимания</h3>
              {data.atRisk.students.length ? (
                <table className="curator-table">
                  <thead>
                    <tr>
                      <th>Студент</th>
                      <th>Сигналы</th>
                      <th className="num">Настроение</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.atRisk.students.map((student) => (
                      <tr key={student.user_id}>
                        <td>{student.username}</td>
                        <td>
                          <div className="curator-flags">
                            {student.flags.map((flag) => (
                              <Badge key={flag} tone={FLAG_LABELS[flag]?.tone ?? 'neutral'}>
                                {FLAG_LABELS[flag]?.text ?? 'Другой сигнал'}
                              </Badge>
                            ))}
                          </div>
                        </td>
                        <td className="num">
                          {student.satisfaction ?? '—'}
                          {student.satisfaction_drop > 0 ? ` (−${student.satisfaction_drop})` : ''}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <StateView state="empty" title="Все в порядке" message="Нет студентов с падением вовлечённости." compact />
              )}
            </div>

            <div className="curator-card">
              <h3>Посещаемость по неделям</h3>
              <WeeklyChart weeks={data.weekly.weeks} />
            </div>

            <div className="curator-card" style={{ gridColumn: '1 / -1' }}>
              <h3>Студенты</h3>
              <table className="curator-table">
                <thead>
                  <tr>
                    <th>Студент</th>
                    <th className="num">Посещено</th>
                    <th className="num">Посещаемость</th>
                    <th className="num">Серия</th>
                    <th className="num">Настроение</th>
                  </tr>
                </thead>
                <tbody>
                  {data.attendance.per_student.map((student) => (
                    <tr key={student.user_id}>
                      <td>{student.username}</td>
                      <td className="num">
                        {student.attended}/{student.expected}
                      </td>
                      <td className="num">{percent(student.rate)}</td>
                      <td className="num">{student.current_streak}</td>
                      <td className="num">{student.satisfaction ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {data.attendance.per_lesson.some((lesson) => lesson.is_simulated) ? (
                <p className="curator-note">Часть занятий загружена из тестового расписания (смоделированные данные).</p>
              ) : null}
            </div>
          </div>
        </>
      ) : null}
    </section>
  );
}
