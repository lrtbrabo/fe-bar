import { useEffect, useState } from 'react';
import { Button, Card, CardContent, Skeleton } from '@databricks/appkit-ui/react';
import { CheckCircle2, PhoneCall, ShieldAlert, Sparkles, Target } from 'lucide-react';
import { Meter, StatTile } from '../components/charts';
import { RiskBadge } from '../components/status';
import { useAgent, useAgentSuggestions } from '../components/agent';
import { ACAO_LABEL, fmtInt, getJSON, postJSON, type AcaoRetencao, type RadarItem } from '../lib/api';

/* Out-of-sample recall of the propensity model on its test split (evidence/05_ml_propensity.md). */
const RECALL_TESTE = { acertos: 40, total: 52 };

const PERGUNTAS = [
  'Quantos beneficiários estão em risco alto de abrir NIP e por quê?',
  'Quais planos concentram beneficiários em risco alto ou médio?',
  'Qual o sentimento médio no call center de quem abriu NIP comparado a quem não abriu?',
];

export function RadarPage() {
  const agent = useAgent();
  useAgentSuggestions(PERGUNTAS);
  const [faixa, setFaixa] = useState<'ALTO' | 'RISCO'>('RISCO');
  const [rows, setRows] = useState<RadarItem[] | null>(null);
  const [acao, setAcao] = useState<Record<string, AcaoRetencao>>({});
  const [busy, setBusy] = useState<string | null>(null);

  const load = () => getJSON<RadarItem[]>('/api/radar?faixa=RISCO').then(setRows).catch(() => setRows([]));
  useEffect(() => { void load(); }, []);

  async function acionar(r: RadarItem) {
    setBusy(r.beneficiario_id);
    try {
      await postJSON(`/api/radar/${r.beneficiario_id}/acao`, { acao: acao[r.beneficiario_id] ?? 'LIGAR' });
      await load();
    } finally {
      setBusy(null);
    }
  }

  const visiveis = rows ? (faixa === 'ALTO' ? rows.filter((r) => r.faixa_risco === 'ALTO') : rows) : null;
  const alto = rows?.filter((r) => r.faixa_risco === 'ALTO').length ?? 0;
  const acionados = rows?.filter((r) => r.ultima_acao).length ?? 0;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold text-foreground">Radar de prevenção</h2>
          <p className="text-sm text-muted-foreground max-w-3xl">
            Beneficiários que ainda não abriram NIP, mas cujo comportamento no call center parece com o de quem abriu.
            Acionar antes evita a reclamação na ANS, o prazo de 5 dias e a multa.
          </p>
        </div>
        <Button variant="outline" onClick={() => agent.ask(PERGUNTAS[0])}>
          <Sparkles className="h-4 w-4" /> Perguntar ao agente
        </Button>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatTile
          label="Risco alto (≥ 70%)"
          accent={<ShieldAlert className="h-3.5 w-3.5" style={{ color: 'var(--status-critical)' }} aria-hidden />}
          value={rows ? fmtInt(alto) : '—'}
          sub="ligar hoje"
        />
        <StatTile
          label="Em observação (risco alto + médio)"
          value={rows ? fmtInt(rows.length) : '—'}
          sub="priorizar autorizações pendentes"
        />
        <StatTile
          label="Já acionados"
          accent={<PhoneCall className="h-3.5 w-3.5" style={{ color: 'var(--viz-series-1)' }} aria-hidden />}
          value={fmtInt(acionados)}
          sub="ações registradas no Lakebase"
        />
        <StatTile
          label="NIPs que o modelo anteciparia"
          accent={<Target className="h-3.5 w-3.5" style={{ color: 'var(--viz-series-1)' }} aria-hidden />}
          value={`${Math.round((RECALL_TESTE.acertos / RECALL_TESTE.total) * 100)}%`}
          sub={`${RECALL_TESTE.acertos} de ${RECALL_TESTE.total} no teste fora da amostra`}
        />
      </div>

      <div className="flex gap-1">
        {(['RISCO', 'ALTO'] as const).map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setFaixa(f)}
            className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
              faixa === f ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground hover:text-foreground'
            }`}
          >
            {f === 'RISCO' ? 'Risco alto e médio' : 'Só risco alto'}
          </button>
        ))}
      </div>

      <Card>
        <CardContent className="p-0">
          {visiveis === null ? (
            <div className="p-4 space-y-2">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-12" />)}</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-muted-foreground border-b">
                    <th className="px-4 py-2.5 font-medium">Beneficiário</th>
                    <th className="px-2 py-2.5 font-medium">Chance de abrir NIP</th>
                    <th className="px-2 py-2.5 font-medium">Por que o modelo aponta</th>
                    <th className="px-2 py-2.5 font-medium">Último contato</th>
                    <th className="px-4 py-2.5 font-medium">Ação do call center</th>
                  </tr>
                </thead>
                <tbody>
                  {visiveis.map((r) => (
                    <tr key={r.beneficiario_id} className="border-b last:border-0 align-middle">
                      <td className="px-4 py-2.5">
                        <div className="text-foreground">{r.nome ?? '—'}</div>
                        <div className="text-xs text-muted-foreground">{r.beneficiario_id} · {r.nome_plano} · {r.uf}</div>
                      </td>
                      <td className="px-2 py-2.5">
                        <div className="flex flex-col items-start gap-1">
                          <Meter value={r.score} />
                          <RiskBadge faixa={r.faixa_risco} />
                        </div>
                      </td>
                      <td className="px-2 py-2.5 text-xs text-foreground max-w-[18rem]">{r.motivos}</td>
                      <td className="px-2 py-2.5 text-xs text-muted-foreground whitespace-nowrap">há {r.dias_desde_ultima} dias</td>
                      <td className="px-4 py-2.5">
                        {r.ultima_acao ? (
                          <span className="inline-flex items-center gap-1.5 text-xs text-foreground">
                            <CheckCircle2 className="h-4 w-4" style={{ color: 'var(--status-good)' }} aria-hidden />
                            {ACAO_LABEL[r.ultima_acao]} · {r.acionado_em}
                          </span>
                        ) : (
                          <div className="flex items-center gap-2">
                            <select
                              aria-label="Ação"
                              value={acao[r.beneficiario_id] ?? 'LIGAR'}
                              onChange={(e) => setAcao((a) => ({ ...a, [r.beneficiario_id]: e.target.value as AcaoRetencao }))}
                              className="h-8 rounded-md border bg-background px-2 text-xs text-foreground"
                            >
                              {(Object.keys(ACAO_LABEL) as AcaoRetencao[]).map((k) => <option key={k} value={k}>{ACAO_LABEL[k]}</option>)}
                            </select>
                            <Button size="sm" onClick={() => acionar(r)} disabled={busy === r.beneficiario_id}>Acionar</Button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
      <p className="text-xs text-muted-foreground">
        Pontuação em lote do modelo <span className="font-mono">nip_propensity_model</span> (Unity Catalog), o mesmo servido no endpoint{' '}
        <span className="font-mono">nip-propensity</span>. Nomes mascarados pelo Unity Catalog.
      </p>
    </div>
  );
}
