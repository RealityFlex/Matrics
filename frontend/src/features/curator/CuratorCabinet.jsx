import React, { useCallback, useEffect, useState } from 'react';
import { useAppState } from '../../state/AppProvider.jsx';
import { Badge, Button, Card, ProgressBar, StateView } from '../../components/ui/index.jsx';
import { Modal } from '../../components/common/Modal.jsx';
import { toast } from '../../components/ui/toast.jsx';
import {
  curatorGroups,
  groupAtRisk,
  groupAttendance,
  groupInvite,
  groupLessons,
  groupSupport,
  lessonCode,
  lessonQrImage,
  linkQrImage,
  nudgeStudent,
  resolveSupport
} from '../../services/curator.js';
import { shareContent } from '../../utils/maxBridge.js';
import { AlertTriangle, LifeBuoy, QrCode, UserPlus } from 'lucide-react';
import '../../styles/features-extra.css';

const FLAGS = {
  asked_help: { text: 'Просит помощи', tone: 'danger' },
  satisfaction_drop: { text: 'Падает настроение', tone: 'danger' },
  low_satisfaction: { text: 'Низкое настроение', tone: 'warning' },
  low_attendance_14d: { text: 'Мало посещений', tone: 'warning' },
  recent_penalty: { text: 'Пропуск без «заморозки»', tone: 'neutral' }
};

const time = (iso) => new Date(iso).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
const percent = (value) => (value == null ? '—' : `${Math.round(value * 100)}%`);

/** Экран аудитории: QR-код пары + код + живой счётчик отметок */
function LessonQrModal({ lesson, userId, onClose }) {
  const [code, setCode] = useState(null);
  const [qrUrl, setQrUrl] = useState(null);
  const [counter, setCounter] = useState({ attended: lesson.attended, expected: lesson.expected });
  const [secondsLeft, setSecondsLeft] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    let timer = null;
    let url = null;
    const load = async () => {
      try {
        const data = await lessonCode(lesson.id, userId);
        const image = await lessonQrImage(lesson.id, userId);
        if (cancelled) {
          URL.revokeObjectURL(image);
          return;
        }
        if (url) URL.revokeObjectURL(url);
        url = image;
        setCode(data);
        setQrUrl(image);
        setSecondsLeft(data.expires_in_seconds);
        setError(null);
        timer = setTimeout(load, Math.max(1, data.expires_in_seconds) * 1000 + 300);
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError?.message ?? 'Не удалось получить код');
          timer = setTimeout(load, 5000);
        }
      }
    };
    load();
    const tick = setInterval(() => setSecondsLeft((value) => (value > 0 ? value - 1 : value)), 1000);
    return () => {
      cancelled = true;
      clearTimeout(timer);
      clearInterval(tick);
      if (url) URL.revokeObjectURL(url);
    };
  }, [lesson.id, userId]);

  // Живой счётчик: сколько студентов уже отметилось
  useEffect(() => {
    const poll = setInterval(async () => {
      try {
        const lessons = await groupLessons(lesson.groupId, userId);
        const fresh = lessons.find((item) => item.id === lesson.id);
        if (fresh) setCounter({ attended: fresh.attended, expected: fresh.expected });
      } catch {
        /* счётчик — вспомогательный */
      }
    }, 5000);
    return () => clearInterval(poll);
  }, [lesson.id, lesson.groupId, userId]);

  return (
    <Modal isOpen onClose={onClose} title={lesson.name} size="md">
      <div className="qr-screen">
        {error ? <StateView state="error" title="Код недоступен" message={error} compact /> : null}
        {!code && !error ? <StateView state="loading" message="Готовим QR…" compact /> : null}
        {code ? (
          <>
            {qrUrl ? <img className="qr-screen__image" src={qrUrl} alt="QR-код для отметки через MAX" /> : null}
            <div className="qr-screen__code tabular" aria-live="polite">{code.code}</div>
            <div className="qr-screen__timer">Обновится через {secondsLeft ?? '…'} с</div>
            <div className="qr-screen__counter">
              <span className="tabular">
                {counter.attended} / {counter.expected}
              </span>{' '}
              отметились
            </div>
            <ProgressBar value={counter.attended} max={Math.max(1, counter.expected)} tone="success" />
            <p className="qr-screen__hint">Студенты сканируют QR камерой телефона или вводят код в мини-приложении.</p>
          </>
        ) : null}
      </div>
    </Modal>
  );
}

