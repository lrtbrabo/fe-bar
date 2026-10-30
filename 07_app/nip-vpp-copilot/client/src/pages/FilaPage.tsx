import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router';
import { Button, Card, CardContent, CardHeader, CardTitle, Skeleton } from '@databricks/appkit-ui/react';
import { Check, CheckCircle2, Info, MessageSquare, Sparkles, X, XCircle } from 'lucide-react';
import { Meter } from '../components/charts';
import { Pill, SlaBadge, TipoGuia } from '../components/status';
import { useAgent, useAgentSuggestions } from '../components/agent';
import {
  DECISAO_LABEL, fmtDate, getJSON, postJSON, prazoLabel,
  type Decisao, type NipDetail, type NipListItem,
} from '../lib/api';

const FILTROS: { key: string; label: string }[] = [
  { key: 'ATIVAS', label: 'Em aberto' },
  { key: 'CRITICA', label: 'Vence em até 1 dia' },
  { key: 'ATENCAO', label: 'Vence em até 3 dias' },
  { key: 'VENCIDA', label: 'Vencidas' },
  { key: 'RESOLVIDA', label: 'Resolvidas' },
  { key: 'TODAS', label: 'Todas' },
];

export function FilaPage() {
  const [params, setParams] = useSearchParams();
  const sla = params.get('sla') ?? 'ATIVAS';
  const selectedId = params.get('nip');
  const [list, setList] = useState<NipListItem[] | null>(null);
  const [detail, setDetail] = useState<NipDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [version, setVersion] = useState(0);

  // Refs keep the latest selection/setter without making the list refetch on every click.
  const selectedRef = useRef(selectedId);
  selectedRef.current = selectedId;
  const setParamsRef = useRef(setParams);
  setParamsRef.current = setParams;
  const select = (id: string, replace = false) =>
    setParamsRef.current((p) => { const n = new URLSearchParams(p); n.set('nip', id); return n; }, { replace });

  useEffect(() => {
    getJSON<NipListItem[]>(`/api/nips?sla=${sla}`)
      .then((rows) => {
        setList(rows);
        const cur = selectedRef.current;
        if (rows.length && (!cur || !rows.some((r) => r.nip_id === cur))) {
          setParamsRef.current((p) => { const n = new URLSearchParams(p); n.set('nip', rows[0].nip_id); return n; }, { replace: true });
        }
      })
      .catch(() => setList([]));
  }, [sla, version]);

  useEffect(() => {
    if (!selectedId) { setDetail(null); return; }
    setLoadingDetail(true);
    getJSON<NipDetail>(`/api/nips/${selectedId}`)
      .then(setDetail)
      .catch(() => setDetail(null))
      .finally(() => setLoadingDetail(false));
  }, [selectedId, version]);

  const tema = detail?.nip.tema;
  useAgentSuggestions(
    selectedId
      ? [
          `Resuma a NIP ${selectedId}: reclamação, guia associada, justificativa e prazo.`,
          `O beneficiário da NIP ${selectedId} tem contatos negativos no call center antes da NIP?`,
          `Quantas NIPs do tema "${tema ?? ''}" estão vencidas e qual a exposição a multa?`,
        ]
      : ['Quais NIPs vencem em até 1 dia e qual o tema de cada uma?'],
  );

  const setFiltro = (key: string) => setParams(new URLSearchParams({ sla: key }));

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[360px_1fr] gap-5">
      {/* Queue */}
      <div className="min-w-0">
        <div className="flex flex-wrap gap-1 mb-3">
          {FILTROS.map((f) => (
            <button
              key={f.key}
              type="button"
              onClick={() => setFiltro(f.key)}
              className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                sla === f.key ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground hover:text-foreground'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
        <p className="text-xs text-muted-foreground mb-2">{list ? `${list.length} NIPs · mais urgentes primeiro` : 'carregando…'}</p>
        <div className="space-y-2 xl:max-h-[calc(100vh-12rem)] overflow-y-auto pr-1">
          {list === null
            ? Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-20 w-full" />)
            : list.length === 0
              ? <p className="text-sm text-muted-foreground py-8 text-center">Nenhuma NIP neste filtro.</p>
              : list.map((n) => (
                <button
                  key={n.nip_id}
                  type="button"
                  onClick={() => select(n.nip_id)}
                  className={`w-full text-left rounded-lg border p-3 transition-colors ${
                    selectedId === n.nip_id ? 'border-primary bg-primary/5' : 'hover:bg-muted/50'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-xs text-muted-foreground">{n.nip_id}</span>
                    <SlaBadge status={n.sla_status} />
                  </div>
                  <div className="text-sm font-medium mt-1 truncate text-foreground first-letter:uppercase">{n.tema}</div>
                  <div className="text-xs text-muted-foreground truncate">{n.beneficiario_nome ?? '—'} · {n.nome_plano}</div>
                  <div className="flex items-center justify-between gap-2 mt-1 text-xs text-muted-foreground">
                    <span>{prazoLabel(n)}</span>
                    {n.ultima_decisao && (
                      <span className="inline-flex items-center gap-1 text-foreground">
                        <Check className="h-3 w-3" style={{ color: 'var(--status-good)' }} aria-hidden />
                        {DECISAO_LABEL[n.ultima_decisao]}
                      </span>
                    )}
                  </div>
                </button>
              ))}
        </div>
      </div>

      {/* Detail */}
      <div className="min-w-0">
        {!detail ? (
          loadingDetail ? <Skeleton className="h-96 w-full" /> : <p className="text-sm text-muted-foreground mt-8">Selecione uma NIP na fila.</p>
        ) : (
          <NipDetailView key={detail.nip.nip_id} d={detail} onDecided={() => setVersion((v) => v + 1)} />
        )}
      </div>
    </div>
  );
}

function recomendacao(d: NipDetail): { tone: 'good' | 'warning' | 'neutral'; text: string } {
  if (d.nip.resolvida) return { tone: 'neutral', text: 'NIP já resolvida pelo analista; a checagem fica como registro.' };
  if (!d.rol.length) return { tone: 'neutral', text: 'Sem guia associada: o analista precisa localizar a VPP manualmente.' };
  const pendentes = d.rol.filter((r) => r.status_item !== 'APROVADO');
  if (!pendentes.length) {
    return { tone: 'neutral', text: 'Nenhum item negado na guia: a reclamação tende a ser de demora. Confirme a liberação e informe o beneficiário.' };
  }
  const fora = pendentes.filter((r) => !(r.no_rol && r.segmentacao_cobre));
  const seg = (d.nip.plano_segmentacao ?? '').toLowerCase();
  if (!fora.length) {
    return { tone: 'good', text: `Sugestão: reverter a negativa. Os itens negados ou em análise constam no rol da ANS e são cobertos pela segmentação do plano (${seg}).` };
  }
  return {
    tone: 'warning',
    text: `Sugestão: manter a negativa de ${fora.map((f) => f.descricao_procedimento).join(', ')}, fora da segmentação do plano (${seg}). Fundamente o parecer na cobertura contratada.`,
  };
}

function sentimento(s: number | null): { label: string; color: string } {
  if (s == null) return { label: '', color: 'var(--viz-neutral)' };
  if (s <= -0.2) return { label: 'tom negativo', color: 'var(--viz-negative)' };
  if (s >= 0.2) return { label: 'tom positivo', color: 'var(--viz-positive)' };
  return { label: 'tom neutro', color: 'var(--viz-neutral)' };
}

function YesNo({ ok }: { ok: boolean | null }) {
  return ok ? (
    <span className="inline-flex items-center gap-1 text-foreground"><Check className="h-3.5 w-3.5" style={{ color: 'var(--status-good)' }} aria-hidden />sim</span>
  ) : (
    <span className="inline-flex items-center gap-1 text-foreground"><X className="h-3.5 w-3.5" style={{ color: 'var(--status-critical)' }} aria-hidden />não</span>
  );
}

function NipDetailView({ d, onDecided }: { d: NipDetail; onDecided: () => void }) {
  const agent = useAgent();
  const n = d.nip;
  const [parecer, setParecer] = useState(n.parecer_sugerido ?? '');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState<Decisao | null>(null);
  const chosen = d.candidatas.find((c) => c.escolhida);
  const descartadas = d.candidatas.filter((c) => !c.escolhida);
  const rec = recomendacao(d);
  const recColor = rec.tone === 'good' ? 'var(--status-good)' : rec.tone === 'warning' ? 'var(--status-warning)' : 'var(--viz-axis)';

  async function decide(decisao: Decisao) {
    setSaving(true);
    try {
      await postJSON(`/api/nips/${n.nip_id}/feedback`, { decisao, parecer_final: parecer });
      setSaved(decisao);
      onDecided();
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-sm text-muted-foreground">{n.nip_id}</span>
        <SlaBadge status={n.sla_status} />
        <span className="text-sm text-muted-foreground">{prazoLabel(n)}</span>
        <Button size="sm" variant="outline" className="ml-auto" onClick={() => agent.ask(`Resuma a NIP ${n.nip_id}: reclamação, guia associada, justificativa e prazo.`)}>
          <Sparkles className="h-3.5 w-3.5" /> Perguntar ao agente sobre esta NIP
        </Button>
      </div>
      <h2 className="text-xl font-semibold text-foreground first-letter:uppercase">{n.tema}</h2>

      <div className="grid grid-cols-1 xl:grid-cols-[1.2fr_1fr] gap-4">
        <div className="space-y-4 min-w-0">
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-base">Reclamação do beneficiário</CardTitle></CardHeader>
            <CardContent>
              <p className="text-sm text-foreground">“{n.reclamacao_texto}”</p>
              <p className="text-xs text-muted-foreground mt-2">
                {n.beneficiario_nome} · {n.nome_plano} ({(n.plano_segmentacao ?? '').toLowerCase()}) · aberta em {fmtDate(n.data_criacao)}
                {n.vpp_citada ? ` · citou a guia ${n.vpp_citada}` : ''}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2 flex flex-row items-center justify-between space-y-0">
              <CardTitle className="text-base">Guia associada pelo agente</CardTitle>
              {n.auto_resolvavel
                ? <Pill color="var(--status-good)" icon={<CheckCircle2 className="h-3 w-3" style={{ color: 'var(--status-good)' }} aria-hidden />}>pronta para resolver</Pill>
                : <Pill color="var(--status-warning)" icon={<Info className="h-3 w-3" style={{ color: 'var(--status-warning)' }} aria-hidden />}>requer revisão</Pill>}
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="font-medium text-foreground">{n.matched_vpp_numero ?? 'nenhuma'}</span>
                <TipoGuia tipo={n.matched_tipo} />
                {chosen && <span className="text-xs text-muted-foreground">criada em {fmtDate(chosen.data)} · {chosen.dias_antes_nip} dias antes da NIP</span>}
              </div>
              {n.confidence != null && (
                <div>
                  <div className="text-xs text-muted-foreground mb-1">Confiança do agente</div>
                  <Meter value={n.confidence} />
                </div>
              )}
              <p className="text-sm text-muted-foreground">{n.justificativa}</p>

              <div className="pt-1">
                <div className="text-xs font-medium text-muted-foreground mb-1.5">
                  Guias avaliadas ({d.candidatas.length}) · por que as outras foram descartadas
                </div>
                <ul className="space-y-1.5">
                  {[...(chosen ? [chosen] : []), ...descartadas].map((c) => (
                    <li key={c.manifestacao_id} className={`flex gap-2 rounded-md border px-2.5 py-2 ${c.dentro_janela ? '' : 'opacity-60'}`}>
                      {c.escolhida
                        ? <CheckCircle2 className="h-4 w-4 mt-0.5 shrink-0" style={{ color: 'var(--viz-series-1)' }} aria-hidden />
                        : <XCircle className="h-4 w-4 mt-0.5 shrink-0 text-muted-foreground" aria-hidden />}
                      <div className="min-w-0 text-xs">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <span className="font-medium text-foreground">{c.vpp_numero}</span>
                          <TipoGuia tipo={c.tipo} />
                          <span className="text-muted-foreground">{fmtDate(c.data)} · {c.status.toLowerCase()}</span>
                        </div>
                        <div className="text-muted-foreground line-clamp-1">{c.procedimentos_texto}</div>
                        <div className={c.escolhida ? 'font-medium text-foreground' : 'text-foreground'}>{c.motivo}</div>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-base">Checagem no rol da ANS e no plano</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <div
                className="rounded-md px-3 py-2 text-sm text-foreground"
                style={{ background: `color-mix(in oklch, ${recColor} 14%, transparent)` }}
              >
                {rec.text}
              </div>
              {d.rol.length > 0 && (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-left text-muted-foreground border-b">
                        <th className="py-1.5 pr-2 font-medium">Item da guia</th>
                        <th className="py-1.5 pr-2 font-medium">Status</th>
                        <th className="py-1.5 pr-2 font-medium">No rol</th>
                        <th className="py-1.5 font-medium">Plano cobre</th>
                      </tr>
                    </thead>
                    <tbody>
                      {d.rol.map((r) => (
                        <tr key={r.codigo_tuss} className="border-b last:border-0 align-top">
                          <td className="py-1.5 pr-2">
                            <div className="text-foreground">{r.descricao_procedimento}</div>
                            <div className="text-muted-foreground">{r.dut_texto}</div>
                          </td>
                          <td className="py-1.5 pr-2 text-foreground whitespace-nowrap">{r.status_item.toLowerCase().replace('_', ' ')}</td>
                          <td className="py-1.5 pr-2"><YesNo ok={r.no_rol} /></td>
                          <td className="py-1.5"><YesNo ok={r.segmentacao_cobre} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4 min-w-0">
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-base">Parecer sugerido</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <textarea
                value={parecer}
                onChange={(e) => setParecer(e.target.value)}
                rows={7}
                className="w-full rounded-md border bg-background p-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              />
              <div className="flex flex-wrap gap-2">
                <Button onClick={() => decide('APROVADO')} disabled={saving}>Aprovar e enviar</Button>
                <Button variant="outline" onClick={() => decide('AJUSTADO')} disabled={saving}>Salvar ajuste</Button>
                <Button variant="ghost" onClick={() => decide('REJEITADO')} disabled={saving}>Rejeitar associação</Button>
              </div>
              {saved && (
                <p className="text-sm text-foreground inline-flex items-center gap-1.5">
                  <CheckCircle2 className="h-4 w-4" style={{ color: 'var(--status-good)' }} aria-hidden />
                  {DECISAO_LABEL[saved]} e gravado no Lakebase.
                </p>
              )}
              {d.feedback.length > 0 && (
                <p className="text-xs text-muted-foreground">
                  Histórico: {d.feedback.map((f) => `${DECISAO_LABEL[f.decisao].toLowerCase()} em ${f.quando}`).join(' · ')}
                </p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Linha do tempo do beneficiário</CardTitle>
              <p className="text-xs text-muted-foreground">Contatos no call center, guias e a NIP. Muitas NIPs avisam antes de chegar.</p>
            </CardHeader>
            <CardContent>
              <ol className="relative border-l pl-4 space-y-3" style={{ borderColor: 'var(--viz-grid)' }}>
                {d.timeline.map((e, i) => {
                  const s = sentimento(e.sentimento);
                  const dot = e.tipo === 'NIP' ? 'var(--status-critical)' : e.tipo === 'GUIA' ? 'var(--viz-series-1)' : s.color;
                  return (
                    <li key={`${e.tipo}-${i}`} className="relative">
                      <span className="absolute -left-[21px] top-1 h-2.5 w-2.5 rounded-full ring-2 ring-card" style={{ background: dot }} />
                      <div className="text-xs text-muted-foreground">
                        {fmtDate(e.quando)}{e.tipo === 'CONTATO' && s.label ? ` · ${s.label}` : ''}
                      </div>
                      <div className="text-sm text-foreground inline-flex items-center gap-1.5">
                        {e.tipo === 'CONTATO' && <MessageSquare className="h-3.5 w-3.5 text-muted-foreground" aria-hidden />}
                        {e.titulo}
                      </div>
                      {e.detalhe && <div className="text-xs text-muted-foreground line-clamp-2">{e.detalhe}</div>}
                    </li>
                  );
                })}
              </ol>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
