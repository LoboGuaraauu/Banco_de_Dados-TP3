"""T6 — Paginas da tabela t.

Registre em resultados/t06.json: relpages, reltuples, bytes (pg_relation_size), block_size,
paginas_pelo_tamanho (bytes / block_size), tuplas_por_pagina. Faça ANALYZE antes.
"""
from common import conectar, salvar  # noqa: F401
from params import carregar  # noqa: F401

N_TUPLAS = 100_000


def main():
    p = carregar()  # noqa: F841 (a tabela ja foi criada pela T5)
    with conectar() as con, con.cursor() as cur:
        cur.execute("SELECT count(*) FROM t")
        n = cur.fetchone()[0]
        if n != N_TUPLAS:
            raise RuntimeError(f"t tem {n} tuplas (esperado {N_TUPLAS}); execute a T5 antes")

        cur.execute("ANALYZE t")
        cur.execute("SELECT relpages, reltuples FROM pg_class WHERE oid = 't'::regclass")
        relpages, reltuples = cur.fetchone()
        cur.execute("SELECT pg_relation_size('t')")
        tamanho = cur.fetchone()[0]
        cur.execute("SELECT current_setting('block_size')::int")
        block_size = cur.fetchone()[0]
        # maximo de tuplas encontradas em uma unica pagina (ctid = (pagina, item))
        cur.execute("SELECT max(c) FROM (SELECT count(*) AS c FROM t "
                    "GROUP BY (ctid::text::point)[0]) s")
        max_por_pagina = cur.fetchone()[0]

    paginas_pelo_tamanho = tamanho // block_size
    if paginas_pelo_tamanho != relpages:
        print(f"aviso: relpages={relpages} difere de bytes/block_size={paginas_pelo_tamanho}")

    resultado = {
        "relpages": relpages,
        "reltuples": reltuples,
        "bytes": tamanho,
        "block_size": block_size,
        "paginas_pelo_tamanho": paginas_pelo_tamanho,
        "tuplas_por_pagina": reltuples / relpages,         # media
        "tuplas_por_pagina_max": max_por_pagina,           # cheia (apoio ao relatorio)
    }
    salvar("t06", resultado)
    print("t06 ok:", resultado)


if __name__ == "__main__":
    main()
