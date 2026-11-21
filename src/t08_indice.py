"""T8 — Indice em v.

Para n = 100.000 e n = 1.000.000 (recriando t com a mesma seed) registre em resultados/t08.json
uma lista de dicts: n, valor, tempo_consulta_ms, no_raiz_consulta, tempo_criacao_ms, tempo_recriacao_ms,
indice: {paginas, altura, paginas_folha, densidade_media_folha}.
Use SET max_parallel_maintenance_workers = 0 para tornar a construcao do indice reprodutivel.
"""
from common import conectar, salvar
from indice_util import (NOME_IDX, caracteristicas_indice, criar_indice, medir_consulta,
                         recriar_indice, recriar_t, valor_consulta)
from params import carregar


def main():
    p = carregar()
    valor = valor_consulta(p)
    resultados = []
    with conectar() as con, con.cursor() as cur:
        cur.execute("SET max_parallel_maintenance_workers = 0")
        for n in (100_000, 1_000_000):
            recriar_t(cur, n, p)
            tempo_criacao = criar_indice(cur)
            indice = caracteristicas_indice(cur)
            normal = medir_consulta(cur, valor)                       # plano escolhido pelo otimizador
            forcada = medir_consulta(cur, valor, forcar_indice=True)  # seqscan desligado (apoio a analise)
            tempo_recriacao = recriar_indice(cur)                     # REINDEX do mesmo indice
            resultados.append({
                "n": n,
                "valor": valor,
                "tempo_consulta_ms": normal["tempo_ms"],
                "no_raiz_consulta": normal["no_raiz"],
                "tempo_consulta_indice_forcado_ms": forcada["tempo_ms"],
                "tempo_criacao_ms": tempo_criacao,
                "tempo_recriacao_ms": tempo_recriacao,
                "indice": indice,
            })
            print(f"n={n}: {indice}")
        cur.execute(f"DROP INDEX IF EXISTS {NOME_IDX}")
    salvar("t08", resultados)


if __name__ == "__main__":
    main()
