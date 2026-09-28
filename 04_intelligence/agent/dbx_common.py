"""Shared helpers: Databricks OAuth token, SQL access, and the Foundation Model client."""
from __future__ import annotations

import json
import subprocess
from functools import lru_cache

PROFILE = "wks-demo-brabo"
HOST = "https://fevm-wks-demo-brabo.cloud.databricks.com"
WAREHOUSE_ID = "bb64cb12ed5c77f0"
HTTP_PATH = f"/sql/1.0/warehouses/{WAREHOUSE_ID}"
CATALOG = "wks_demo_brabo_catalog"
MODEL = "databricks-gpt-6-sol"


@lru_cache(maxsize=1)
def token() -> str:
    out = subprocess.check_output(["databricks", "auth", "token", "-p", PROFILE], text=True)
    return json.loads(out)["access_token"]


@lru_cache(maxsize=1)
def _connection():
    from databricks import sql
    return sql.connect(server_hostname=HOST.replace("https://", ""),
                       http_path=HTTP_PATH, access_token=token())


def query(sql_text: str):
    """Run SQL, return list[dict]."""
    with _connection().cursor() as cur:
        cur.execute(sql_text)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


@lru_cache(maxsize=1)
def llm():
    from openai import OpenAI
    return OpenAI(base_url=f"{HOST}/serving-endpoints", api_key=token())


def chat_json(system: str, user: str, model: str = MODEL, max_tokens: int = 900) -> dict:
    """Call the FM and parse a JSON object out of the reply (robust to code fences)."""
    r = llm().chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_tokens=max_tokens,
    )
    txt = r.choices[0].message.content.strip()
    if "```" in txt:
        txt = txt.split("```")[1]
        if txt.startswith("json"):
            txt = txt[4:]
    start, end = txt.find("{"), txt.rfind("}")
    return json.loads(txt[start:end + 1])
