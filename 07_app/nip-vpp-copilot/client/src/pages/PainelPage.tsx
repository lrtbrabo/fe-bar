import { useEffect, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router';
import { Button, Card, CardContent, CardHeader, CardTitle, Input, Skeleton } from '@databricks/appkit-ui/react';
import { AlertOctagon, AlertTriangle, ArrowRight, CheckCircle2, Clock, Radar, Sparkles } from 'lucide-react';
import { BarList, SlaRows, StatTile, WeeklyColumns } from '../components/charts';
import { useAgent, useAgentSuggestions } from '../components/agent';
import {
  ACAO_LABEL, DECISAO_LABEL, fmtBRL, fmtDate, fmtInt, fmtPct, getJSON, loadPremissas, savePremissas,
  type AcaoRetencao, type Activity, type Decisao, type Overview, type Premissas,
} from '../lib/api';

const PERGUNTAS = [
  'Qual a exposição a multa das NIPs vencidas, por tema?',
  'Quais temas concentram mais NIPs em aberto?',
  'Quais NIPs vencem em até 1 dia e qual o tema de cada uma?',
  'Quantas NIPs abertas têm itens fora da segmentação do plano?',
];

export function PainelPage() {
  const navigate = useNavigate();
  const agent = useAgent();
  useAgentSuggestions(PERGUNTAS);
  const [data, setData] = useState<Overview | null>(null);
  const [activity, setActivity] = useState<Activity[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [premissas, setPremissas] = useState<Premissas>(loadPremissas);

  useEffect(() => {
    getJSON<Overview>('/api/overview').then(setData).catch((e: Error) => setError(e.message));
    getJSON<Activity[]>('/api/activity').then(setActivity).catch(() => setActivity([]));
  }, []);

  const updatePremissa = (k: keyof Premissas, v: string) => {
    const n = Number(v.replace(/\D/g, ''));
    const next = { ...premissas, [k]: Number.isFinite(n) ? n : 0 };
    setPremissas(next);
    savePremissas(next);
  };

  if (error) return <p className="text-sm" style={{ color: 'var(--status-critical)' }}>Não foi possível carregar o painel: {error}</p>;
  if (!data) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-80" />
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">{Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-28" />)}</div>
        <div className="grid lg:grid-cols-2 gap-4"><Skeleton className="h-64" /><Skeleton className="h-64" /></div>
      </div>
    );
  }

  const t = data.totals;
  const exposicao = t.vencidas * premissas.multaPorNip;
  const horasPotencial = (t.prontas * premissas.minutosPorNip) / 60;
  const horasRealizadas = (data.decisions.resolvidas * premissas.minutosPorNip) / 60;
  const goFila = (sla: string) => navigate(`/fila?sla=${sla}`);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold text-foreground">Painel da coordenação de NIPs</h2>
          <p className="text-sm text-muted-foreground">
            Posição da fila em {fmtDate(data.asOf)} · prazo ANS de 5 dias por NIP · dados sintéticos
          </p>
        </div>
        <Button variant="outline" onClick={() => agent.open()}>
          <Sparkles className="h-4 w-4" /> Perguntar ao agente
        </Button>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <StatTile label="NIPs em aberto" value={fmtInt(t.abertas)} sub={`de ${fmtInt(t.total)} recebidas no período`} />
        <StatTile
          label="Vencem em até 1 dia"
          accent={<AlertTriangle className="h-3.5 w-3.5" style={{ color: 'var(--status-serious)' }} aria-hidden />}
          value={fmtInt(t.criticas)}
          sub="prioridade de hoje"
        />
        <StatTile
          label="Exposição a multa"
          accent={<AlertOctagon className="h-3.5 w-3.5" style={{ color: 'var(--status-critical)' }} aria-hidden />}
          value={fmtBRL(exposicao)}
          sub={`${fmtInt(t.vencidas)} vencidas × ${fmtBRL(premissas.multaPorNip)} (premissa)`}
        />
        <StatTile
          label="Prontas para resolver"
          accent={<CheckCircle2 className="h-3.5 w-3.5" style={{ color: 'var(--status-good)' }} aria-hidden />}
          value={fmtPct(t.abertas ? t.prontas / t.abertas : 0)}
          sub={`${fmtInt(t.prontas)} com VPP inferida e confiança ≥ 80%`}
        />
        <StatTile
          label="Horas que o copiloto devolve"
          accent={<Clock className="h-3.5 w-3.5" style={{ color: 'var(--viz-series-1)' }} aria-hidden />}
          value={`${Math.round(horasPotencial)} h`}
          sub={`no backlog atual · ${horasRealizadas.toLocaleString('pt-BR', { maximumFractionDigits: 1 })} h já realizadas`}
        />
      </div>

      <div className="grid lg:grid-cols-[1.15fr_1fr] gap-4">
        {/* Next best actions */}
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-base">O que fazer agora</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            <Acao
              icon={<AlertTriangle className="h-4 w-4" style={{ color: 'var(--status-serious)' }} aria-hidden />}
              titulo={`${fmtInt(t.criticas)} NIPs vencem em até 1 dia`}
              texto="A VPP já está inferida e o parecer rascunhado: é revisar e enviar."
              cta="Abrir fila crítica"
              onClick={() => goFila('CRITICA')}
            />
            <Acao
              icon={<AlertOctagon className="h-4 w-4" style={{ color: 'var(--status-critical)' }} aria-hidden />}
              titulo={`${fmtInt(t.vencidas)} NIPs vencidas · ${fmtBRL(exposicao)} em exposição`}
              texto="Backlog fora do prazo. Comece pelos temas com mais vencidas."
              cta="Atacar o backlog"
              onClick={() => goFila('VENCIDA')}
            />
            <Acao
              icon={<Radar className="h-4 w-4" style={{ color: 'var(--viz-series-1)' }} aria-hidden />}
              titulo={`${fmtInt(data.radar.alto)} beneficiários em risco alto de abrir NIP`}
              texto={`Mais ${fmtInt(data.radar.medio)} em risco médio. ${fmtInt(data.radar.acionados)} já acionados pelo call center.`}
              cta="Abrir radar"
              onClick={() => navigate('/radar')}
            />
            <Acao
              icon={<Sparkles className="h-4 w-4" style={{ color: 'var(--viz-series-1)' }} aria-hidden />}
              titulo="Onde está o dinheiro em risco?"
              texto="Pergunte ao agente qual a exposição a multa por tema."
              cta="Perguntar"
              onClick={() => agent.ask(PERGUNTAS[0])}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Backlog aberto por prazo ANS</CardTitle>
            <p className="text-xs text-muted-foreground">Clique numa faixa para abrir a fila filtrada.</p>
          </CardHeader>
          <CardContent>
            <SlaRows rows={data.sla} onSelect={goFila} />
          </CardContent>
        </Card>
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">NIPs recebidas por semana</CardTitle>
            <p className="text-xs text-muted-foreground">Últimas 12 semanas. O azul é o que ainda espera resposta.</p>
          </CardHeader>
          <CardContent><WeeklyColumns data={data.weekly} /></CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Temas com mais NIPs em aberto</CardTitle>
            <p className="text-xs text-muted-foreground">Tratamento ou cirurgia da guia associada pelo agente.</p>
          </CardHeader>
          <CardContent>
            <BarList
              rows={data.temas.map((r) => ({ label: r.tema, value: r.abertas, note: `${r.vencidas} vencidas` }))}
              onSelect={(tema) => agent.ask(`Quais NIPs em aberto são do tema "${tema}" e qual o prazo de cada uma?`)}
            />
          </CardContent>
        </Card>
      </div>

      <div className="grid lg:grid-cols-[1fr_1.15fr] gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Premissas do cálculo</CardTitle>
            <p className="text-xs text-muted-foreground">Valores ilustrativos. Ajuste para a realidade da operadora e os números acima recalculam.</p>
          </CardHeader>
          <CardContent className="grid sm:grid-cols-2 gap-3">
            <label className="text-sm text-foreground space-y-1">
              <span className="text-xs text-muted-foreground">Multa média por NIP fora do prazo (R$)</span>
              <Input inputMode="numeric" value={premissas.multaPorNip.toLocaleString('pt-BR')} onChange={(e) => updatePremissa('multaPorNip', e.target.value)} />
            </label>
            <label className="text-sm text-foreground space-y-1">
              <span className="text-xs text-muted-foreground">Minutos economizados por NIP (25 manual − 8 copiloto)</span>
              <Input inputMode="numeric" value={String(premissas.minutosPorNip)} onChange={(e) => updatePremissa('minutosPorNip', e.target.value)} />
            </label>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-base">Atividade recente</CardTitle></CardHeader>
          <CardContent>
            {activity.length === 0 ? (
              <p className="text-sm text-muted-foreground">Nenhuma decisão registrada ainda. Aprove um parecer na fila ou acione um beneficiário no radar.</p>
            ) : (
              <ul className="divide-y">
                {activity.map((a) => (
                  <li key={`${a.tipo}-${a.alvo}-${a.criado_em}`} className="py-2 flex items-center justify-between gap-3 text-sm">
                    <span className="truncate text-foreground">
                      <span className="font-mono text-xs text-muted-foreground mr-2">{a.alvo}</span>
                      {a.tipo === 'NIP' ? DECISAO_LABEL[a.acao as Decisao] ?? a.acao : ACAO_LABEL[a.acao as AcaoRetencao] ?? a.acao}
                    </span>
                    <span className="shrink-0 text-xs text-muted-foreground">
                      {new Date(a.criado_em).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Acao({ icon, titulo, texto, cta, onClick }: { icon: ReactNode; titulo: string; texto: string; cta: string; onClick: () => void }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border px-3 py-2.5">
      <div className="shrink-0">{icon}</div>
      <div className="min-w-0 flex-1">
        <div className="text-sm font-medium text-foreground">{titulo}</div>
        <div className="text-xs text-muted-foreground">{texto}</div>
      </div>
      <Button size="sm" variant="ghost" onClick={onClick} className="shrink-0">
        {cta} <ArrowRight className="h-3.5 w-3.5" />
      </Button>
    </div>
  );
}
