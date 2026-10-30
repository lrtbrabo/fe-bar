// NIP-VPP copilot routes. Reads the operational serving tables in Lakebase Postgres
// (schema nip_vpp, loaded by 05_lakebase/load_lakebase.py) and writes analyst and
// call-center decisions back to nip_vpp.analyst_feedback / nip_vpp.retention_actions.
import { z } from 'zod';
import { Application, Response } from 'express';

interface AppKitWithLakebase {
  lakebase: {
    query(text: string, params?: unknown[]): Promise<{ rows: Record<string, unknown>[] }>;
  };
  server: { extend(fn: (app: Application) => void): void };
}

const FeedbackBody = z.object({
  decisao: z.enum(['APROVADO', 'AJUSTADO', 'REJEITADO']),
  parecer_final: z.string().optional(),
});

const RetentionBody = z.object({
  acao: z.enum(['LIGAR', 'PRIORIZAR_AUTORIZACAO', 'OUVIDORIA_PROATIVA']),
});

function fail(res: Response, label: string, err: unknown) {
  console.error(`${label} failed:`, err);
  res.status(500).json({ error: `Falha ao carregar ${label}` });
}

export async function setupNipRoutes(appkit: AppKitWithLakebase) {
  const q = (text: string, params?: unknown[]) => appkit.lakebase.query(text, params).then((r) => r.rows);

  try {
    await q('SELECT 1 FROM nip_vpp.nip_serving LIMIT 1');
    console.log('[nip] nip_vpp schema reachable');
  } catch (err) {
    console.warn('[nip] cannot read nip_vpp — run 05_lakebase/load_lakebase.py (it grants the app SP):',
      (err as Error).message);
  }

  appkit.server.extend((app) => {
    // Painel: everything the overview needs in one round-trip.
    app.get('/api/overview', async (_req, res) => {
      try {
        const [totals, sla, weekly, temas, decisions, radar, asOf] = await Promise.all([
          q(`SELECT count(*)::int AS total,
                    count(*) FILTER (WHERE NOT resolvida)::int AS abertas,
                    count(*) FILTER (WHERE NOT resolvida AND auto_resolvavel)::int AS prontas,
                    count(*) FILTER (WHERE NOT resolvida AND sla_status = 'VENCIDA')::int AS vencidas,
                    count(*) FILTER (WHERE sla_status = 'CRITICA')::int AS criticas,
                    round(avg(confidence) FILTER (WHERE NOT resolvida)::numeric, 3)::float AS conf_media
             FROM nip_vpp.nip_serving`),
          q(`SELECT sla_status, count(*)::int AS n FROM nip_vpp.nip_serving
             WHERE NOT resolvida GROUP BY sla_status`),
          q(`SELECT to_char(date_trunc('week', data_criacao), 'YYYY-MM-DD') AS semana,
                    count(*) FILTER (WHERE NOT resolvida)::int AS abertas,
                    count(*) FILTER (WHERE resolvida)::int AS resolvidas
             FROM nip_vpp.nip_serving
             WHERE data_criacao >= (SELECT max(data_criacao) FROM nip_vpp.nip_serving) - interval '12 weeks'
             GROUP BY 1 ORDER BY 1`),
          q(`SELECT coalesce(nullif(tema, ''), 'sem guia associada') AS tema,
                    count(*)::int AS abertas,
                    count(*) FILTER (WHERE sla_status = 'VENCIDA')::int AS vencidas
             FROM nip_vpp.nip_serving WHERE NOT resolvida
             GROUP BY 1 ORDER BY abertas DESC, tema`),
          q(`SELECT count(*)::int AS decisoes,
                    count(*) FILTER (WHERE decisao IN ('APROVADO', 'AJUSTADO'))::int AS resolvidas
             FROM nip_vpp.analyst_feedback`),
          q(`SELECT count(*) FILTER (WHERE faixa_risco = 'ALTO')::int AS alto,
                    count(*) FILTER (WHERE faixa_risco = 'MEDIO')::int AS medio,
                    (SELECT count(DISTINCT beneficiario_id)::int FROM nip_vpp.retention_actions) AS acionados
             FROM nip_vpp.propensity WHERE abriu_nip = 0`),
          q(`SELECT to_char(max(data_criacao), 'YYYY-MM-DD') AS as_of FROM nip_vpp.nip_serving`),
        ]);
        res.json({ totals: totals[0], sla, weekly, temas, decisions: decisions[0], radar: radar[0],
          asOf: asOf[0]?.as_of ?? null });
      } catch (err) {
        fail(res, 'painel', err);
      }
    });

    // Fila: list (optionally by SLA), most urgent unresolved first.
    app.get('/api/nips', async (req, res) => {
      try {
        const sla = typeof req.query.sla === 'string' ? req.query.sla : 'ATIVAS';
        const params: unknown[] = [];
        let where = 'WHERE NOT s.resolvida';
        if (sla === 'TODAS') where = '';
        else if (sla !== 'ATIVAS') { params.push(sla); where = 'WHERE s.sla_status = $1'; }
        const rows = await q(
          `SELECT s.nip_id, s.beneficiario_nome, s.nome_plano, s.sla_status, s.dias_para_prazo,
                  s.reclamacao_texto, coalesce(nullif(s.tema, ''), 'sem guia associada') AS tema,
                  s.categoria_reclamacao, s.confidence, s.auto_resolvavel, s.resolvida,
                  f.decisao AS ultima_decisao
           FROM nip_vpp.nip_serving s
           LEFT JOIN LATERAL (SELECT decisao FROM nip_vpp.analyst_feedback a
                              WHERE a.nip_id = s.nip_id ORDER BY criado_em DESC LIMIT 1) f ON true
           ${where}
           ORDER BY s.resolvida ASC, s.dias_para_prazo ASC, s.nip_id
           LIMIT 250`, params);
        res.json(rows);
      } catch (err) {
        fail(res, 'fila', err);
      }
    });

    // Detalhe: the NIP plus the explainability, regulatory check and beneficiary timeline.
    app.get('/api/nips/:id', async (req, res) => {
      try {
        const id = req.params.id;
        const nip = (await q(
          `SELECT nip_id, beneficiario_id, beneficiario_nome, nome_plano, plano_segmentacao, reclamacao_texto,
                  to_char(data_criacao, 'YYYY-MM-DD') AS data_criacao, dias_para_prazo, sla_status, resolvida,
                  vpp_citada, matched_manifestacao_id, matched_tipo, matched_vpp_numero, confidence,
                  auto_resolvavel, justificativa, parecer_sugerido,
                  coalesce(nullif(tema, ''), 'sem guia associada') AS tema, categoria_reclamacao
           FROM nip_vpp.nip_serving WHERE nip_id = $1`, [id]))[0];
        if (!nip) { res.status(404).json({ error: 'NIP não encontrada' }); return; }
        const [candidatas, rol, timeline, feedback] = await Promise.all([
          q(`SELECT manifestacao_id, tipo, vpp_numero, to_char(data_criacao, 'YYYY-MM-DD') AS data,
                    status, procedimentos_texto, dias_antes_nip, dentro_janela, escolhida, motivo
             FROM nip_vpp.nip_candidates WHERE nip_id = $1
             ORDER BY escolhida DESC, dentro_janela DESC, data_criacao DESC`, [id]),
          q(`SELECT codigo_tuss, descricao_procedimento, tipo_item, status_item, no_rol,
                    segmentacao_cobertura, plano_segmentacao, segmentacao_cobre, dut_texto
             FROM nip_vpp.nip_rol_check WHERE nip_id = $1 ORDER BY status_item DESC, descricao_procedimento`, [id]),
          q(`SELECT to_char(t.quando, 'YYYY-MM-DD') AS quando, t.tipo, t.titulo, t.detalhe, t.sentimento FROM (
               SELECT data_interacao AS quando, 'CONTATO' AS tipo,
                      initcap(lower(canal)) || ' · ' || initcap(lower(assunto)) AS titulo,
                      transcricao AS detalhe, sentimento_score AS sentimento
               FROM nip_vpp.callcenter WHERE beneficiario_id = $2
               UNION ALL
               SELECT data_criacao, 'GUIA', 'Guia ' || vpp_numero || CASE WHEN tipo = 'VPP_FILHA' THEN ' (item)' ELSE '' END,
                      procedimentos_texto, NULL
               FROM nip_vpp.nip_candidates WHERE nip_id = $1
               UNION ALL
               SELECT data_criacao, 'NIP', 'NIP aberta na ANS', NULL, NULL
               FROM nip_vpp.nip_serving WHERE nip_id = $1
             ) t ORDER BY t.quando`, [id, nip.beneficiario_id]),
          q(`SELECT decisao, to_char(criado_em AT TIME ZONE 'UTC' AT TIME ZONE 'America/Sao_Paulo', 'DD/MM HH24:MI') AS quando
             FROM nip_vpp.analyst_feedback WHERE nip_id = $1 ORDER BY criado_em DESC LIMIT 5`, [id]),
        ]);
        res.json({ nip, candidatas, rol, timeline, feedback });
      } catch (err) {
        fail(res, 'detalhe da NIP', err);
      }
    });

    app.post('/api/nips/:id/feedback', async (req, res) => {
      try {
        const parsed = FeedbackBody.safeParse(req.body);
        if (!parsed.success) { res.status(400).json({ error: 'decisão inválida' }); return; }
        const analista = req.header('x-forwarded-email') ?? 'analista';
        const rows = await q(
          `INSERT INTO nip_vpp.analyst_feedback (nip_id, decisao, parecer_final, analista)
           VALUES ($1, $2, $3, $4) RETURNING feedback_id, nip_id, decisao, criado_em`,
          [req.params.id, parsed.data.decisao, parsed.data.parecer_final ?? null, analista]);
        res.status(201).json(rows[0]);
      } catch (err) {
        fail(res, 'registro da decisão', err);
      }
    });

    // Radar: at-risk beneficiaries without a NIP, with their latest retention action.
    app.get('/api/radar', async (req, res) => {
      try {
        const faixa = typeof req.query.faixa === 'string' ? req.query.faixa : 'RISCO';
        const filter = faixa === 'ALTO' ? "p.faixa_risco = 'ALTO'" : "p.faixa_risco IN ('ALTO', 'MEDIO')";
        const rows = await q(
          `SELECT p.beneficiario_id, p.nome, p.uf, p.nome_plano, p.score, p.faixa_risco, p.motivos,
                  p.n_interacoes, p.avg_sentimento, p.total_protocolos, p.dias_desde_ultima,
                  a.acao AS ultima_acao, to_char(a.criado_em AT TIME ZONE 'UTC' AT TIME ZONE 'America/Sao_Paulo', 'DD/MM HH24:MI') AS acionado_em
           FROM nip_vpp.propensity p
           LEFT JOIN LATERAL (SELECT acao, criado_em FROM nip_vpp.retention_actions r
                              WHERE r.beneficiario_id = p.beneficiario_id
                              ORDER BY criado_em DESC LIMIT 1) a ON true
           WHERE p.abriu_nip = 0 AND ${filter}
           ORDER BY p.score DESC`);
        res.json(rows);
      } catch (err) {
        fail(res, 'radar', err);
      }
    });

    app.post('/api/radar/:id/acao', async (req, res) => {
      try {
        const parsed = RetentionBody.safeParse(req.body);
        if (!parsed.success) { res.status(400).json({ error: 'ação inválida' }); return; }
        const analista = req.header('x-forwarded-email') ?? 'analista';
        const rows = await q(
          `INSERT INTO nip_vpp.retention_actions (beneficiario_id, acao, analista)
           VALUES ($1, $2, $3) RETURNING acao_id, beneficiario_id, acao, criado_em`,
          [req.params.id, parsed.data.acao, analista]);
        res.status(201).json(rows[0]);
      } catch (err) {
        fail(res, 'registro da ação', err);
      }
    });

    // Atividade: latest decisions and retention actions (audit trail for the Painel).
    app.get('/api/activity', async (_req, res) => {
      try {
        const rows = await q(
          `SELECT * FROM (
             SELECT criado_em AT TIME ZONE 'UTC' AS criado_em, 'NIP' AS tipo, nip_id AS alvo, decisao AS acao, analista FROM nip_vpp.analyst_feedback
             UNION ALL
             SELECT criado_em AT TIME ZONE 'UTC', 'RETENCAO', beneficiario_id, acao, analista FROM nip_vpp.retention_actions
           ) t ORDER BY criado_em DESC LIMIT 8`);
        res.json(rows);
      } catch (err) {
        fail(res, 'atividade', err);
      }
    });
  });
}
