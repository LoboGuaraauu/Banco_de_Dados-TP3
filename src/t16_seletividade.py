"""T16 — Estimativa de seletividade.

Para votes < params['movie_votos_baixo'] e votes > params['movie_votos_alto'] registre linhas estimadas x reais
com as estatisticas padrao e com SET STATISTICS 1000 em votes (depois restaure o padrao: SET STATISTICS -1).
resultados/t16.json: padrao e statistics_1000 ({baixo, alto}: {sql, estimadas, reais, no}), histograma_padrao.
"""
from common import conectar, explain, salvar
from params import carregar


def medir(cur, p):
    """Linhas estimadas x reais (no raiz do plano) das duas consultas."""
    consultas = {
        "baixo": f"SELECT * FROM movie WHERE votes < {p['movie_votos_baixo']}",
        "alto": f"SELECT * FROM movie WHERE votes > {p['movie_votos_alto']}",
    }
    saida = {}
    for chave, sql in consultas.items():
        raiz = explain(cur, sql)["Plan"]
        saida[chave] = {
            "sql": sql,
            "estimadas": raiz["Plan Rows"],
            "reais": raiz["Actual Rows"],
            "no": raiz["Node Type"],
        }
    return saida


def histograma(cur):
    """Estatisticas de votes em pg_stats (com o alvo de estatisticas atual)."""
    cur.execute("""
        SELECT n_distinct, null_frac, histogram_bounds::text
        FROM pg_stats WHERE tablename = 'movie' AND attname = 'votes'
    """)
    n_distinct, null_frac, bounds = cur.fetchone()
    limites = [int(x) for x in bounds.strip("{}").split(",")] if bounds else []
    return {
        "n_distinct": n_distinct,
        "null_frac": null_frac,
        "n_limites": len(limites),
        "limites": limites,
    }


def main():
    p = carregar()
    with conectar() as con, con.cursor() as cur:
        try:
            # estado de partida: estatisticas padrao (default_statistics_target)
            cur.execute("ALTER TABLE movie ALTER COLUMN votes SET STATISTICS -1")
            cur.execute("ANALYZE movie")
            padrao = medir(cur, p)
            hist = histograma(cur)

            cur.execute("ALTER TABLE movie ALTER COLUMN votes SET STATISTICS 1000")
            cur.execute("ANALYZE movie")
            stats1000 = medir(cur, p)
        finally:
            # restaura o padrao e recoleta as estatisticas
            cur.execute("ALTER TABLE movie ALTER COLUMN votes SET STATISTICS -1")
            cur.execute("ANALYZE movie")

    salvar("t16", {
        "padrao": padrao,
        "statistics_1000": stats1000,
        "histograma_padrao": hist,
    })


if __name__ == "__main__":
    main()
