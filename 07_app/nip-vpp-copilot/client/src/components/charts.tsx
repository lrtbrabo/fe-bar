/* Small, dependency-free charts built to the dataviz rules: thin marks with 4px rounded
   data-ends, 2px surface gaps, hairline grid, text in text tokens, hover tooltips, and a
   screen-reader table twin for every plot. */
import { useState, type ReactNode } from 'react';
import { fmtDayMonth, fmtInt, type SlaStatus } from '../lib/api';
import { slaMeta } from './status';

export function StatTile({ label, value, sub, accent }: { label: string; value: ReactNode; sub?: ReactNode; accent?: ReactNode }) {
  return (
    <div className="rounded-xl border bg-card p-4 flex flex-col gap-1 min-w-0">
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        {accent}
        <span className="truncate">{label}</span>
      </div>
      <div className="text-3xl font-semibold leading-tight text-foreground">{value}</div>
      {sub && <div className="text-xs text-muted-foreground">{sub}</div>}
    </div>
  );
}

export function Meter({ value, label }: { value: number; label?: string }) {
  const pct = Math.max(0, Math.min(1, value));
  return (
    <div className="flex items-center gap-2 min-w-[7rem]">
      <div className="h-1.5 flex-1 rounded-full bg-muted overflow-hidden" role="meter" aria-valuenow={Math.round(pct * 100)} aria-valuemin={0} aria-valuemax={100}>
        <div className="h-full rounded-full" style={{ width: `${pct * 100}%`, background: 'var(--viz-series-1)' }} />
      </div>
      <span className="text-xs tabular-nums text-foreground w-9 text-right">{label ?? `${Math.round(pct * 100)}%`}</span>
    </div>
  );
}

function Swatch({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
      <span className="h-2.5 w-2.5 rounded-sm" style={{ background: color }} />
      {label}
    </span>
  );
}

/* Weekly intake, emphasis form: the still-open part in the accent hue, the resolved part as
   gray context. One axis, stacked to the baseline. */
export function WeeklyColumns({ data }: { data: { semana: string; abertas: number; resolvidas: number }[] }) {
  const [hover, setHover] = useState<number | null>(null);
  const peakVal = Math.max(1, ...data.map((d) => d.abertas + d.resolvidas));
  const step = peakVal <= 10 ? 5 : 10;
  const max = Math.ceil(peakVal / step) * step;
  const plotH = 240;
  const peak = data.reduce((best, d, i) => (d.abertas + d.resolvidas > data[best].abertas + data[best].resolvidas ? i : best), 0);
  return (
    <div>
      <div className="flex gap-4 mb-3">
        <Swatch color="var(--viz-series-1)" label="Ainda em aberto" />
        <Swatch color="var(--viz-deemph)" label="Já resolvidas" />
      </div>
      <div className="relative" style={{ height: plotH + 22 }}>
        {[0.5, 1].map((f) => (
          <div key={f} className="absolute left-0 right-0 border-t" style={{ top: plotH * (1 - f), borderColor: 'var(--viz-grid)' }}>
            <span className="absolute -top-2.5 left-0 bg-card pr-1 text-[10px] tabular-nums text-muted-foreground">{Math.round(max * f)}</span>
          </div>
        ))}
        <div className="absolute left-0 right-0 border-t" style={{ top: plotH, borderColor: 'var(--viz-axis)' }} />
        <div className="absolute left-6 right-0 top-0 flex items-end gap-1.5" style={{ height: plotH }}>
          {data.map((d, i) => {
            const hTot = ((d.abertas + d.resolvidas) / max) * plotH;
            const hOpen = (d.abertas / max) * plotH;
            return (
              <div
                key={d.semana}
                className="relative flex-1 h-full flex flex-col justify-end cursor-default"
                onMouseEnter={() => setHover(i)}
                onMouseLeave={() => setHover(null)}
                tabIndex={0}
                onFocus={() => setHover(i)}
                onBlur={() => setHover(null)}
                aria-label={`Semana de ${fmtDayMonth(d.semana)}: ${d.abertas} em aberto, ${d.resolvidas} resolvidas`}
              >
                {i === peak && (
                  <span className="absolute left-1/2 -translate-x-1/2 text-[10px] tabular-nums text-foreground" style={{ bottom: hTot + 3 }}>
                    {d.abertas + d.resolvidas}
                  </span>
                )}
                <div className="mx-auto w-full max-w-[22px] flex flex-col" style={{ opacity: hover === null || hover === i ? 1 : 0.55 }}>
                  {d.resolvidas > 0 && (
                    <div style={{ height: Math.max(2, hTot - hOpen - (d.abertas > 0 ? 2 : 0)), background: 'var(--viz-deemph)', borderRadius: '4px 4px 0 0' }} />
                  )}
                  {d.abertas > 0 && (
                    <div
                      style={{
                        height: hOpen,
                        marginTop: d.resolvidas > 0 ? 2 : 0,
                        background: 'var(--viz-series-1)',
                        borderRadius: d.resolvidas > 0 ? 0 : '4px 4px 0 0',
                      }}
                    />
                  )}
                </div>
                {hover === i && (
                  <div className="absolute z-10 bottom-full mb-2 left-1/2 -translate-x-1/2 rounded-md border bg-popover px-2.5 py-1.5 text-xs shadow-sm whitespace-nowrap text-popover-foreground">
                    <div className="font-medium">Semana de {fmtDayMonth(d.semana)}</div>
                    <div className="tabular-nums">{d.abertas} em aberto · {d.resolvidas} resolvidas</div>
                  </div>
                )}
                <span className="absolute -bottom-5 left-1/2 -translate-x-1/2 text-[10px] text-muted-foreground whitespace-nowrap">
                  {i % 2 === 0 ? fmtDayMonth(d.semana) : ''}
                </span>
              </div>
            );
          })}
        </div>
      </div>
      <table className="sr-only">
        <caption>NIPs recebidas por semana</caption>
        <thead><tr><th>Semana</th><th>Em aberto</th><th>Resolvidas</th></tr></thead>
        <tbody>{data.map((d) => <tr key={d.semana}><td>{d.semana}</td><td>{d.abertas}</td><td>{d.resolvidas}</td></tr>)}</tbody>
      </table>
    </div>
  );
}

