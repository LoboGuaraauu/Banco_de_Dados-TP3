"""T5 — Tabela t.

Crie t(k serial primary key, v integer) com 100.000 tuplas, v = trunc(random() * t_cardinalidade_v),
chamando SELECT setseed(t_seed) antes do INSERT (valores em params.json).
Registre em resultados/t05.json: primeiras_10 (k, v ordenado por k), soma_v, tuplas.
"""
from common import conectar, salvar  # noqa: F401
from params import carregar  # noqa: F401

N_TUPLAS = 100_000


def main():
    p = carregar()
    seed = p["t_seed"]
    card = p["t_cardinalidade_v"]

    # Uma unica conexao: o estado de setseed() vale por sessao, e o INSERT
    # abaixo consome a sequencia de random() na ordem de generate_series.
    with conectar() as con, con.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS t CASCADE")
        cur.execute("CREATE TABLE t (k serial PRIMARY KEY, v integer)")
        cur.execute("SELECT setseed(%s::float8)", (seed,))
        cur.execute(
            "INSERT INTO t (v) SELECT trunc(random() * %s::int)::int "
            "FROM generate_series(1, %s)", (card, N_TUPLAS))

        cur.execute("SELECT k, v FROM t ORDER BY k LIMIT 10")
        primeiras_10 = [list(l) for l in cur.fetchall()]
        cur.execute("SELECT sum(v), count(*) FROM t")
        soma_v, tuplas = cur.fetchone()

    resultado = {
        "primeiras_10": primeiras_10,
        "soma_v": int(soma_v),
        "tuplas": int(tuplas),
    }
    salvar("t05", resultado)
    print(f"t05 ok: {tuplas} tuplas, soma_v={soma_v}, seed={seed}, C={card}")


if __name__ == "__main__":
    main()
