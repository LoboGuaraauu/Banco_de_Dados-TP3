"""T15 — LIKE e indices.

Consultas (letras em params): prefixo_like (title LIKE 'X%'), prefixo_substr (substr(title,1,1) = 'X'),
sufixo_like (title LIKE '%Y') e sufixo_reverse (reverse(title) LIKE 'Y%').
Meça o plano ANTES e DEPOIS de criar os indices adequados (text_pattern_ops, indice funcional em substr,
indice em reverse(title) com text_pattern_ops). resultados/t15.json:
  antes e depois: {<consulta>: {sql, linhas, nos, custo}}, indices_criados: {nome: DDL}.
Os indices criados devem permanecer no banco.
"""
from common import conectar, explain, salvar, tipos_de_no
from params import carregar

INDICES = {
    # atende title LIKE 'X%' (prefixo) em bancos com colacao nao-C
    "idx_movie_title_pattern": "CREATE INDEX idx_movie_title_pattern ON movie (title text_pattern_ops)",
    # atende substr(title,1,1) = 'X' (a expressao deve ser identica a da consulta)
    "idx_movie_title_substr": "CREATE INDEX idx_movie_title_substr ON movie (substr(title, 1, 1))",
    # atende reverse(title) LIKE 'Y%' (reescrita do sufixo como prefixo)
    "idx_movie_title_reverse": "CREATE INDEX idx_movie_title_reverse ON movie (reverse(title) text_pattern_ops)",
}


def lit(s):
    return "'" + s.replace("'", "''") + "'"


def consultas(p):
    x = p["movie_letra_prefixo"]
    y = p["movie_letra_sufixo"]
    return {
        "prefixo_like": f"SELECT * FROM movie WHERE title LIKE {lit(x + '%')}",
        "prefixo_substr": f"SELECT * FROM movie WHERE substr(title, 1, 1) = {lit(x)}",
        "sufixo_like": f"SELECT * FROM movie WHERE title LIKE {lit('%' + y)}",
        "sufixo_reverse": f"SELECT * FROM movie WHERE reverse(title) LIKE {lit(y + '%')}",
    }


def medir_todas(cur, qs):
    saida = {}
    for nome, sql in qs.items():
        plano = explain(cur, sql)
        saida[nome] = {
            "sql": sql,
            "linhas": plano["Plan"]["Actual Rows"],
            "nos": tipos_de_no(plano),
            "custo": plano["Plan"]["Total Cost"],
        }
    return saida


def main():
    p = carregar()
    qs = consultas(p)

    with conectar() as con, con.cursor() as cur:
        # garante o estado "antes" mesmo se o programa for reexecutado
        for nome in INDICES:
            cur.execute(f"DROP INDEX IF EXISTS {nome}")
        cur.execute("ANALYZE movie")
        antes = medir_todas(cur, qs)

        for ddl in INDICES.values():
            cur.execute(ddl)
        # ANALYZE coleta estatisticas das expressoes indexadas (substr, reverse),
        # necessarias para o planejador estimar corretamente essas consultas
        cur.execute("ANALYZE movie")
        depois = medir_todas(cur, qs)

    salvar("t15", {"antes": antes, "depois": depois, "indices_criados": dict(INDICES)})


if __name__ == "__main__":
    main()
