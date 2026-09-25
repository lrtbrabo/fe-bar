"""
Synthetic data generator for the NIP <-> VPP automation build (FE Bar).

Produces "source-system exports" for a fictional Brazilian health insurer, to be
landed in a Unity Catalog Volume and ingested by Lakeflow (Auto Loader).

NOTHING here is real customer data. Names, CPFs, plans, TUSS codes, procedures,
complaints and call-center transcripts are all synthesized. Any resemblance to
SulAmérica or its beneficiaries is coincidental and unintended.

Domain (regulatory):
  - A beneficiary unhappy with a denied procedure escalates to the ANS regulator
    by opening a NIP (Notificação de Intermediação Preliminar) -> 5-day deadline,
    fines on delay.
  - To answer, an analyst must find the VPP (Validação de Procedimento Prévio):
    the prior-authorization guide listing the procedures requested for a treatment.
  - Everything is a "manifestação": NIP, VPP (parent) and VPP child items all live
    in ONE manifestações table.

Hard cases planted on purpose (this is what makes the matcher non-trivial):
  1. pai vs filha: complaints about MATERIAL/MEDICAMENTO/OPME must resolve to the
     CHILD manifestação, not the parent guide.
  2. resolved-case status trap: for resolved NIPs the denied line item status is
     flipped to APROVADO and a parecer is filled, so a naive matcher keying on
     status=NEGADO fails -> must detect resolution and ignore status.
  3. multiple-VPP ambiguity + 65-day window: beneficiaries with several VPPs, some
     older than 65 days (must be excluded), sharing overlapping procedures.

Outputs (under 01_synthetic_data/output/):
  raw/                      -> bulk source exports (gitignored, uploaded to Volume)
    dim_plano.csv
    dim_beneficiario.csv
    ref_rol_ans.csv
    manifestacoes/part-*.csv          (VPP parent, VPP child, NIP -- one table)
    procedimentos_solicitados/part-*.csv
    interacoes_callcenter/part-*.jsonl (semi-structured, for the ML model)
    ground_truth/nip_vpp_labels.csv    (evaluation oracle -- not "prod" data)
  preview/                  -> small samples + summary (committed as text evidence)

Reproducible: fixed seed. Deterministic given the same parameters.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
from datetime import datetime, timedelta
from pathlib import Path

from faker import Faker

# --------------------------------------------------------------------------- #
# Parameters
# --------------------------------------------------------------------------- #
SEED = 42
N_BENEFICIARIOS = 1500
NIP_RATE = 0.22            # fraction of beneficiaries that escalate to a NIP
RESOLVED_NIP_RATE = 0.45   # fraction of NIPs that are historical/resolved (status trap)
REF_DATE = datetime(2026, 9, 24)  # "today" for the dataset (matches the recording date)
PART_FILES = 4             # split fact tables into N parts (simulate incremental arrival)

fake = Faker("pt_BR")
Faker.seed(SEED)
random.seed(SEED)

OUT = Path(__file__).resolve().parents[1] / "output"
RAW = OUT / "raw"
PREVIEW = OUT / "preview"

# --------------------------------------------------------------------------- #
# Reference: plans
# --------------------------------------------------------------------------- #
PLANOS = [
    # plano_id, nome, segmentacao, abrangencia, coparticipacao
    ("PL-AMB-HOSP-NAC", "Saúde Total Nacional",      "AMBULATORIAL+HOSPITALAR", "NACIONAL",  False),
    ("PL-HOSP-EST",     "Hospitalar Estadual",       "HOSPITALAR",              "ESTADUAL",  True),
    ("PL-AMB-NAC",      "Ambulatorial Nacional",     "AMBULATORIAL",            "NACIONAL",  True),
    ("PL-REF-NAC",      "Referência Premium",        "REFERENCIA",              "NACIONAL",  False),
    ("PL-HOSP-NAC-COP", "Hospitalar Nacional Copart","HOSPITALAR",              "NACIONAL",  True),
]

# --------------------------------------------------------------------------- #
# Reference: ANS rol de procedimentos (synthetic subset).
# TUSS codes are synthetic 8-digit codes -- NOT the real ANS/TUSS terminology.
# Each entry: codigo_tuss, nome_procedimento, categoria, tipo_item,
#             segmentacao_cobertura, obrigatorio_rol, dut_texto, layman (colloquial term)
# categoria in {CONSULTA, EXAME, CIRURGIA, TERAPIA, OPME, MEDICAMENTO, INTERNACAO}
# tipo_item in {PROCEDIMENTO, MATERIAL, MEDICAMENTO, OPME}  (line-item nature)
# --------------------------------------------------------------------------- #
ROL = [
    # --- consultas / exames genéricos ---
    ("40010012", "Consulta em consultório (ortopedia)",           "CONSULTA",    "PROCEDIMENTO", "AMBULATORIAL",            True,  "Cobertura sem carência após 24h para urgência.", "consulta com o ortopedista"),
    ("40010020", "Consulta em consultório (oncologia clínica)",   "CONSULTA",    "PROCEDIMENTO", "AMBULATORIAL",            True,  "Cobertura obrigatória.", "consulta com o oncologista"),
    ("40010039", "Consulta em consultório (cardiologia)",         "CONSULTA",    "PROCEDIMENTO", "AMBULATORIAL",            True,  "Cobertura obrigatória.", "consulta com o cardiologista"),
    ("40808133", "Ressonância magnética de joelho",               "EXAME",       "PROCEDIMENTO", "AMBULATORIAL",            True,  "Coberto com pedido médico e DUT específica.", "ressonância do joelho"),
    ("40801012", "Ultrassonografia de abdome total",              "EXAME",       "PROCEDIMENTO", "AMBULATORIAL",            True,  "Cobertura obrigatória.", "ultrassom da barriga"),
    ("40802019", "Ultrassonografia obstétrica",                   "EXAME",       "PROCEDIMENTO", "AMBULATORIAL",            True,  "Cobertura obrigatória no pré-natal.", "ultrassom do bebê"),
    ("40901025", "Endoscopia digestiva alta",                     "EXAME",       "PROCEDIMENTO", "AMBULATORIAL",            True,  "Coberto com indicação clínica.", "endoscopia"),
    ("40501012", "Cateterismo cardíaco",                          "EXAME",       "PROCEDIMENTO", "HOSPITALAR",              True,  "Coberto com relatório médico.", "cateterismo"),
    # --- cirurgias ---
    ("30715016", "Artroplastia total de joelho",                  "CIRURGIA",    "PROCEDIMENTO", "HOSPITALAR",              True,  "Coberto com laudo e DUT de artroplastia.", "cirurgia de prótese no joelho"),
    ("30715024", "Artroscopia de joelho",                         "CIRURGIA",    "PROCEDIMENTO", "HOSPITALAR",              True,  "Coberto com indicação ortopédica.", "artroscopia do joelho"),
    ("31003010", "Colecistectomia videolaparoscópica",            "CIRURGIA",    "PROCEDIMENTO", "HOSPITALAR",              True,  "Coberto com laudo.", "cirurgia da vesícula"),
    ("30912016", "Angioplastia coronariana",                      "CIRURGIA",    "PROCEDIMENTO", "HOSPITALAR",              True,  "Coberto com relatório e DUT cardiológica.", "colocação de stent no coração"),
    ("31309054", "Gastroplastia (cirurgia bariátrica)",           "CIRURGIA",    "PROCEDIMENTO", "HOSPITALAR",              True,  "Coberto com DUT de obesidade mórbida (IMC e comorbidades).", "cirurgia de redução de estômago"),
    ("31601010", "Parto cesariano",                               "CIRURGIA",    "PROCEDIMENTO", "HOSPITALAR",              True,  "Cobertura obstétrica obrigatória.", "cesárea"),
    ("31601029", "Parto normal (assistência)",                    "CIRURGIA",    "PROCEDIMENTO", "HOSPITALAR",              True,  "Cobertura obstétrica obrigatória.", "parto normal"),
    # --- OPME (órteses, próteses, materiais especiais) ---
    ("70712010", "Prótese total de joelho (OPME)",                "OPME",        "OPME",         "HOSPITALAR",              True,  "OPME sujeita a análise técnica e três orçamentos.", "prótese do joelho"),
    ("70712028", "Stent farmacológico (OPME)",                    "OPME",        "OPME",         "HOSPITALAR",              True,  "OPME sujeita a análise técnica.", "stent do coração"),
    ("70200011", "Kit de materiais para videolaparoscopia (OPME)","OPME",        "MATERIAL",     "HOSPITALAR",              True,  "Material vinculado ao ato cirúrgico.", "material da cirurgia por vídeo"),
    ("70712036", "Banda gástrica ajustável (OPME)",               "OPME",        "OPME",         "HOSPITALAR",              True,  "OPME sujeita a DUT bariátrica.", "banda gástrica"),
    # --- medicamentos ---
    ("90300010", "Quimioterapia antineoplásica (medicamento)",    "MEDICAMENTO", "MEDICAMENTO",  "AMBULATORIAL+HOSPITALAR", True,  "Antineoplásico oral/venoso com DUT oncológica.", "remédio da quimioterapia"),
    ("90300028", "Antiemético de alto custo (medicamento)",       "MEDICAMENTO", "MEDICAMENTO",  "AMBULATORIAL",            False, "Cobertura condicionada à DUT.", "remédio de enjoo da quimio"),
    ("90300036", "Imunobiológico (medicamento)",                  "MEDICAMENTO", "MEDICAMENTO",  "AMBULATORIAL",            True,  "Imunobiológico com DUT específica.", "medicação imunobiológica"),
    # --- terapias / internação ---
    ("50000470", "Sessão de fisioterapia",                        "TERAPIA",     "PROCEDIMENTO", "AMBULATORIAL",            True,  "Coberto por número de sessões conforme DUT.", "fisioterapia"),
    ("50000560", "Sessão de hemodiálise",                         "TERAPIA",     "PROCEDIMENTO", "AMBULATORIAL+HOSPITALAR", True,  "Cobertura obrigatória para doença renal crônica.", "hemodiálise"),
    ("60000015", "Diária de internação hospitalar",               "INTERNACAO",  "PROCEDIMENTO", "HOSPITALAR",              True,  "Sem limite de diárias conforme lei.", "internação"),
    ("60000023", "Diária de UTI",                                 "INTERNACAO",  "PROCEDIMENTO", "HOSPITALAR",              True,  "Sem limite de diárias conforme lei.", "UTI"),
]
ROL_BY_TUSS = {r[0]: r for r in ROL}

# --------------------------------------------------------------------------- #
# Clinical episodes -> ordered list of TUSS items that make up the VPP guide.
# The `filha_tuss` (if set) is the MATERIAL/MEDICAMENTO/OPME item that becomes a
# separate CHILD manifestação (pai/filha rule).
# --------------------------------------------------------------------------- #
EPISODIOS = [
    dict(nome="ARTROPLASTIA_JOELHO", layman="cirurgia de prótese no joelho",
         itens=["40010012", "40808133", "60000015", "30715016", "50000470"],
         filha_tuss="70712010"),  # prótese de joelho (OPME) -> filha
    dict(nome="ONCOLOGIA_QUIMIO", layman="tratamento de quimioterapia",
         itens=["40010020", "60000015"],
         filha_tuss="90300010"),  # medicamento quimio -> filha
    dict(nome="PARTO", layman="parto",
         itens=["40802019", "31601010", "60000015"],
         filha_tuss=None),
    dict(nome="COLECISTECTOMIA", layman="cirurgia da vesícula",
         itens=["40010012", "40801012", "31003010", "60000015"],
         filha_tuss="70200011"),  # material videolaparoscopia -> filha
    dict(nome="CARDIO_STENT", layman="colocação de stent no coração",
         itens=["40010039", "40501012", "30912016", "60000023", "60000015"],
         filha_tuss="70712028"),  # stent (OPME) -> filha
    dict(nome="BARIATRICA", layman="cirurgia bariátrica",
         itens=["40010012", "40901025", "31309054", "60000015"],
         filha_tuss="70712036"),  # banda gástrica (OPME) -> filha
    dict(nome="HEMODIALISE", layman="tratamento de hemodiálise",
         itens=["40010039", "50000560"],
         filha_tuss=None),
    dict(nome="ARTROSCOPIA", layman="artroscopia do joelho",
         itens=["40010012", "40808133", "30715024", "50000470"],
         filha_tuss=None),
]

# --------------------------------------------------------------------------- #
# Free-text NIP complaint templates (the "textão"). Layman terms, noise, urgency.
# --------------------------------------------------------------------------- #
TPL_PROCEDIMENTO = [
    "Boa tarde. Meu médico solicitou {proc} para o meu tratamento de {epi} e o plano negou a autorização. "
    "Já liguei {n} vezes no atendimento e ninguém resolve. Preciso de uma posição urgente, senão vou perder a data marcada.",
    "Estou revoltado. Pedi autorização para {proc} (indicação do especialista) e recebi negativa sem explicação. "
    "Isso está atrasando meu {epi}. Quero que revejam essa decisão.",
    "Solicito revisão da negativa de {proc}. Faço acompanhamento de {epi} e o procedimento foi indicado pelo meu médico. "
    "Não aceito a recusa e vou registrar reclamação formal.",
    "O plano recusou o meu {proc}. Estou há {n} dias esperando e a situação do meu {epi} está piorando. Preciso de resposta.",
]
TPL_MATERIAL = [
    "Minha cirurgia de {epi} está marcada, a internação já foi liberada, MAS negaram o {mat} que o médico pediu. "
    "Sem esse material não dá para operar. Já são {n} dias de espera, preciso com urgência.",
    "Autorizaram a cirurgia de {epi} mas travaram a liberação do {mat}. É justamente o material principal! "
    "Ninguém me dá retorno sobre isso.",
    "Reclamo da demora na liberação do {mat} para o meu {epi}. A guia da cirurgia saiu, só falta o material, e o hospital não marca sem ele.",
]
TPL_MEDICAMENTO = [
    "Sou paciente de {epi} e o plano negou o {mat} que faz parte do meu protocolo. É um medicamento essencial, "
    "não posso ficar sem. Já tentei resolver pela ouvidoria e não consegui.",
    "Negaram o {mat} do meu tratamento de {epi}. Meu oncologista disse que é indispensável. Estou desesperado, {n} dias sem resposta.",
    "Preciso do {mat} para continuar o {epi}. O plano recusa alegando cobertura, mas o médico diz que é obrigatório. Quero revisão.",
]


def money(a, b):
    return round(random.uniform(a, b), 2)


def add_noise(text: str) -> str:
    """Occasional light noise to make free text realistic (typos / caps / extra spaces)."""
    if random.random() < 0.12:
        text = text.replace("médico", "medico").replace("negaram", "nao autorizaram")
    if random.random() < 0.08:
        text = text.upper()
    return text


def dt_str(d: datetime) -> str:
    return d.strftime("%Y-%m-%d %H:%M:%S")


# --------------------------------------------------------------------------- #
# Generation
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--beneficiarios", type=int, default=N_BENEFICIARIOS)
    ap.add_argument("--nip-rate", type=float, default=NIP_RATE)
    args = ap.parse_args()

    for p in (RAW, PREVIEW):
        p.mkdir(parents=True, exist_ok=True)
    # Each source gets its OWN subfolder so Auto Loader (read_files in streaming
    # mode) can consume a directory, not a single file.
    for sub in ("manifestacoes", "procedimentos_solicitados", "interacoes_callcenter",
                "ground_truth", "dim_plano", "dim_beneficiario", "ref_rol_ans"):
        (RAW / sub).mkdir(exist_ok=True)

    # ---- dim_plano ----
    with open(RAW / "dim_plano" / "dim_plano.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["plano_id", "nome_plano", "segmentacao", "abrangencia", "coparticipacao"])
        for p in PLANOS:
            w.writerow(list(p))

    # ---- ref_rol_ans ----
    with open(RAW / "ref_rol_ans" / "ref_rol_ans.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["codigo_tuss", "nome_procedimento", "categoria", "tipo_item",
                    "segmentacao_cobertura", "obrigatorio_rol", "dut_texto"])
        for r in ROL:
            w.writerow([r[0], r[1], r[2], r[3], r[4], r[5], r[6]])

    # ---- beneficiaries ----
    beneficiarios = []
    with open(RAW / "dim_beneficiario" / "dim_beneficiario.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["beneficiario_id", "nome", "cpf", "data_nascimento", "plano_id",
                    "data_adesao", "uf", "email"])
        for i in range(1, args.beneficiarios + 1):
            bid = f"BEN-{i:06d}"
            plano = random.choice(PLANOS)[0]
            nasc = fake.date_of_birth(minimum_age=0, maximum_age=88)
            adesao = fake.date_between(start_date="-6y", end_date="-2m")
            row = [bid, fake.name(), fake.cpf(), nasc.isoformat(), plano,
                   adesao.isoformat(), fake.estado_sigla(), fake.email()]
            w.writerow(row)
            beneficiarios.append(dict(id=bid, plano=plano))

    # ---- manifestações (VPP pai + VPP filha + NIP) & procedimentos & ground truth ----
    manifest_rows = []      # (all manifestações)
    proc_rows = []          # (line items for VPP-type manifestações)
    gt_rows = []            # (evaluation oracle for NIPs)
    manifest_seq = 0
    vpp_seq = 0
    nip_seq = 0
    proc_seq = 0

    # counters for the summary
    stats = dict(vpp_pai=0, vpp_filha=0, nip=0, nip_resolvida=0,
                 nip_target_filha=0, nip_target_pai=0, nip_ambigua=0, nip_fora_janela=0)

    for ben in beneficiarios:
        # decide how many episodes this beneficiary has (0-3)
        n_epi = random.choices([0, 1, 2, 3], weights=[35, 40, 18, 7])[0]
        if n_epi == 0:
            continue
        chosen = random.sample(EPISODIOS, k=min(n_epi, len(EPISODIOS)))
        ben_vpps = []  # list of dicts describing this beneficiary's VPP guides

        for epi in chosen:
            manifest_seq += 1
            vpp_seq += 1
            vpp_numero = f"VPP{vpp_seq:07d}"
            pai_id = f"MAN-{manifest_seq:07d}"
            # base date of the guide (some intentionally older than 65 days)
            days_ago = random.choice(
                [random.randint(2, 60)] * 4 + [random.randint(70, 200)]  # ~20% out of window
            )
            data_criacao = REF_DATE - timedelta(days=days_ago, hours=random.randint(0, 20))
            # parent guide status
            status_pai = random.choices(
                ["APROVADO", "PARCIAL", "NEGADO", "EM_ANALISE"], weights=[55, 20, 15, 10])[0]

            # build line items from the episode
            item_tuss = list(epi["itens"])
            desc_items = ", ".join(ROL_BY_TUSS[t][1] for t in item_tuss)
            manifest_rows.append(dict(
                manifestacao_id=pai_id, beneficiario_id=ben["id"], tipo="VPP",
                manifestacao_pai_id="", data_criacao=dt_str(data_criacao),
                data_atualizacao=dt_str(data_criacao + timedelta(days=random.randint(0, 3))),
                status=status_pai, canal="PORTAL_PRESTADOR",
                prestador_id=f"PREST-{random.randint(1, 400):04d}",
                descricao=f"Guia de autorização prévia ({epi['layman']}): {desc_items}.",
                vpp_numero=vpp_numero, prazo_ans="", parecer_texto="",
                analista_id="", data_resolucao="",
            ))
            stats["vpp_pai"] += 1

            for t in item_tuss:
                proc_seq += 1
                r = ROL_BY_TUSS[t]
                status_item = "APROVADO" if status_pai == "APROVADO" else \
                    random.choices(["APROVADO", "NEGADO"], weights=[70, 30])[0]
                proc_rows.append(dict(
                    procedimento_id=f"PRC-{proc_seq:08d}", manifestacao_id=pai_id,
                    codigo_tuss=t, descricao_procedimento=r[1], categoria=r[2],
                    tipo_item=r[3], status_item=status_item, valor=money(80, 45000),
                ))

            # child manifestação (material/med/OPME) if the episode has one
            filha_id = None
            filha_tuss = epi["filha_tuss"]
            if filha_tuss:
                manifest_seq += 1
                filha_id = f"MAN-{manifest_seq:07d}"
                rf = ROL_BY_TUSS[filha_tuss]
                status_filha = random.choices(["NEGADO", "EM_ANALISE", "APROVADO"], weights=[50, 30, 20])[0]
                manifest_rows.append(dict(
                    manifestacao_id=filha_id, beneficiario_id=ben["id"], tipo="VPP_FILHA",
                    manifestacao_pai_id=pai_id,
                    data_criacao=dt_str(data_criacao + timedelta(hours=random.randint(1, 48))),
                    data_atualizacao=dt_str(data_criacao + timedelta(days=random.randint(0, 4))),
                    status=status_filha, canal="PORTAL_PRESTADOR",
                    prestador_id=f"PREST-{random.randint(1, 400):04d}",
                    descricao=f"Solicitação de {rf[3].lower()}: {rf[1]} (vinculada à guia {vpp_numero}).",
                    vpp_numero=vpp_numero, prazo_ans="", parecer_texto="",
                    analista_id="", data_resolucao="",
                ))
                stats["vpp_filha"] += 1
                proc_seq += 1
                proc_rows.append(dict(
                    procedimento_id=f"PRC-{proc_seq:08d}", manifestacao_id=filha_id,
                    codigo_tuss=filha_tuss, descricao_procedimento=rf[1], categoria=rf[2],
                    tipo_item=rf[3], status_item=status_filha, valor=money(1500, 90000),
                ))

            ben_vpps.append(dict(
                pai_id=pai_id, filha_id=filha_id, vpp_numero=vpp_numero, epi=epi,
                data_criacao=data_criacao, days_ago=days_ago, filha_tuss=filha_tuss,
            ))

        # decide whether this beneficiary opens a NIP
        if not ben_vpps or random.random() > args.nip_rate:
            continue

        # pick the target episode/guide (prefer ones within the 65-day window)
        in_window = [v for v in ben_vpps if v["days_ago"] <= 65]
        target = random.choice(in_window) if in_window else random.choice(ben_vpps)
        ambigua = len(ben_vpps) >= 2 and random.random() < 0.35
        fora_janela_distractor = any(v["days_ago"] > 65 for v in ben_vpps)

        # complaint type -> which manifestação is the correct answer (pai vs filha)
        if target["filha_tuss"] and random.random() < 0.6:
            complaint_type = "MATERIAL" if ROL_BY_TUSS[target["filha_tuss"]][3] in ("MATERIAL", "OPME") else "MEDICAMENTO"
            correct_id = target["filha_id"]
            correct_tipo = "VPP_FILHA"
            mat_layman = ROL_BY_TUSS[target["filha_tuss"]][7]
        else:
            complaint_type = "PROCEDIMENTO"
            correct_id = target["pai_id"]
            correct_tipo = "VPP"
            mat_layman = None

        manifest_seq += 1
        nip_seq += 1
        nip_id = f"MAN-{manifest_seq:07d}"
        nip_data = REF_DATE - timedelta(days=random.randint(0, 40), hours=random.randint(0, 20))
        prazo = nip_data + timedelta(days=5)
        epi_layman = target["epi"]["layman"]
        n = random.randint(2, 9)

        if complaint_type == "PROCEDIMENTO":
            # cite a denied procedure from the target guide (layman term, not exact name)
            proc_layman = ROL_BY_TUSS[random.choice(target["epi"]["itens"])][7]
            texto = random.choice(TPL_PROCEDIMENTO).format(proc=proc_layman, epi=epi_layman, n=n)
        elif complaint_type == "MATERIAL":
            texto = random.choice(TPL_MATERIAL).format(mat=mat_layman, epi=epi_layman, n=n)
        else:
            texto = random.choice(TPL_MEDICAMENTO).format(mat=mat_layman, epi=epi_layman, n=n)
        texto = add_noise(texto)

        # sometimes the beneficiary cites the VPP number (helps matching when present)
        cita_vpp = random.random() < 0.25
        if cita_vpp:
            texto += f" (protocolo/guia informado: {target['vpp_numero']})"

        # resolved-case status trap
        resolvida = random.random() < RESOLVED_NIP_RATE
        parecer = ""
        analista = ""
        data_res = ""
        status_nip = "EM_ANALISE"
        if resolvida:
            status_nip = "RESOLVIDA"
            analista = f"ANL-{random.randint(1, 60):03d}"
            data_res = dt_str(nip_data + timedelta(days=random.randint(1, 5)))
            deferida = random.random() < 0.7
            parecer = (
                f"Após análise, {'DEFERIDA' if deferida else 'INDEFERIDA'} a solicitação. "
                f"Guia {target['vpp_numero']} localizada. "
                + ("Procedimento consta no rol e atende à DUT; negativa revertida e item autorizado."
                   if deferida else
                   "Procedimento fora dos critérios de cobertura do plano; negativa mantida.")
            )
            # THE TRAP: flip the denied line item(s) of the correct manifestação to APROVADO
            if deferida:
                for pr in proc_rows:
                    if pr["manifestacao_id"] == correct_id and pr["status_item"] == "NEGADO":
                        pr["status_item"] = "APROVADO"
                for m in manifest_rows:
                    if m["manifestacao_id"] == correct_id and m["status"] == "NEGADO":
                        m["status"] = "APROVADO"
            stats["nip_resolvida"] += 1

        manifest_rows.append(dict(
            manifestacao_id=nip_id, beneficiario_id=ben["id"], tipo="NIP",
            manifestacao_pai_id="", data_criacao=dt_str(nip_data),
            data_atualizacao=data_res or dt_str(nip_data),
            status=status_nip, canal="ANS", prestador_id="",
            descricao=texto, vpp_numero=(target["vpp_numero"] if cita_vpp else ""),
            prazo_ans=dt_str(prazo), parecer_texto=parecer,
            analista_id=analista, data_resolucao=data_res,
        ))
        stats["nip"] += 1
        stats["nip_target_filha" if correct_tipo == "VPP_FILHA" else "nip_target_pai"] += 1
        if ambigua:
            stats["nip_ambigua"] += 1
        if fora_janela_distractor:
            stats["nip_fora_janela"] += 1

        gt_rows.append(dict(
            nip_id=nip_id, beneficiario_id=ben["id"],
            correct_manifestacao_id=correct_id, correct_tipo=correct_tipo,
            vpp_numero=target["vpp_numero"], episodio=target["epi"]["nome"],
            complaint_type=complaint_type, nip_resolvida=int(resolvida),
            ambigua=int(ambigua), tem_distrator_fora_janela=int(fora_janela_distractor),
            cita_vpp=int(cita_vpp),
        ))

    # ---- call-center interactions (for the ML propensity model) ----
    nip_bens = {g["beneficiario_id"] for g in gt_rows}
    cc_rows = []
    cc_seq = 0
    for ben in beneficiarios:
        will_nip = ben["id"] in nip_bens
        # NIP openers have more interactions and more negative sentiment (learnable signal)
        n_int = random.choices([0, 1, 2, 3, 4, 5], weights=(
            [15, 20, 22, 20, 13, 10] if will_nip else [45, 28, 15, 7, 3, 2]))[0]
        for _ in range(n_int):
            cc_seq += 1
            base = random.uniform(-0.9, 0.2) if will_nip else random.uniform(-0.3, 0.8)
            sentiment = round(max(-1.0, min(1.0, base + random.uniform(-0.15, 0.15))), 3)
            data = REF_DATE - timedelta(days=random.randint(1, 90), hours=random.randint(0, 23))
            neg = sentiment < -0.2
            frases_neg = ["Isso é um absurdo, ninguém resolve!", "Vou reclamar na ANS se não resolverem.",
                          "Já liguei várias vezes e continua negado.", "Estou muito insatisfeito com o atendimento."]
            frases_pos = ["Obrigado, ficou resolvido.", "Consegui a autorização, valeu.",
                          "Atendimento tranquilo, sem problemas.", "Só uma dúvida sobre a carteirinha."]
            cc_rows.append(dict(
                interacao_id=f"CC-{cc_seq:08d}", beneficiario_id=ben["id"],
                data_interacao=dt_str(data), canal=random.choice(["TELEFONE", "CHAT", "APP"]),
                duracao_seg=random.randint(45, 1800),
                assunto=random.choice(["AUTORIZACAO", "REEMBOLSO", "REDE", "COBRANCA", "CADASTRO"]),
                sentimento_score=sentiment,
                transcricao=random.choice(frases_neg if neg else frases_pos),
                protocolos_abertos=random.randint(0, 4) if will_nip else random.randint(0, 1),
            ))

    # --------------------------------------------------------------------- #
    # Write fact tables (partitioned into PART_FILES to simulate incremental arrival)
    # --------------------------------------------------------------------- #
    def write_parts(rows, subdir, fieldnames, ext="csv"):
        random.shuffle(rows)
        chunks = [rows[i::PART_FILES] for i in range(PART_FILES)]
        for idx, chunk in enumerate(chunks):
            path = RAW / subdir / f"part-{idx:03d}.{ 'jsonl' if ext=='jsonl' else 'csv'}"
            if ext == "jsonl":
                with open(path, "w") as f:
                    for r in chunk:
                        f.write(json.dumps(r, ensure_ascii=False) + "\n")
            else:
                with open(path, "w", newline="") as f:
                    w = csv.DictWriter(f, fieldnames=fieldnames)
                    w.writeheader()
                    w.writerows(chunk)

    man_fields = ["manifestacao_id", "beneficiario_id", "tipo", "manifestacao_pai_id",
                  "data_criacao", "data_atualizacao", "status", "canal", "prestador_id",
                  "descricao", "vpp_numero", "prazo_ans", "parecer_texto", "analista_id", "data_resolucao"]
    proc_fields = ["procedimento_id", "manifestacao_id", "codigo_tuss", "descricao_procedimento",
                   "categoria", "tipo_item", "status_item", "valor"]
    cc_fields = list(cc_rows[0].keys()) if cc_rows else []

    write_parts(manifest_rows, "manifestacoes", man_fields, "csv")
    write_parts(proc_rows, "procedimentos_solicitados", proc_fields, "csv")
    write_parts(cc_rows, "interacoes_callcenter", cc_fields, "jsonl")

    # ground truth (single file -- evaluation oracle)
    gt_fields = list(gt_rows[0].keys())
    with open(RAW / "ground_truth" / "nip_vpp_labels.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=gt_fields)
        w.writeheader()
        w.writerows(gt_rows)

    # --------------------------------------------------------------------- #
    # Preview samples + summary (committed as text evidence)
    # --------------------------------------------------------------------- #
    def sample_csv(rows, fieldnames, name, k=8):
        with open(PREVIEW / name, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows[:k])

    sample_csv([r for r in manifest_rows if r["tipo"] == "NIP"], man_fields, "sample_nips.csv")
    sample_csv([r for r in manifest_rows if r["tipo"] == "VPP"], man_fields, "sample_vpp_pai.csv")
    sample_csv([r for r in manifest_rows if r["tipo"] == "VPP_FILHA"], man_fields, "sample_vpp_filha.csv")
    sample_csv(proc_rows, proc_fields, "sample_procedimentos.csv")
    sample_csv(gt_rows, gt_fields, "sample_ground_truth.csv")
    with open(PREVIEW / "sample_callcenter.jsonl", "w") as f:
        for r in cc_rows[:8]:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    total_man = len(manifest_rows)
    cc_pos = sum(1 for r in cc_rows if r["beneficiario_id"] in nip_bens)
    summary = f"""# Synthetic data — generation summary

