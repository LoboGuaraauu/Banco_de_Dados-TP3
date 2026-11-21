"""T10 — Indice descendente.

Repita T9 com CREATE INDEX ... ON t(v DESC NULLS FIRST) e fillfactors [100] + params['fillfactors'].
resultados/t10.json: mesmo formato de t09.
"""
from common import conectar, salvar
from indice_util import experimento_fillfactor
from params import carregar


def main():
    p = carregar()
    fillfactors = [100] + [f for f in p["fillfactors"] if f != 100]   # sem duplicar o 100
    with conectar() as con, con.cursor() as cur:
        resultados = experimento_fillfactor(cur, p, fillfactors, desc=True)
    salvar("t10", resultados)


if __name__ == "__main__":
    main()
