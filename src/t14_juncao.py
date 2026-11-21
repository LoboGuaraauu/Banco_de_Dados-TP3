"""T14 — Subconsulta x junção.

Filmes com mais votos que params['movie_titulo_alvo']: uma versao com subconsulta e outra com junção (auto-junção).
resultados/t14.json: titulo_alvo, e chaves 'subconsulta' e 'juncao', cada uma {sql, linhas, nos, custo, tempo_ms}.
"""
from common import conectar, explain, salvar, tipos_de_no
from params import carregar


def medir(cur, sql):
    """Executa EXPLAIN (ANALYZE, BUFFERS) e resume o plano."""
    plano = explain(cur, sql)
    raiz = plano["Plan"]
    return {
        "sql": sql,
        "linhas": raiz["Actual Rows"],
        "nos": tipos_de_no(plano),
        "custo": raiz["Total Cost"],
        "tempo_ms": plano["Execution Time"],
    }


def main():
    p = carregar()
    titulo = p["movie_titulo_alvo"]
    lit = "'" + titulo.replace("'", "''") + "'"

    with conectar() as con, con.cursor() as cur:
        # Se o titulo nao for unico, fixa o filme de menor id nas duas formulacoes,
        # de modo que a subconsulta escalar nunca retorne mais de uma linha
        # e as duas consultas continuem equivalentes.
        cur.execute(f"SELECT count(*), min(id) FROM movie WHERE title = {lit}")
        n_alvo, id_min = cur.fetchone()
        if n_alvo == 0:
            raise SystemExit(f"filme-alvo {titulo!r} nao encontrado em movie")
        extra_sub = f" AND id = {id_min}" if n_alvo > 1 else ""
        extra_join = f" AND a.id = {id_min}" if n_alvo > 1 else ""

        sql_sub = (
            "SELECT m.id, m.title, m.votes FROM movie m "
            f"WHERE m.votes > (SELECT votes FROM movie WHERE title = {lit}{extra_sub})"
        )
        sql_join = (
            "SELECT m.id, m.title, m.votes FROM movie m "
            f"JOIN movie a ON m.votes > a.votes WHERE a.title = {lit}{extra_join}"
        )

        r_sub = medir(cur, sql_sub)
        r_join = medir(cur, sql_join)

    if r_sub["linhas"] != r_join["linhas"]:
        print("AVISO: as duas formulacoes retornaram numeros de linhas diferentes!",
              r_sub["linhas"], r_join["linhas"])

    salvar("t14", {"titulo_alvo": titulo, "subconsulta": r_sub, "juncao": r_join})


if __name__ == "__main__":
    main()
