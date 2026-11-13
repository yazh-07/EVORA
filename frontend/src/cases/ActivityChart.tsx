import { useMemo } from 'react';
import type { EventRecord } from './workspaceData';

type Bucket = { from: string; to: string; label: string; count: number };
/** UTC day buckets; selected buckets cover exact day boundaries, not upload dates. */
export function activityBuckets(events: EventRecord[]): Bucket[] {
  const counts = new Map<string, number>();
  for (const event of events) {
    if (!event.observed_at_utc || !Number.isFinite(Date.parse(event.observed_at_utc))) continue;
    const day = new Date(event.observed_at_utc).toISOString().slice(0, 10);
    counts.set(day, (counts.get(day) ?? 0) + 1);
  }
  const dates = [...counts.keys()].sort();
  if (!dates.length) return [];
  const start = Date.parse(`${dates[0]}T00:00:00Z`), end = Date.parse(`${dates.at(-1)}T00:00:00Z`);
  const days = Math.round((end - start) / 86400000) + 1;
  const width = Math.max(1, Math.ceil(days / 30));
  const result: Bucket[] = [];
  for (let at = start; at <= end; at += width * 86400000) {
    const from = new Date(at).toISOString().slice(0, 10);
    const to = new Date(Math.min(end, at + (width - 1) * 86400000)).toISOString().slice(0, 10);
    const count = dates.filter(day => day >= from && day <= to).reduce((sum, day) => sum + counts.get(day)!, 0);
    result.push({ from, to, count, label: from === to ? from : `${from} – ${to}` });
  }
  return result;
}

export function ActivityChart({ events, from, to, select }: { events: EventRecord[]; from: string; to: string; select: (from: string, to: string) => void }) {
  const buckets = useMemo(() => activityBuckets(events), [events]);
  const max = Math.max(1, ...buckets.map(bucket => bucket.count));
  const unknown = events.filter(event => !event.observed_at_utc).length;
  return <section className="activity-chart" aria-label="Event activity chart">
    <div className="section-heading"><h3>Activity</h3><span title="Recorded event times">UTC</span></div>
    {buckets.length ? <>
      <div className="activity-bars">{buckets.map(bucket => <button type="button" key={bucket.from} title={`${bucket.label}: ${bucket.count} ${bucket.count === 1 ? 'event' : 'events'}`} aria-label={`${bucket.label}: ${bucket.count} ${bucket.count === 1 ? 'event' : 'events'}`} aria-pressed={from === bucket.from && to === bucket.to} onClick={() => select(bucket.from, bucket.to)}>
        <span className="bar-area"><span className="activity-bar" style={{ height: `${100 * bucket.count / max}%` }} /></span><span>{bucket.count}</span><small>{bucket.from.slice(5)}</small>
      </button>)}</div>
      <details className="context-help"><summary>Data</summary><table><caption>UTC event counts</caption><thead><tr><th>Date range</th><th>Events</th></tr></thead><tbody>{buckets.map(bucket => <tr key={bucket.from}><td>{bucket.label}</td><td>{bucket.count}</td></tr>)}</tbody></table></details>
    </> : <p>No dated events to chart.</p>}
    {unknown > 0 && <span className="chart-undated" title="Events without a timestamp are excluded from this chart">{unknown} undated</span>}
  </section>;
}
