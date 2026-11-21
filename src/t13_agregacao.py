"""T13 — MAX x >= ALL.

Compare SELECT title FROM movie WHERE votes >= (SELECT MAX(votes) FROM movie) com
SELECT title FROM movie WHERE votes >= ALL (SELECT votes FROM movie).
resultados/t13.json: chaves 'max' e 'all', cada uma {sql, resultado, nos, custo, tempo_ms}.
"""
from common import conectar, salvar
from params import carregar  # noqa: F401
from util_plano import medir_sql

SQL_MAX = "SELECT title FROM movie WHERE votes >= (SELECT MAX(votes) FROM movie)"
SQL_ALL = "SELECT title FROM movie WHERE votes >= ALL (SELECT votes FROM movie)"


def medir(cur, sql):
    cur.execute(sql)                                         # resultado (e aquecimento do cache)
    resultado = sorted((r[0] for r in cur.fetchall()), key=lambda t: (t is None, str(t)))
    m = medir_sql(cur, sql)
    return {"sql": sql, "resultado": resultado, "nos": m["nos"], "custo": m["custo"],
            "tempo_ms": m["tempo_ms"]}


def main():
    carregar()
    with conectar() as con, con.cursor() as cur:
        r_max = medir(cur, SQL_MAX)
        r_all = medir(cur, SQL_ALL)
    print("resultados iguais:", r_max["resultado"] == r_all["resultado"])
    salvar("t13", {"max": r_max, "all": r_all})


if __name__ == "__main__":
    main()