/* Ranked horizontal bars, one hue, value labelled at the bar end. */
export function BarList({ rows, onSelect }: {
  rows: { label: string; value: number; note?: string }[];
  onSelect?: (label: string) => void;
}) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <ul className="space-y-2.5">
      {rows.map((r) => (
        <li key={r.label}>
          <button
            type="button"
            disabled={!onSelect}
            onClick={() => onSelect?.(r.label)}
            className="w-full text-left group disabled:cursor-default"
          >
            <div className="flex items-baseline justify-between gap-2 text-sm">
              <span className="truncate text-foreground group-enabled:group-hover:underline underline-offset-2">{r.label}</span>
              <span className="shrink-0 tabular-nums text-foreground">
                {fmtInt(r.value)}
                {r.note && <span className="text-muted-foreground"> · {r.note}</span>}
              </span>
            </div>
            <div className="mt-1 h-2 rounded-full" style={{ background: 'var(--viz-grid)' }}>
              <div className="h-2 rounded-full" style={{ width: `${(r.value / max) * 100}%`, background: 'var(--viz-series-1)' }} />
            </div>
          </button>
        </li>
      ))}
    </ul>
  );
}

/* Open backlog by ANS deadline: one row per state, status color + icon + label, clickable. */
export function SlaRows({ rows, onSelect }: { rows: { sla_status: SlaStatus; n: number }[]; onSelect: (s: SlaStatus) => void }) {
  const order: SlaStatus[] = ['VENCIDA', 'CRITICA', 'ATENCAO', 'NO_PRAZO'];
  const total = Math.max(1, rows.reduce((a, r) => a + r.n, 0));
  return (
    <ul className="space-y-2">
      {order.map((s) => {
        const n = rows.find((r) => r.sla_status === s)?.n ?? 0;
        const m = slaMeta(s);
        const Icon = m.icon;
        return (
          <li key={s}>
            <button type="button" onClick={() => onSelect(s)} className="w-full rounded-lg px-2 py-1.5 -mx-2 text-left hover:bg-muted/60 transition-colors">
              <div className="flex items-center justify-between gap-2 text-sm">
                <span className="inline-flex items-center gap-2 text-foreground">
                  <Icon className="h-4 w-4" style={{ color: m.color }} aria-hidden />
                  {m.label}
                </span>
                <span className="tabular-nums text-foreground">{fmtInt(n)}</span>
              </div>
              <div className="mt-1.5 h-1.5 rounded-full" style={{ background: 'var(--viz-grid)' }}>
                <div className="h-1.5 rounded-full" style={{ width: `${(n / total) * 100}%`, background: m.color }} />
              </div>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
