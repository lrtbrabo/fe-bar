import { useState, useEffect, useCallback } from 'react';
import {
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Skeleton,
} from '@databricks/appkit-ui/react';

/* ---------- types ---------- */
interface Nip {
  nip_id: string;
  beneficiario_nome: string | null;
  nome_plano: string | null;
  sla_status: string;
  dias_para_prazo: number | null;
  reclamacao_texto: string | null;
  matched_manifestacao_id: string | null;
  matched_tipo: string | null;
  confidence: number | null;
  auto_resolvavel: boolean | null;
  justificativa: string | null;
  parecer_sugerido: string | null;
  vpp_citada: string | null;
  resolvida: boolean | null;
}
interface Kpis {
  sla: { sla_status: string; n: number }[];
  agg: { total: number; abertas: number; auto_abertas: number; conf_media: number | string };
}

/* ---------- SLA semantic styling ---------- */
function slaClass(s: string): string {
  switch (s) {
    case 'VENCIDA': return 'bg-red-100 text-red-800 border-red-200';
    case 'CRITICA': return 'bg-orange-100 text-orange-800 border-orange-200';
    case 'ATENCAO': return 'bg-amber-100 text-amber-800 border-amber-200';
    case 'NO_PRAZO': return 'bg-emerald-100 text-emerald-800 border-emerald-200';
    case 'RESOLVIDA': return 'bg-slate-100 text-slate-600 border-slate-200';
    default: return 'bg-slate-100 text-slate-600 border-slate-200';
  }
}
function Badge({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${className}`}>{children}</span>;
}

/* ---------- app ---------- */
const FILTERS = ['ATIVAS', 'CRITICA', 'ATENCAO', 'VENCIDA', 'RESOLVIDA', 'TODAS'];

export default function App() {
  const [kpis, setKpis] = useState<Kpis | null>(null);
  const [nips, setNips] = useState<Nip[]>([]);
  const [filter, setFilter] = useState('ATIVAS');
  const [selected, setSelected] = useState<Nip | null>(null);
  const [parecer, setParecer] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState<string | null>(null);

  const loadKpis = useCallback(() => {
    fetch('/api/kpis').then((r) => r.json() as Promise<Kpis>).then(setKpis).catch(() => undefined);
  }, []);

  const loadNips = useCallback(() => {
    setLoading(true);
    const q = filter === 'ATIVAS' || filter === 'TODAS' ? 'TODAS' : filter;
    fetch(`/api/nips?sla=${q}`)
      .then((r) => r.json() as Promise<Nip[]>)
      .then((rows) => {
        const list = filter === 'ATIVAS' ? rows.filter((n) => !n.resolvida) : rows;
        setNips(list);
        setSelected((cur) => (cur && list.some((n) => n.nip_id === cur.nip_id) ? cur : list[0] ?? null));
      })
      .catch(() => setNips([]))
      .finally(() => setLoading(false));
  }, [filter]);

  useEffect(() => { loadKpis(); }, [loadKpis]);
  useEffect(() => { loadNips(); }, [loadNips]);
  useEffect(() => { setParecer(selected?.parecer_sugerido ?? ''); setSaved(null); }, [selected]);

  async function decide(decisao: 'APROVADO' | 'AJUSTADO' | 'REJEITADO') {
    if (!selected) return;
    setSaving(true);
    try {
      await fetch(`/api/nips/${selected.nip_id}/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decisao, parecer_final: parecer }),
      });
      setSaved(decisao);
    } finally {
      setSaving(false);
    }
  }

  const conf = selected?.confidence != null ? Math.round(selected.confidence * 100) : null;

  return (
    <div className="min-h-screen bg-background">
      {/* header */}
      <header className="border-b px-6 py-3">
        <h1 className="text-lg font-semibold text-foreground">NIP → VPP Copilot</h1>
        <p className="text-sm text-muted-foreground">Resolução de NIPs da ANS — VPP inferida e parecer sugerido (dados sintéticos)</p>
      </header>

      {/* KPI row */}
      <div className="px-6 py-4 grid grid-cols-2 md:grid-cols-5 gap-3">
        <Kpi label="NIPs abertas" value={kpis?.agg.abertas} />
        <Kpi label="Auto-resolvíveis (abertas)" value={kpis?.agg.auto_abertas} accent="text-emerald-600" />
        <Kpi label="Confiança média" value={kpis ? `${Math.round(Number(kpis.agg.conf_media) * 100)}%` : undefined} />
        <Kpi label="Vencidas (backlog)" value={kpis?.sla.find((s) => s.sla_status === 'VENCIDA')?.n} accent="text-red-600" />
        <Kpi label="Total no sistema" value={kpis?.agg.total} />
      </div>

      <div className="px-6 pb-8 grid grid-cols-1 lg:grid-cols-[380px_1fr] gap-6">
        {/* queue */}
        <div>
          <div className="flex flex-wrap gap-1 mb-3">
            {FILTERS.map((f) => (
              <button key={f} onClick={() => setFilter(f)}
                className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                  filter === f ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground hover:text-foreground'}`}>
                {f}
              </button>
            ))}
          </div>
          <div className="space-y-2 max-h-[70vh] overflow-y-auto pr-1">
            {loading
              ? Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-16 w-full" />)
              : nips.length === 0
                ? <p className="text-sm text-muted-foreground py-8 text-center">Nenhuma NIP neste filtro.</p>
                : nips.map((n) => (
                  <button key={n.nip_id} onClick={() => setSelected(n)}
                    className={`w-full text-left rounded-lg border p-3 transition-colors ${
                      selected?.nip_id === n.nip_id ? 'border-primary bg-primary/5' : 'hover:bg-muted/50'}`}>
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-xs text-muted-foreground">{n.nip_id}</span>
                      <Badge className={slaClass(n.sla_status)}>{n.sla_status}</Badge>
                    </div>
                    <div className="text-sm font-medium mt-1 truncate">{n.beneficiario_nome ?? '—'}</div>
                    <div className="text-xs text-muted-foreground truncate">{n.reclamacao_texto ?? ''}</div>
                    <div className="text-xs mt-1 text-muted-foreground">
                      {n.resolvida ? 'resolvida' : `prazo em ${n.dias_para_prazo}d`}
                      {n.auto_resolvavel ? ' · auto-resolvível' : ''}
                    </div>
                  </button>
                ))}
          </div>
        </div>

        {/* detail */}
        <div>
          {!selected ? (
            <p className="text-sm text-muted-foreground mt-8">Selecione uma NIP na fila.</p>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-mono text-sm text-muted-foreground">{selected.nip_id}</span>
                <Badge className={slaClass(selected.sla_status)}>{selected.sla_status}</Badge>
                {!selected.resolvida && selected.dias_para_prazo != null && (
                  <span className="text-sm text-muted-foreground">prazo ANS em {selected.dias_para_prazo} dia(s)</span>
                )}
              </div>

              <Card>
                <CardHeader><CardTitle className="text-base">Reclamação do beneficiário</CardTitle></CardHeader>
                <CardContent>
                  <p className="text-sm">{selected.reclamacao_texto}</p>
                  <p className="text-xs text-muted-foreground mt-2">
                    {selected.beneficiario_nome} · {selected.nome_plano}
                    {selected.vpp_citada ? ` · guia citada: ${selected.vpp_citada}` : ''}
                  </p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0">
                  <CardTitle className="text-base">VPP inferida pelo agente</CardTitle>
                  {selected.auto_resolvavel
                    ? <Badge className="bg-emerald-100 text-emerald-800 border-emerald-200">auto-resolvível</Badge>
                    : <Badge className="bg-amber-100 text-amber-800 border-amber-200">requer revisão</Badge>}
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex items-center gap-3 text-sm">
                    <span className="font-mono">{selected.matched_manifestacao_id}</span>
                    <Badge className="bg-slate-100 text-slate-700 border-slate-200">{selected.matched_tipo}</Badge>
                  </div>
                  {conf != null && (
                    <div>
                      <div className="flex justify-between text-xs text-muted-foreground mb-1">
                        <span>confiança</span><span>{conf}%</span>
                      </div>
                      <div className="h-2 rounded-full bg-muted overflow-hidden">
                        <div className={`h-full ${conf >= 80 ? 'bg-emerald-500' : 'bg-amber-500'}`} style={{ width: `${conf}%` }} />
                      </div>
                    </div>
                  )}
                  <p className="text-sm text-muted-foreground">{selected.justificativa}</p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader><CardTitle className="text-base">Parecer sugerido</CardTitle></CardHeader>
                <CardContent className="space-y-3">
                  <textarea
                    value={parecer}
                    onChange={(e) => setParecer(e.target.value)}
                    rows={5}
                    className="w-full rounded-md border bg-background p-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                  <div className="flex flex-wrap gap-2">
                    <Button onClick={() => decide('APROVADO')} disabled={saving}>Aprovar e enviar</Button>
                    <Button variant="outline" onClick={() => decide('AJUSTADO')} disabled={saving}>Salvar ajuste</Button>
                    <Button variant="ghost" onClick={() => decide('REJEITADO')} disabled={saving}>Rejeitar match</Button>
                    {saved && <span className="text-sm text-emerald-600 self-center">Decisão registrada: {saved}</span>}
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Kpi({ label, value, accent = 'text-foreground' }: { label: string; value?: number | string; accent?: string }) {
  return (
    <div className="rounded-lg border p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={`text-2xl font-semibold ${accent}`}>{value ?? '—'}</div>
    </div>
  );
}
