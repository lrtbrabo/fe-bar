/* Typed contracts for the server routes in server/routes/nip-routes.ts + small helpers. */

export type SlaStatus = 'VENCIDA' | 'CRITICA' | 'ATENCAO' | 'NO_PRAZO' | 'RESOLVIDA';
export type Decisao = 'APROVADO' | 'AJUSTADO' | 'REJEITADO';
export type AcaoRetencao = 'LIGAR' | 'PRIORIZAR_AUTORIZACAO' | 'OUVIDORIA_PROATIVA';

export interface Overview {
  totals: { total: number; abertas: number; prontas: number; vencidas: number; criticas: number; conf_media: number };
  sla: { sla_status: SlaStatus; n: number }[];
  weekly: { semana: string; abertas: number; resolvidas: number }[];
  temas: { tema: string; abertas: number; vencidas: number }[];
  decisions: { decisoes: number; resolvidas: number };
  radar: { alto: number; medio: number; acionados: number };
  asOf: string | null;
}

export interface NipListItem {
  nip_id: string;
  beneficiario_nome: string | null;
  nome_plano: string | null;
  sla_status: SlaStatus;
  dias_para_prazo: number | null;
  reclamacao_texto: string | null;
  tema: string;
  categoria_reclamacao: string | null;
  confidence: number | null;
  auto_resolvavel: boolean | null;
  resolvida: boolean;
  ultima_decisao: Decisao | null;
}

export interface NipDetail {
  nip: NipListItem & {
    beneficiario_id: string;
    plano_segmentacao: string | null;
    data_criacao: string;
    vpp_citada: string | null;
    matched_manifestacao_id: string | null;
    matched_tipo: string | null;
    matched_vpp_numero: string | null;
    justificativa: string | null;
    parecer_sugerido: string | null;
  };
  candidatas: {
    manifestacao_id: string; tipo: string; vpp_numero: string; data: string; status: string;
    procedimentos_texto: string; dias_antes_nip: number; dentro_janela: boolean; escolhida: boolean; motivo: string;
  }[];
  rol: {
    codigo_tuss: string; descricao_procedimento: string; tipo_item: string; status_item: string;
    no_rol: boolean | null; segmentacao_cobertura: string | null; plano_segmentacao: string | null;
    segmentacao_cobre: boolean | null; dut_texto: string | null;
  }[];
  timeline: { quando: string; tipo: 'CONTATO' | 'GUIA' | 'NIP'; titulo: string; detalhe: string | null; sentimento: number | null }[];
  feedback: { decisao: Decisao; quando: string }[];
}

export interface RadarItem {
  beneficiario_id: string; nome: string | null; uf: string | null; nome_plano: string | null;
  score: number; faixa_risco: 'ALTO' | 'MEDIO' | 'BAIXO'; motivos: string;
  n_interacoes: number; avg_sentimento: number; total_protocolos: number; dias_desde_ultima: number;
  ultima_acao: AcaoRetencao | null; acionado_em: string | null;
}

export interface Activity { criado_em: string; tipo: 'NIP' | 'RETENCAO'; alvo: string; acao: string; analista: string | null }

export async function getJSON<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

export async function postJSON<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

const int = new Intl.NumberFormat('pt-BR');
export const fmtInt = (n: number | null | undefined) => (n == null ? '—' : int.format(n));
export const fmtPct = (x: number | null | undefined) => (x == null ? '—' : `${Math.round(x * 100)}%`);

export function fmtBRL(v: number): string {
  if (v >= 1_000_000) return `R$ ${(v / 1_000_000).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} mi`;
  if (v >= 1_000) return `R$ ${(v / 1_000).toLocaleString('pt-BR', { maximumFractionDigits: 0 })} mil`;
  return `R$ ${int.format(v)}`;
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  const [y, m, d] = iso.slice(0, 10).split('-');
  return `${d}/${m}/${y}`;
}

export const fmtDayMonth = (iso: string) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;

export function prazoLabel(n: { resolvida: boolean; dias_para_prazo: number | null }): string {
  if (n.resolvida) return 'resolvida';
  const d = n.dias_para_prazo ?? 0;
  if (d < 0) return `vencida há ${-d} dia${d === -1 ? '' : 's'}`;
  if (d === 0) return 'vence hoje';
  return `vence em ${d} dia${d === 1 ? '' : 's'}`;
}

export const ACAO_LABEL: Record<AcaoRetencao, string> = {
  LIGAR: 'Ligar para o beneficiário',
  PRIORIZAR_AUTORIZACAO: 'Priorizar autorização',
  OUVIDORIA_PROATIVA: 'Ouvidoria proativa',
};

export const DECISAO_LABEL: Record<Decisao, string> = {
  APROVADO: 'Parecer aprovado',
  AJUSTADO: 'Parecer ajustado',
  REJEITADO: 'Associação rejeitada',
};

/* Premissas (illustrative, editable on the Painel; persisted per browser). */
export interface Premissas { multaPorNip: number; minutosPorNip: number }
const KEY = 'nip-copilot-premissas';
export const PREMISSAS_PADRAO: Premissas = { multaPorNip: 30000, minutosPorNip: 17 };
export function loadPremissas(): Premissas {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? { ...PREMISSAS_PADRAO, ...(JSON.parse(raw) as Partial<Premissas>) } : PREMISSAS_PADRAO;
  } catch {
    return PREMISSAS_PADRAO;
  }
}
export function savePremissas(p: Premissas) {
  localStorage.setItem(KEY, JSON.stringify(p));
}