function InvitePanel({ groupId, userId }) {
  const [invite, setInvite] = useState(null);
  const [qr, setQr] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let url = null;
    setInvite(null);
    setQr(null);
    groupInvite(groupId, userId)
      .then(async (data) => {
        setInvite(data);
        if (data.student_link) {
          url = await linkQrImage(data.student_link, userId);
          setQr(url);
        }
      })
      .catch((loadError) => setError(loadError?.message ?? 'Ссылки недоступны'));
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [groupId, userId]);

  if (error) return <StateView state="error" title="Ссылки недоступны" message={error} compact />;
  if (!invite) return <StateView state="loading" compact />;

  const share = async (text, link) => {
    const result = await shareContent({ text, link });
    if (result === 'copied') toast.success('Ссылка скопирована');
  };

  return (
    <div className="invite">
      {qr ? <img className="invite__qr" src={qr} alt="QR-приглашение в группу" /> : null}
      <div className="invite__actions">
        {invite.student_link ? (
          <Button size="sm" onClick={() => share(`Вступай в группу ${invite.group_name} в «Матриксе»`, invite.student_link)}>
            Пригласить студентов
          </Button>
        ) : (
          <p className="curator-muted">Код группы: <b>{invite.invite_code}</b> (ссылка-приглашение пока недоступна)</p>
        )}
        {invite.curator_link ? (
          <Button size="sm" variant="secondary" onClick={() => share(`Ссылка куратора группы ${invite.group_name}`, invite.curator_link)}>
            Ссылка для второго куратора
          </Button>
        ) : null}
      </div>
      <div className="invite__chat">
        <b>Чат группы в MAX:</b>{' '}
        {invite.chat_bound ? (
          <Badge tone="success">привязан</Badge>
        ) : (
          <>
            добавьте бота в чат и отправьте <code>{invite.bind_chat_command}</code> — бот будет напоминать о парах и
            подводить итоги командной цели.
          </>
        )}
      </div>
    </div>
  );
}

/**
 * Кабинет куратора прямо в MAX: QR для отметки на паре с телефона, посещаемость,
 * студенты в зоне риска и обращения «Нужна помощь», приглашения в группу.
 */
