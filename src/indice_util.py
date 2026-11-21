"""Apoio comum a T8, T9 e T10 (tabela t de 100k/1M tuplas, indice sobre v, medicoes).

Camada fina sobre src/tabela_t.py (fornecido pelo template): a criacao de t, a medicao de tempos e as
caracteristicas do indice vêm de la; aqui ficam apenas as partes especificas de T8-T10 (nome do indice,
DESC/fillfactor, REINDEX, consulta de igualdade e forcar o uso do indice).
"""
from common import explain
from tabela_t import criar_t, info_indice, tempo, tempo_consulta

NOME_IDX = "idx_t_v"
REPETICOES = 5          # execucoes medidas da consulta (apos 1 de aquecimento); reporta-se a mediana


def valor_consulta(p):
    """Valor de v usado na consulta de igualdade (existe sempre: C <= 100 e n >= 100.000)."""
    return int(p["t_cardinalidade_v"]) // 2


def recriar_t(cur, n, p):
    """Recria t(k serial pk, v int) com n tuplas, v = trunc(random()*C), seed individual."""
    criar_t(cur, int(n), float(p["t_seed"]), int(p["t_cardinalidade_v"]))


def criar_indice(cur, desc=False, fillfactor=None):
    """Cria idx_t_v sobre t(v) e devolve o tempo de criacao em ms."""
    cur.execute(f"DROP INDEX IF EXISTS {NOME_IDX}")
    ordem = " DESC NULLS FIRST" if desc else ""
    com = f" WITH (fillfactor = {int(fillfactor)})" if fillfactor is not None else ""
    return tempo(cur, f"CREATE INDEX {NOME_IDX} ON t (v{ordem}){com}")


def recriar_indice(cur):
    """REINDEX do indice existente (mantem as opcoes, ex.: fillfactor); devolve ms."""
    return tempo(cur, f"REINDEX INDEX {NOME_IDX}")


def caracteristicas_indice(cur):
    """paginas (inclui metapagina), altura (nivel da raiz; 0 = raiz e folha), paginas_folha,
    densidade_media_folha (% de ocupacao das folhas, via pgstatindex)."""
    info = info_indice(cur, NOME_IDX)
    return {
        "paginas": int(info["paginas"]),
        "altura": int(info["altura"]),
        "niveis": int(info["altura"]) + 1,          # altura contada em niveis (raiz folha = 1)
        "paginas_folha": int(info["paginas_folha"]),
        "densidade_media_folha": float(info["densidade_media_folha"]),
    }


def medir_consulta(cur, valor, forcar_indice=False):
    """Mediana do Execution Time (ms) de SELECT * FROM t WHERE v = valor, e no raiz do plano.
    forcar_indice=True desliga seqscan para medir o caminho pelo indice mesmo quando o
    planejador preferiria varrer a tabela (com C pequeno, v = x devolve n/C tuplas)."""
    sql = f"SELECT * FROM t WHERE v = {int(valor)}"
    if forcar_indice:
        cur.execute("SET enable_seqscan = off")
    try:
        explain(cur, sql)                                       # aquecimento (cache, hint bits)
        tempo_ms = tempo_consulta(cur, sql, REPETICOES)         # mediana (tabela_t)
        no_raiz = explain(cur, sql, analyze=False)["Plan"]["Node Type"]
    finally:
        if forcar_indice:
            cur.execute("RESET enable_seqscan")
    return {"tempo_ms": tempo_ms, "no_raiz": no_raiz}


def experimento_fillfactor(cur, p, fillfactors, desc):
    """Com t de 1.000.000 de tuplas, cria o indice para cada fillfactor e mede."""
    cur.execute("SET max_parallel_maintenance_workers = 0")
    recriar_t(cur, 1_000_000, p)
    valor = valor_consulta(p)
    saida = []
    for ff in fillfactors:
        tempo_criacao = criar_indice(cur, desc=desc, fillfactor=ff)
        indice = caracteristicas_indice(cur)
        normal = medir_consulta(cur, valor)
        forcada = medir_consulta(cur, valor, forcar_indice=True)
        saida.append({
            "fillfactor": ff,
            "tempo_criacao_ms": tempo_criacao,
            "tempo_consulta_ms": normal["tempo_ms"],
            "no_raiz_consulta": normal["no_raiz"],
            "tempo_consulta_indice_forcado_ms": forcada["tempo_ms"],
            "valor": valor,
            "indice": indice,
        })
        print(f"fillfactor={ff}: {indice}")
    cur.execute(f"DROP INDEX IF EXISTS {NOME_IDX}")
    return saida