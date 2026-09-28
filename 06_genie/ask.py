"""
Ask the NIP->VPP Genie Space a few natural-language questions and capture the
generated SQL + results as text evidence. Uses the Genie Conversation API.

Usage:  python ask.py
"""
from __future__ import annotations

from pathlib import Path

from databricks.sdk import WorkspaceClient

PROFILE = "wks-demo-brabo"
SPACE_ID = (Path(__file__).parent / ".space_id").read_text().strip()
EVID = Path(__file__).resolve().parents[1] / "evidence"

QUESTIONS = [
    "Quantas NIPs existem por status de SLA?",
    "Qual a taxa de matches auto resolvíveis (auto_resolvavel) entre as NIPs?",
    "Quais são os 5 beneficiários com mais interações no call center e menor sentimento médio?",
]


def result_table(w, conv_id, msg_id, att) -> str:
    try:
        r = w.genie.get_message_attachment_query_result(SPACE_ID, conv_id, msg_id, att.attachment_id)
        sr = r.statement_response
        cols = [c.name for c in sr.manifest.schema.columns]
        rows = sr.result.data_array or []
        out = [" | ".join(cols)]
        for row in rows[:10]:
            out.append(" | ".join("" if v is None else str(v) for v in row))
        return "\n".join(out)
    except Exception as e:
        return f"(could not fetch result rows: {e})"


def main():
    w = WorkspaceClient(profile=PROFILE)
    lines = ["# Evidence — Genie Space (natural-language analytics)\n",
             f"Space `NIP VPP Copilot` (id `{SPACE_ID}`) over the gold tables. Analysts ask in "
             f"plain Portuguese via Genie / Databricks One; Genie writes and runs the SQL.\n"]
    for q in QUESTIONS:
        print(f"ASK: {q}")
        msg = w.genie.start_conversation_and_wait(SPACE_ID, q)
        lines.append(f"## Q: {q}")
        sql, table = None, None
        for att in (msg.attachments or []):
            if att.query and att.query.query:
                sql = att.query.query
                table = result_table(w, msg.conversation_id, msg.id, att)
            elif att.text and att.text.content:
                lines.append(f"_{att.text.content.strip()}_\n")
        if sql:
            lines.append("Generated SQL:\n```sql\n" + sql.strip() + "\n```")
        if table:
            lines.append("Result:\n```\n" + table + "\n```")
        lines.append("")
        print("  ok")
    report = "\n".join(lines) + "\n"
    (EVID / "06_genie.md").write_text(report, encoding="utf-8")
    print("\n" + report)


if __name__ == "__main__":
    main()
