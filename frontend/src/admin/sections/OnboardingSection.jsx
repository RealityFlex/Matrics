import React, { useCallback, useEffect, useState } from 'react';
import { adminApi } from '../api.js';
import { Badge, Button, StateView } from '../../components/ui/index.jsx';

const SAMPLE_SCHEDULE = `name,start_time,duration_minutes,location,group
Программирование,2026-10-05T09:00:00,90,301,ИС-11
Математика,2026-10-05T10:40:00,90,215,ИС-11
Программирование,2026-10-05T12:40:00,90,301,ИС-12`;

function QrImage({ link }) {
  const [url, setUrl] = useState(null);
  useEffect(() => {
    let current = null;
    if (link) {
      adminApi.linkQrImageUrl(link).then((value) => {
        current = value;
        setUrl(value);
      }).catch(() => setUrl(null));
    }
    return () => {
      if (current) URL.revokeObjectURL(current);
    };
  }, [link]);
  return url ? <img className="onboard-qr" src={url} alt="QR-приглашение" /> : null;
}

function OrganizationCard({ org }) {
  return (
    <div className="curator-card onboard-org">
      <div className="onboard-org__head">
        <span className="onboard-org__swatch" style={{ background: org.brand_color || 'var(--color-primary)' }} aria-hidden="true" />
        <h3>{org.name}</h3>
        {org.city ? <Badge>{org.city}</Badge> : null}
      </div>
      <div className="onboard-groups">
        {org.groups.map((group) => (
          <div key={group.id} className="onboard-group">
            <div className="onboard-group__title">
              <b>{group.name}</b> · студентов: {group.members} · цель пары {group.team_goal_percent}%
              {group.chat_bound ? <Badge tone="success">чат привязан</Badge> : null}
            </div>
            {group.student_link ? <QrImage link={group.student_link} /> : null}
            <dl className="onboard-links">
              <dt>Студентам</dt>
              <dd><code>{group.student_link || `код ${group.invite_code} (задайте MAX_BOT_USERNAME для ссылок)`}</code></dd>
              <dt>Куратору</dt>
              <dd><code>{group.curator_link || `код ${group.curator_code}`}</code></dd>
              <dt>Чат группы</dt>
              <dd>добавьте бота в чат и отправьте <code>{group.bind_chat_command}</code></dd>
            </dl>
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Подключение вуза или колледжа «за 10 минут»: организация, группы, ссылки-приглашения
 * для студентов и кураторов, брендированная локация персонажа, тестовое расписание.
 */
export function OnboardingSection({ isActive }) {
  const [form, setForm] = useState({
    name: '',
    short_name: '',
    city: 'Казань',
    brand_color: '#1E5BA8',
    groups: 'ИС-11\nИС-12',
    schedule_csv: SAMPLE_SCHEDULE
  });
  const [orgs, setOrgs] = useState([]);
  const [state, setState] = useState('loading');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [digest, setDigest] = useState(null);

  const load = useCallback(async () => {
    setState('loading');
    try {
      setOrgs(await adminApi.listOrganizations());
      setState('ready');
    } catch {
      setState('error');
    }
  }, []);

  useEffect(() => {
    if (isActive) load();
  }, [isActive, load]);

  const update = (field) => (event) => setForm((prev) => ({ ...prev, [field]: event.target.value }));

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await adminApi.onboardOrganization({
        name: form.name.trim(),
        short_name: form.short_name.trim() || null,
        city: form.city.trim() || null,
        brand_color: form.brand_color,
        groups: form.groups.split('\n').map((name) => name.trim()).filter(Boolean).map((name) => ({ name })),
        schedule_csv: form.schedule_csv.trim() || null
      });
      setForm((prev) => ({ ...prev, name: '', short_name: '' }));
      await load();
    } catch (submitError) {
      setError(submitError?.message ?? 'Не удалось подключить организацию');
    } finally {
      setBusy(false);
    }
  };

  const sendDigest = async () => {
    setDigest('sending');
    try {
      const result = await adminApi.sendCuratorDigest();
      setDigest(`Сводка отправлена кураторам: ${result.delivered} из ${result.curators}`);
    } catch (digestError) {
      setDigest(digestError?.message ?? 'Не отправлено');
    }
  };

  return (
    <section className={`admin-section ${isActive ? 'active' : ''}`}>
      <div className="section-header">
        <h2>Подключение вуза</h2>
        <Button size="sm" variant="secondary" loading={digest === 'sending'} onClick={sendDigest}>
          Отправить сводку кураторам
        </Button>
      </div>
      {digest && digest !== 'sending' ? <p className="curator-note">{digest}</p> : null}
      <p className="curator-note">
        Организация получает группы со ссылками-приглашениями в MAX, фирменную локацию персонажа и расписание. Студенты
        вступают по ссылке, кураторы — по своей ссылке (роль и кабинет в мини-приложении), чат группы привязывается командой
        боту. Расписание в демо — тестовый CSV (смоделированные данные).
      </p>

      <form className="curator-card onboard-form" onSubmit={submit}>
        <label>
          Название организации
          <input className="admin-login__input" value={form.name} onChange={update('name')} required placeholder="Казанский колледж информатики" />
        </label>
        <div className="onboard-form__row">
          <label>
            Краткое название
            <input className="admin-login__input" value={form.short_name} onChange={update('short_name')} placeholder="ККИ" />
          </label>
          <label>
            Город
            <input className="admin-login__input" value={form.city} onChange={update('city')} />
          </label>
          <label>
            Фирменный цвет
            <input type="color" className="onboard-color" value={form.brand_color} onChange={update('brand_color')} />
          </label>
        </div>
        <label>
          Группы (по одной в строке)
          <textarea className="admin-login__input onboard-textarea" value={form.groups} onChange={update('groups')} rows={3} />
        </label>
        <label>
          Расписание (CSV, тестовая выгрузка; колонка group — название группы)
          <textarea className="admin-login__input onboard-textarea onboard-textarea--mono" value={form.schedule_csv} onChange={update('schedule_csv')} rows={5} />
        </label>
        {error ? <div className="inline-error" role="alert">{error}</div> : null}
        <Button type="submit" loading={busy} disabled={!form.name.trim()}>
          Подключить организацию
        </Button>
      </form>

      {state === 'loading' ? <StateView state="loading" compact /> : null}
      {state === 'error' ? <StateView state="error" title="Список организаций недоступен" onRetry={load} compact /> : null}
      {state === 'ready' ? (
        orgs.length ? orgs.slice().reverse().map((org) => <OrganizationCard key={org.id} org={org} />) : (
          <StateView state="empty" title="Организаций пока нет" message="Подключите первую — ссылки и QR появятся здесь." compact />
        )
      ) : null}
    </section>
  );
}
