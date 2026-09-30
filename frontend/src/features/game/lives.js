export function formatNextLife(iso) {
  if (!iso) return null;
  const ms = new Date(iso).getTime() - Date.now();
  if (Number.isNaN(ms) || ms <= 0) return 'скоро';
  const minutes = Math.max(1, Math.ceil(ms / 60000));
  if (minutes < 60) return `${minutes} мин`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `${hours} ч ${rest} мин` : `${hours} ч`;
}

export function livesOf(overview) {
  const max = overview?.lives_max ?? overview?.rewarded_runs_total ?? 0;
  const current = overview?.lives ?? overview?.rewarded_runs_left ?? 0;
  return { current, max };
}

export function livesWord(count) {
  const n = Math.abs(Number(count) || 0) % 100;
  const d = n % 10;
  if (n > 10 && n < 20) return 'жизней';
  if (d === 1) return 'жизнь';
  if (d >= 2 && d <= 4) return 'жизни';
  return 'жизней';
}

export function livesRewardText(added) {
  if (!added) return '';
  return ` · +${added} ${livesWord(added)} для забега`;
}
