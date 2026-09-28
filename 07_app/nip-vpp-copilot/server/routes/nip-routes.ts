// NIP-VPP copilot routes. Reads the operational serving table (nip_vpp.nip_serving)
// and writes analyst decisions to nip_vpp.analyst_feedback — both in Lakebase Postgres,
// populated by the reverse-ETL loader (05_lakebase/load_lakebase.py).
import { z } from 'zod';
import { Application } from 'express';

interface AppKitWithLakebase {
  lakebase: {
    query(text: string, params?: unknown[]): Promise<{ rows: Record<string, unknown>[] }>;
  };
  server: { extend(fn: (app: Application) => void): void };
}

const FeedbackBody = z.object({
  decisao: z.enum(['APROVADO', 'AJUSTADO', 'REJEITADO']),
  parecer_final: z.string().optional(),
  analista: z.string().optional(),
});

export async function setupNipRoutes(appkit: AppKitWithLakebase) {
  // Ensure the write-back table exists (the SP owns it once granted); serving table is read-only.
  try {
    await appkit.lakebase.query('SELECT 1 FROM nip_vpp.nip_serving LIMIT 1');
    console.log('[nip] nip_vpp.nip_serving reachable');
  } catch (err) {
    console.warn('[nip] cannot read nip_vpp.nip_serving — grant the app SP USAGE/SELECT on schema nip_vpp:',
      (err as Error).message);
  }

  appkit.server.extend((app) => {
    // KPI header: counts by SLA + automation rate + avg confidence
    app.get('/api/kpis', async (_req, res) => {
      try {
        const sla = await appkit.lakebase.query(
          'SELECT sla_status, count(*)::int AS n FROM nip_vpp.nip_serving GROUP BY sla_status');
        const agg = await appkit.lakebase.query(
          `SELECT count(*)::int AS total,
                  sum(CASE WHEN resolvida THEN 0 ELSE 1 END)::int AS abertas,
                  sum(CASE WHEN auto_resolvavel AND NOT resolvida THEN 1 ELSE 0 END)::int AS auto_abertas,
                  round(avg(confidence)::numeric, 3) AS conf_media
           FROM nip_vpp.nip_serving`);
        res.json({ sla: sla.rows, agg: agg.rows[0] });
      } catch (err) {
        console.error('kpis failed:', err);
        res.status(500).json({ error: 'Falha ao carregar KPIs' });
      }
    });

    // NIP queue (optionally filtered by SLA status); most urgent unresolved first
    app.get('/api/nips', async (req, res) => {
      try {
        const sla = typeof req.query.sla === 'string' ? req.query.sla : null;
        const params: unknown[] = [];
        let where = '';
        if (sla && sla !== 'TODAS') { params.push(sla); where = 'WHERE sla_status = $1'; }
        const result = await appkit.lakebase.query(
          `SELECT nip_id, beneficiario_nome, nome_plano, sla_status, dias_para_prazo,
                  reclamacao_texto, matched_manifestacao_id, matched_tipo, confidence,
                  auto_resolvavel, justificativa, parecer_sugerido, vpp_citada, resolvida
           FROM nip_vpp.nip_serving
           ${where}
           ORDER BY resolvida ASC, dias_para_prazo ASC
           LIMIT 200`, params);
        res.json(result.rows);
      } catch (err) {
        console.error('nips failed:', err);
        res.status(500).json({ error: 'Falha ao carregar NIPs' });
      }
    });

    // Record an analyst decision (write-back)
    app.post('/api/nips/:id/feedback', async (req, res) => {
      try {
        const parsed = FeedbackBody.safeParse(req.body);
        if (!parsed.success) { res.status(400).json({ error: 'decisao inválida' }); return; }
        const { decisao, parecer_final, analista } = parsed.data;
        const result = await appkit.lakebase.query(
          `INSERT INTO nip_vpp.analyst_feedback (nip_id, decisao, parecer_final, analista)
           VALUES ($1, $2, $3, $4)
           RETURNING feedback_id, nip_id, decisao, criado_em`,
          [req.params.id, decisao, parecer_final ?? null, analista ?? 'analista_demo']);
        res.status(201).json(result.rows[0]);
      } catch (err) {
        console.error('feedback failed:', err);
        res.status(500).json({ error: 'Falha ao registrar decisão' });
      }
    });

    // Recent analyst decisions (audit trail)
    app.get('/api/feedback', async (_req, res) => {
      try {
        const result = await appkit.lakebase.query(
          `SELECT feedback_id, nip_id, decisao, analista, criado_em
           FROM nip_vpp.analyst_feedback ORDER BY criado_em DESC LIMIT 20`);
        res.json(result.rows);
      } catch (err) {
        res.status(500).json({ error: 'Falha ao carregar histórico' });
      }
    });
  });
}
