"""T11 — Metadados dos indices de movie.

Para cada indice de movie (movie_key, movie_title, movie_votes) registre em resultados/t11.json:
indice, tabela, atributo, altura, max_chaves_por_bloco_folha, media_chaves_por_bloco_folha, blocos_folha,
media_blocos_folha_por_chave, media_blocos_dados_por_chave, linhas, chaves_distintas.
Fontes: pgstatindex, bt_page_stats (pageinspect), pg_stats, pg_class.
"""
from psycopg import sql

from common import conectar, salvar
from params import carregar  # noqa: F401

TABELA = "movie"
INDICES = ("movie_key", "movie_title", "movie_votes")


def atributo_do_indice(cur, indice):
    cur.execute("""
        SELECT a.attname
        FROM pg_index x
        JOIN pg_class i ON i.oid = x.indexrelid
        JOIN pg_class t ON t.oid = x.indrelid
        JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = x.indkey[0]
        WHERE t.relname = %s AND i.relname = %s""", (TABELA, indice))
    linha = cur.fetchone()
    if linha is None:
        cur.execute("SELECT indexname FROM pg_indexes WHERE tablename = %s", (TABELA,))
        raise RuntimeError(f"indice {indice} nao encontrado em {TABELA}; existentes: {[r[0] for r in cur.fetchall()]}")
    return linha[0]


def folhas_por_bloco(cur, indice):
    """Chaves (tuplas de indice, sem a high key) por bloco-folha, via bt_page_stats."""
    cur.execute("SELECT pg_relation_size(%s::regclass) / current_setting('block_size')::int", (indice,))
    paginas = cur.fetchone()[0]
    cur.execute("""
        SELECT count(*), max(k), avg(k)
        FROM (SELECT s.live_items - CASE WHEN s.btpo_next = 0 THEN 0 ELSE 1 END AS k
              FROM generate_series(1, %s) AS b, LATERAL bt_page_stats(%s::text, b) AS s
              WHERE s.btpo_level = 0 AND s.type IN ('l', 'r')) q""", (paginas - 1, indice))
    n, maximo, media = cur.fetchone()
    return int(n), int(maximo), float(media)


def metadados(cur, indice):
    atributo = atributo_do_indice(cur, indice)
    col = sql.Identifier(atributo)
    cur.execute("SELECT tree_level, leaf_pages FROM pgstatindex(%s::regclass)", (indice,))
    nivel, folhas = cur.fetchone()
    _, max_chaves, media_chaves = folhas_por_bloco(cur, indice)

    cur.execute(sql.SQL("SELECT count(*), count(DISTINCT {c}) FROM movie").format(c=col))
    linhas, distintas = cur.fetchone()

    # media, sobre as chaves, de blocos de dados (paginas do heap) distintos que as contem
    cur.execute(sql.SQL(
        "SELECT avg(n)::float8 FROM (SELECT count(DISTINCT (ctid::text::point)[0]) AS n "
        "FROM movie WHERE {c} IS NOT NULL GROUP BY {c}) q").format(c=col))
    blocos_dados = cur.fetchone()[0]

    cur.execute("SELECT n_distinct FROM pg_stats WHERE tablename = %s AND attname = %s", (TABELA, atributo))
    r = cur.fetchone()
    estimado = None if r is None else (r[0] if r[0] > 0 else -r[0] * linhas)

    return {
        "indice": indice,
        "tabela": TABELA,
        "atributo": atributo,
        "altura": int(nivel),                  # nivel da raiz (0 = raiz e folha), como no pgstatindex
        "niveis": int(nivel) + 1,
        "max_chaves_por_bloco_folha": max_chaves,
        "media_chaves_por_bloco_folha": media_chaves,
        "blocos_folha": int(folhas),
        "media_blocos_folha_por_chave": folhas / distintas,   # = (entradas por chave) / (entradas por folha)
        "media_blocos_dados_por_chave": blocos_dados,
        "linhas": int(linhas),
        "chaves_distintas": int(distintas),
        "chaves_distintas_pg_stats": estimado,  # estimativa do otimizador, para comparar
    }


def main():
    carregar()
    resultados = []
    with conectar() as con, con.cursor() as cur:
        for indice in INDICES:
            m = metadados(cur, indice)
            resultados.append(m)
            print(m)
    salvar("t11", resultados)


if __name__ == "__main__":
    main()
