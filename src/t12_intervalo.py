"""T12 — Consultas por intervalo em movie.votes.

Escreva uma consulta seletiva (< 10 tuplas, usando params['movie_votos_alto']) e uma nao seletiva (> 80% das tuplas,
usando params['movie_votos_baixo']). resultados/t12.json:
  pequena e grande: {sql, linhas, nos, custo, tempo_ms, buffers},
  limiar_votos_menor_que (menor X, em passos de 50, tal que 'votes < X' passa a usar Seq Scan),
  linhas_no_limiar, fracao_no_limiar.
No relatorio: por que o indice sobre votes nao e sempre usado.
"""
from common import conectar, salvar, explain, tipos_de_no
from params import carregar
from util_plano import medir_sql

PASSO = 50


def contar(cur, predicado):
    cur.execute(f"SELECT count(*) FROM movie WHERE {predicado}")
    return cur.fetchone()[0]


def escolher(cur, predicados, aceita, descricao):
    """Primeiro predicado (na ordem dada) cuja contagem satisfaz 'aceita'."""
    contagens = []
    for pred in predicados:
        n = contar(cur, pred)
        contagens.append((pred, n))
        if aceita(n):
            return pred
    raise RuntimeError(f"nenhum predicado atende a condicao '{descricao}': {contagens}")


def usa_seq_scan(cur, x):
    plano = explain(cur, f"SELECT * FROM movie WHERE votes < {x}", analyze=False)
    nos = tipos_de_no(plano)
    return any("Seq Scan" in t for t in nos), nos


def main():
    p = carregar()
    alto, baixo = int(p["movie_votos_alto"]), int(p["movie_votos_baixo"])
    with conectar() as con, con.cursor() as cur:
        cur.execute("SELECT count(*), max(votes) FROM movie")
        total, max_votes = cur.fetchone()

        # consulta seletiva (< 10 tuplas); prefere resultado nao vazio
        cand_pequena = [f"votes > {alto}", f"votes >= {alto}"]
        try:
            pred_pequena = escolher(cur, cand_pequena, lambda n: 0 < n < 10, "1 a 9 tuplas")
        except RuntimeError:
            pred_pequena = escolher(cur, cand_pequena, lambda n: n < 10, "menos de 10 tuplas")
        # consulta nao seletiva (> 80% das tuplas)
        pred_grande = escolher(cur, [f"votes > {baixo}", f"votes >= {baixo}"],
                               lambda n: n > 0.8 * total, "mais de 80% das tuplas")

        pequena = medir_sql(cur, f"SELECT * FROM movie WHERE {pred_pequena}")
        grande = medir_sql(cur, f"SELECT * FROM movie WHERE {pred_grande}")

        # menor X (multiplo de PASSO) tal que 'votes < X' usa Seq Scan: busca binaria + ajuste linear
        lo, hi = 1, int(max_votes) // PASSO + 2          # X = PASSO * k; para k = hi todas as linhas casam
        seq_hi, _ = usa_seq_scan(cur, PASSO * hi)
        if not seq_hi:
            raise RuntimeError("votes < X nao usa Seq Scan nem selecionando todas as linhas")
        while lo < hi:
            meio = (lo + hi) // 2
            if usa_seq_scan(cur, PASSO * meio)[0]:
                hi = meio
            else:
                lo = meio + 1
        k = lo
        while k > 1 and usa_seq_scan(cur, PASSO * (k - 1))[0]:   # garante o menor, se nao monotono
            k -= 1
        limiar = PASSO * k
        linhas_limiar = contar(cur, f"votes < {limiar}")
        _, nos_limiar = usa_seq_scan(cur, limiar)
        _, nos_antes = usa_seq_scan(cur, limiar - PASSO)

    salvar("t12", {
        "pequena": pequena,
        "grande": grande,
        "limiar_votos_menor_que": limiar,
        "linhas_no_limiar": linhas_limiar,
        "fracao_no_limiar": linhas_limiar / total,
        "total_linhas": total,
        "passo": PASSO,
        "nos_no_limiar": nos_limiar,
        "nos_antes_do_limiar": nos_antes,
    })


if __name__ == "__main__":
    main()