export function CuratorCabinet({ isActive }) {
  const { user } = useAppState();
  const userId = user?.id;
  const [groups, setGroups] = useState([]);
  const [groupId, setGroupId] = useState(null);
  const [state, setState] = useState('loading');
  const [data, setData] = useState(null);
  const [qrLesson, setQrLesson] = useState(null);
  const [busy, setBusy] = useState(null);

  const loadGroups = useCallback(async () => {
    setState('loading');
    try {
      const response = await curatorGroups(userId);
      setGroups(response.groups);
      setGroupId((current) => current ?? response.groups[0]?.id ?? null);
      setState(response.groups.length ? 'ready' : 'empty');
    } catch {
      setState('error');
    }
  }, [userId]);

  const loadGroup = useCallback(async () => {
    if (!groupId) return;
    try {
      const [lessons, attendance, risk, support] = await Promise.all([
        groupLessons(groupId, userId),
        groupAttendance(groupId, userId),
        groupAtRisk(groupId, userId),
        groupSupport(groupId, userId)
      ]);
      setData({ lessons, attendance, risk: risk.students, support });
      setState('ready');
    } catch {
      setState('error');
    }
  }, [groupId, userId]);

  useEffect(() => {
    if (isActive && userId) loadGroups();
  }, [isActive, userId, loadGroups]);

  useEffect(() => {
    if (isActive && groupId) loadGroup();
  }, [isActive, groupId, loadGroup]);

  const handleNudge = async (student) => {
    setBusy(`nudge-${student.user_id}`);
    try {
      const result = await nudgeStudent(student.user_id, userId);
      toast.success('Сообщение отправлено', result.delivered ? `${student.username} получит сообщение в MAX` : 'Студент ещё не открывал бота в MAX');
    } catch (error) {
      toast.error('Не отправлено', error?.message);
    } finally {
      setBusy(null);
    }
  };

  const handleResolve = async (request) => {
    setBusy(`resolve-${request.id}`);
    try {
      await resolveSupport(request.id, userId);
      toast.success('Обращение закрыто');
      await loadGroup();
    } catch (error) {
      toast.error('Не удалось закрыть', error?.message);
    } finally {
      setBusy(null);
    }
  };

  if (state === 'loading' && !data) return <StateView state="loading" message="Загружаем группы…" />;
  if (state === 'error') return <StateView state="error" title="Кабинет недоступен" message="Проверьте, что вы вошли как куратор." onRetry={loadGroups} />;
  if (state === 'empty') {
    return (
      <StateView
        state="empty"
        title="У вас пока нет групп"
        message="Откройте ссылку куратора, которую прислала администрация вуза, — группа появится здесь."
      />
    );
  }

  const now = data?.lessons.find((lesson) => lesson.is_now);
  const next = data?.lessons.find((lesson) => !lesson.is_now);

  return (
    <div className="cabinet">
      <div className="cabinet__header">
        <h2 className="section-title">Мои группы</h2>
        {groups.length > 1 ? (
          <div className="segmented" role="tablist">
            {groups.map((group) => (
              <button
                key={group.id}
                type="button"
                role="tab"
                aria-selected={group.id === groupId}
                className={`segmented__item ${group.id === groupId ? 'is-active' : ''}`}
                onClick={() => setGroupId(group.id)}
              >
                {group.name}
              </button>
            ))}
          </div>
        ) : (
          <div className="curator-muted">{groups[0]?.name}</div>
        )}
      </div>

      {!data ? <StateView state="loading" compact /> : null}
      {data ? (
        <>
          <Card className={`checkin-card ${now ? 'checkin-card--live' : ''}`}>
            <div className="checkin-card__eyebrow">
              {now ? <Badge tone="success">Идёт сейчас</Badge> : <Badge>Ближайшая пара</Badge>}
              {(now ?? next)?.is_simulated ? <Badge tone="warning">Тестовые данные</Badge> : null}
            </div>
            {now ?? next ? (
              <>
                <h3 className="checkin-card__title">{(now ?? next).name}</h3>
                <div className="checkin-card__meta">
                  {time((now ?? next).start_time)}–{time((now ?? next).end_time)}
                  {(now ?? next).location ? ` · ${(now ?? next).location}` : ''}
                </div>
                {now ? (
                  <>
                    <ProgressBar value={now.attended} max={Math.max(1, now.expected)} tone="success" label="Отметились" showValue />
                    <Button size="lg" block icon={<QrCode size={18} aria-hidden="true" />} onClick={() => setQrLesson({ ...now, groupId })}>
                      Показать QR для отметки
                    </Button>
                  </>
                ) : (
                  <p className="curator-muted">QR появится за 15 минут до начала пары.</p>
                )}
              </>
            ) : (
              <p className="checkin-card__hint">В ближайшие два дня пар нет.</p>
            )}
          </Card>

          <div className="curator-kpis curator-kpis--compact">
            <div className="curator-kpi">
              <div className="curator-kpi__value">{percent(data.attendance.attendance_rate)}</div>
              <div className="curator-kpi__label">посещаемость за 30 дней</div>
            </div>
            <div className="curator-kpi">
              <div className="curator-kpi__value">{data.risk.length}</div>
              <div className="curator-kpi__label">в зоне риска</div>
            </div>
          </div>

          {data.support.length ? (
            <Card>
              <h3 className="card-subtitle inline-icon">
                <LifeBuoy size={18} aria-hidden="true" /> Просят помощи
              </h3>
              {data.support.map((request) => (
                <div key={request.id} className="miss-row">
                  <div>
                    <div className="miss-row__title">{request.username}</div>
                    <div className="miss-row__meta">{request.message || 'Без комментария'}</div>
                  </div>
                  <Button size="sm" variant="secondary" loading={busy === `resolve-${request.id}`} onClick={() => handleResolve(request)}>
                    Решено
                  </Button>
                </div>
              ))}
            </Card>
          ) : null}

          <Card>
            <h3 className="card-subtitle inline-icon">
              <AlertTriangle size={18} aria-hidden="true" /> Требуют внимания
            </h3>
            {data.risk.length ? (
              data.risk.map((student) => (
                <div key={student.user_id} className="risk-row">
                  <div className="risk-row__main">
                    <div className="risk-row__name">{student.username}</div>
                    <div className="curator-flags">
                      {student.flags.map((flag) => (
                        <Badge key={flag} tone={FLAGS[flag]?.tone ?? 'neutral'}>
                          {FLAGS[flag]?.text ?? 'Другой сигнал'}
                        </Badge>
                      ))}
                    </div>
                  </div>
                  <Button size="sm" variant="secondary" loading={busy === `nudge-${student.user_id}`} onClick={() => handleNudge(student)}>
                    Написать
                  </Button>
                </div>
              ))
            ) : (
              <p className="curator-muted">Все студенты в порядке.</p>
            )}
            <p className="curator-muted">Сигнал для разговора, а не оценка. Сложные случаи передавайте психологу или тьютору.</p>
          </Card>

          <Card>
            <h3 className="card-subtitle inline-icon">
              <UserPlus size={18} aria-hidden="true" /> Пригласить в группу
            </h3>
            <InvitePanel groupId={groupId} userId={userId} />
          </Card>
        </>
      ) : null}

      {qrLesson ? <LessonQrModal lesson={qrLesson} userId={userId} onClose={() => { setQrLesson(null); loadGroup(); }} /> : null}
    </div>
  );
}
