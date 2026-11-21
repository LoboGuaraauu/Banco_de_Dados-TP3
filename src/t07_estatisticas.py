"""T7 — Estatisticas e blocos lidos.

Registre em resultados/t07.json: valor_consultado, pg_stats (lista, um item por atributo de t),
heap_blks_read e heap_blks_hit (pg_statio_user_tables depois de uma consulta v = valor,
zerando antes os contadores da tabela e forçando o flush das estatisticas),
explain_buffers {hit, read} da mesma consulta.
"""
from common import conectar, explain, salvar, tipos_de_no  # noqa: F401
from params import carregar  # noqa: F401

N_TUPLAS = 100_000

# Colunas de pg_stats; as de tipo anyarray sao lidas como texto e convertidas em lista.
COLUNAS_ARRAY = ("most_common_vals", "histogram_bounds", "most_common_elems")
SQL_PG_STATS = """
    SELECT attname, inherited, null_frac, avg_width, n_distinct,
           most_common_vals::text AS most_common_vals, most_common_freqs,
           histogram_bounds::text AS histogram_bounds, correlation,
           most_common_elems::text AS most_common_elems, most_common_elem_freqs,
           elem_count_histogram
    FROM pg_stats WHERE schemaname = current_schema() AND tablename = 't'
    ORDER BY attname"""


def _valor(x):
    x = x.strip().strip('"')
    for conv in (int, float):
        try:
            return conv(x)
        except ValueError:
            pass
    return x


def _lista(texto):
    """'{1,2,3}' -> [1, 2, 3] (suficiente para colunas numericas)."""
    if texto is None:
        return None
    miolo = texto.strip()[1:-1]
    return [_valor(x) for x in miolo.split(",")] if miolo else []


def ler_pg_stats(cur):
    cur.execute(SQL_PG_STATS)
    nomes = [d.name for d in cur.description]
    itens = []
    for linha in cur.fetchall():
        item = dict(zip(nomes, linha))
        for c in COLUNAS_ARRAY:
            item[c] = _lista(item[c])
        itens.append(item)
    return itens


def flush_estatisticas(cur):
    """Forca o envio dos contadores pendentes desta sessao ao sistema de estatisticas.

    Em autocommit, ao terminar este comando o backend fica ocioso e faz o flush
    sem esperar o intervalo minimo de 1 s.
    """
    cur.execute("SELECT pg_stat_force_next_flush()")


def contadores_statio(cur):
    cur.execute("SELECT heap_blks_read, heap_blks_hit FROM pg_statio_user_tables "
                "WHERE relid = 't'::regclass")
    return cur.fetchone()


def main():
    p = carregar()
    valor = p["t_cardinalidade_v"] // 2   # valor dentro do dominio [0, C-1]
    sql = f"SELECT count(*) FROM t WHERE v = {int(valor)}"

    with conectar() as con, con.cursor() as cur:
        # Pre-condicoes: t de 100.000 tuplas e sem indice sobre v (so a chave primaria),
        # para que a consulta seja uma varredura sequencial como na T5/T6.
        cur.execute("SELECT count(*) FROM t")
        n = cur.fetchone()[0]
        cur.execute("SELECT indexname FROM pg_indexes WHERE tablename = 't' "
                    "AND schemaname = current_schema()")
        indices = [r[0] for r in cur.fetchall()]
        if n != N_TUPLAS or indices != ["t_pkey"]:
            raise RuntimeError(f"t com {n} tuplas e indices {indices}; execute a T5 antes")

        cur.execute("ANALYZE t")
        pg_stats = ler_pg_stats(cur)

        # Janela de medicao limpa: descarrega o que ficou pendente (ANALYZE, contagens),
        # zera os contadores de t e confere que zeraram.
        flush_estatisticas(cur)
        cur.execute("SELECT pg_stat_reset_single_table_counters('t'::regclass)")
        antes = contadores_statio(cur)
        if tuple(antes) != (0, 0):
            print(f"aviso: contadores nao zeraram (read, hit) = {antes}")

        # A consulta medida
        cur.execute(sql)
        cur.fetchall()
        flush_estatisticas(cur)
        heap_blks_read, heap_blks_hit = contadores_statio(cur)

        # EXPLAIN (ANALYZE, BUFFERS) da mesma consulta; roda por ultimo,
        # pois executa a consulta de novo e somaria nos contadores.
        plano = explain(cur, sql)
        raiz = plano["Plan"]
        explain_buffers = {"hit": raiz.get("Shared Hit Blocks", 0),
                           "read": raiz.get("Shared Read Blocks", 0)}
        cur.execute("SELECT relpages FROM pg_class WHERE oid = 't'::regclass")
        relpages = cur.fetchone()[0]

    resultado = {
        "valor_consultado": valor,
        "pg_stats": pg_stats,
        "heap_blks_read": heap_blks_read,
        "heap_blks_hit": heap_blks_hit,
        "explain_buffers": explain_buffers,
        # apoio ao relatorio
        "relpages": relpages,
        "nos": tipos_de_no(plano),
    }
    salvar("t07", resultado)
    print(f"t07 ok: v = {valor}; statio read={heap_blks_read} hit={heap_blks_hit}; "
          f"explain {explain_buffers}; relpages={relpages}")


if __name__ == "__main__":
    main()
