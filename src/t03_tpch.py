"""T3 — TPC-H carregado.

Registre em resultados/t03.json:
  sf, tabelas: {<tabela>: {linhas, bytes_tabela, bytes_total}} para as 8 tabelas do TPC-H.
(A carga em si e feita por 'make load'; aqui se confere e documenta o que foi carregado.)
"""
from common import conectar, salvar  # noqa: F401
from params import carregar  # noqa: F401

TABELAS = ["region", "nation", "part", "supplier",
           "partsupp", "customer", "orders", "lineitem"]

# Linhas por fator de escala no TPC-H (region e nation sao fixas).
LINHAS_POR_SF = {"part": 200_000, "supplier": 10_000, "partsupp": 800_000,
                 "customer": 150_000, "orders": 1_500_000}
LINHAS_FIXAS = {"region": 5, "nation": 25}

NOMES_SF = ("sf", "fator_escala", "scale_factor", "tpch_sf", "escala")


def _como_dict(p):
    return p if isinstance(p, dict) else vars(p)


def sf_dos_parametros(p):
    """Procura o fator de escala em params.json (no topo ou em um nivel de aninhamento)."""
    d = _como_dict(p)
    for nome in NOMES_SF:
        if nome in d:
            return d[nome]
    for valor in d.values():
        if isinstance(valor, dict):
            for nome in NOMES_SF:
                if nome in valor:
                    return valor[nome]
    return None


def main():
    p = carregar()
    conn = conectar()
    try:
        tabelas = {}
        with conn.cursor() as cur:
            for t in TABELAS:
                cur.execute(f"SELECT count(*) FROM {t}")
                linhas = int(cur.fetchone()[0])
                cur.execute(f"SELECT pg_relation_size('{t}'), pg_total_relation_size('{t}')")
                b_tab, b_tot = cur.fetchone()
                tabelas[t] = {
                    "linhas": linhas,
                    "bytes_tabela": int(b_tab),
                    "bytes_total": int(b_tot),
                }
    finally:
        conn.close()

    sf = sf_dos_parametros(p)
    if sf is None:  # fallback: deduz do banco (customer tem 150.000 * sf linhas)
        sf = tabelas["customer"]["linhas"] / LINHAS_POR_SF["customer"]
        print(f"aviso: fator de escala nao encontrado em params; deduzido do banco: {sf}")

    # Conferencia com a especificacao do TPC-H
    for t, n in LINHAS_FIXAS.items():
        assert tabelas[t]["linhas"] == n, f"{t}: esperado {n}, encontrado {tabelas[t]['linhas']}"
    for t, por_sf in LINHAS_POR_SF.items():
        esperado = round(por_sf * float(sf))
        achado = tabelas[t]["linhas"]
        if achado != esperado:
            print(f"aviso: {t} tem {achado} linhas; a especificacao preve {esperado} para sf={sf}")
    # lineitem tem ~4 linhas por pedido (varia de 1 a 7); nao ha valor exato fixo

    salvar("t03", {"sf": sf, "tabelas": tabelas})
    print("t03 ok: sf =", sf)
    for t, d in tabelas.items():
        print(f"  {t:9s} {d['linhas']:>10,d} linhas  {d['bytes_total']/2**20:9.1f} MiB")


if __name__ == "__main__":
    main()

