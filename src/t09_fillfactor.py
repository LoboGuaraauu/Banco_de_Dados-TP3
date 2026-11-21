"""T9 — Fillfactor do indice.

Com t de 1.000.000 tuplas, para cada fillfactor em params['fillfactors'] crie o indice com esse fillfactor.
resultados/t09.json: lista de {fillfactor, tempo_criacao_ms, tempo_consulta_ms, indice:{paginas, altura, paginas_folha, densidade_media_folha}}.
"""
from common import conectar, salvar
from indice_util import experimento_fillfactor
from params import carregar


def main():
    p = carregar()
    with conectar() as con, con.cursor() as cur:
        resultados = experimento_fillfactor(cur, p, p["fillfactors"], desc=False)
    salvar("t09", resultados)


if __name__ == "__main__":
    main()
