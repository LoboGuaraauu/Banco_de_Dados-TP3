"""Resumo de planos EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) para T12 e T13."""
from common import explain, tipos_de_no


def buffers_de(plano):
    """Blocos compartilhados do no raiz (acumulados sobre a arvore inteira)."""
    raiz = plano["Plan"]
    return {"shared_hit": raiz.get("Shared Hit Blocks", 0),
            "shared_read": raiz.get("Shared Read Blocks", 0)}


def medir_sql(cur, sql):
    """Executa EXPLAIN ANALYZE de sql e resume: sql, linhas (reais), nos, custo, tempo_ms, buffers."""
    plano = explain(cur, sql)
    return {
        "sql": sql,
        "linhas": plano["Plan"]["Actual Rows"],
        "nos": tipos_de_no(plano),
        "custo": plano["Plan"]["Total Cost"],
        "tempo_ms": plano["Execution Time"],
        "buffers": buffers_de(plano),
    }