Generated by `01_synthetic_data/generator/generate.py` (seed={SEED}, ref_date={REF_DATE.date()}).
All data is synthetic. No real customer data.

## Volumes
| Table | Rows |
|---|---|
| dim_plano | {len(PLANOS)} |
| dim_beneficiario | {args.beneficiarios} |
| ref_rol_ans | {len(ROL)} |
| manifestacoes (total) | {total_man} |
| &nbsp;&nbsp;• VPP (pai) | {stats['vpp_pai']} |
| &nbsp;&nbsp;• VPP_FILHA | {stats['vpp_filha']} |
| &nbsp;&nbsp;• NIP | {stats['nip']} |
| procedimentos_solicitados | {len(proc_rows)} |
| interacoes_callcenter | {len(cc_rows)} |
| ground_truth (NIP labels) | {len(gt_rows)} |

## Planted hard cases (this is what makes matching non-trivial)
| Case | Count | Why it matters |
|---|---|---|
| NIP → correct answer is the CHILD (pai/filha rule) | {stats['nip_target_filha']} | material/medicamento/OPME complaints must resolve to VPP_FILHA, not the parent guide |
| NIP → correct answer is the PARENT guide | {stats['nip_target_pai']} | procedure complaints resolve to the VPP pai |
| Resolved NIPs (status trap) | {stats['nip_resolvida']} | denied line items flipped to APROVADO + parecer filled → naive status matching fails |
| NIPs with multi-VPP ambiguity | {stats['nip_ambigua']} | beneficiary has ≥2 VPPs with overlapping procedures → needs tie-break |
| NIPs with an out-of-65-day-window distractor VPP | {stats['nip_fora_janela']} | old guide must be excluded by the 65-day rule |

## Call-center / ML signal
- Beneficiaries who opened a NIP: {len(nip_bens)}
- Call-center interactions from NIP-openers: {cc_pos} of {len(cc_rows)} ({100*cc_pos/max(1,len(cc_rows)):.1f}%)
- NIP-openers have more interactions and more negative sentiment (learnable propensity signal).

## Source formats (for Lakeflow ingestion variety)
- CSV: dim_plano, dim_beneficiario, ref_rol_ans, manifestacoes/, procedimentos_solicitados/
- JSONL: interacoes_callcenter/
- Fact tables split into {PART_FILES} part-files each (simulates incremental arrival for Auto Loader).
"""
    (PREVIEW / "_summary.md").write_text(summary, encoding="utf-8")
    print(summary)
    print(f"\nWrote raw/ to: {RAW}")
    print(f"Wrote preview/ to: {PREVIEW}")


if __name__ == "__main__":
    main()
