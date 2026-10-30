import { AlertOctagon, AlertTriangle, CheckCircle2, Clock, ShieldAlert } from 'lucide-react';
import type { ReactNode } from 'react';
import type { SlaStatus } from '../lib/api';

/* Status colors carry state only; each badge pairs the color with an icon + a label. */
const SLA_META: Record<SlaStatus, { label: string; color: string; icon: typeof Clock }> = {
  VENCIDA:   { label: 'Vencida',         color: 'var(--status-critical)', icon: AlertOctagon },
  CRITICA:   { label: 'Vence em até 1 dia',  color: 'var(--status-serious)',  icon: AlertTriangle },
  ATENCAO:   { label: 'Vence em até 3 dias', color: 'var(--status-warning)',  icon: Clock },
  NO_PRAZO:  { label: 'No prazo',        color: 'var(--status-good)',     icon: CheckCircle2 },
  RESOLVIDA: { label: 'Resolvida',       color: 'var(--viz-axis)',        icon: CheckCircle2 },
};

export const slaMeta = (s: SlaStatus) => SLA_META[s] ?? SLA_META.NO_PRAZO;

export function Pill({ color, icon, children }: { color: string; icon?: ReactNode; children: ReactNode }) {
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium text-foreground whitespace-nowrap"
      style={{ background: `color-mix(in oklch, ${color} 16%, transparent)` }}
    >
      {icon}
      {children}
    </span>
  );
}

export function SlaBadge({ status }: { status: SlaStatus }) {
  const m = slaMeta(status);
  const Icon = m.icon;
  return (
    <Pill color={m.color} icon={<Icon className="h-3 w-3" style={{ color: m.color }} aria-hidden />}>
      {m.label}
    </Pill>
  );
}

export function RiskBadge({ faixa }: { faixa: 'ALTO' | 'MEDIO' | 'BAIXO' }) {
  const color = faixa === 'ALTO' ? 'var(--status-critical)' : faixa === 'MEDIO' ? 'var(--status-warning)' : 'var(--status-good)';
  const label = faixa === 'ALTO' ? 'Risco alto' : faixa === 'MEDIO' ? 'Risco médio' : 'Risco baixo';
  return (
    <Pill color={color} icon={<ShieldAlert className="h-3 w-3" style={{ color }} aria-hidden />}>
      {label}
    </Pill>
  );
}

export function TipoGuia({ tipo }: { tipo: string | null }) {
  if (!tipo || tipo === 'NENHUMA') return <span className="text-xs text-muted-foreground">sem guia</span>;
  return (
    <span className="rounded border px-1.5 py-0.5 text-[11px] font-medium text-muted-foreground">
      {tipo === 'VPP_FILHA' ? 'item filho' : 'guia pai'}
    </span>
  );
}
