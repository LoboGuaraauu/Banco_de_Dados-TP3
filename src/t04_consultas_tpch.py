"""T4 — Consultas TPC-H com EXPLAIN (ANALYZE, BUFFERS).

Para cada consulta de queries/tpch_aluno/qNN.sql registre em resultados/t04.json, chave 'qNN':
  nos (tipos de no do plano), custo_estimado, linhas_estimadas, linhas_reais,
  buffers {hit, read}, tempo_execucao_ms, acesso_dominante.
No relatorio: comente o tipo de acesso de cada consulta (varredura sequencial, indice, junção hash...).
"""
import json
import re
from pathlib import Path

from common import conectar, salvar  # noqa: F401
from params import carregar  # noqa: F401

RAIZ = Path(__file__).resolve().parent.parent
DIR_CONSULTAS = RAIZ / "queries" / "tpch_aluno"

# Nos que leem diretamente uma tabela (candidatos a 'acesso dominante').
# Bitmap Index Scan fica de fora: quem le a tabela e o Bitmap Heap Scan.
NOS_DE_ACESSO = {"Seq Scan", "Index Scan", "Index Only Scan", "Bitmap Heap Scan"}
NOS_DE_JUNCAO = {"Hash Join", "Merge Join", "Nested Loop"}


def ler_comandos(caminho):
    """Separa o arquivo .sql em comandos (remove comentarios; divide em ';')."""
    texto = caminho.read_text(encoding="utf-8")
    texto = re.sub(r"/\*.*?\*/", " ", texto, flags=re.S)
    texto = re.sub(r"--[^\n]*", " ", texto)
    return [c.strip() for c in texto.split(";") if c.strip()]


def e_consulta(cmd):
    return cmd.lstrip("( \n\t").lower().startswith(("select", "with"))


def separar(comandos, nome):
    """Devolve (preparo, consulta, limpeza).

    A consulta e o unico SELECT/WITH do arquivo; o que vem antes (p.ex. CREATE VIEW
    da Q15) e executado antes do EXPLAIN, e o que vem depois (DROP VIEW), ao final.
    """
    idx = [i for i, c in enumerate(comandos) if e_consulta(c)]
    if len(idx) != 1:
        raise RuntimeError(f"{nome}: esperava 1 consulta SELECT, encontrei {len(idx)}")
    i = idx[0]
    return comandos[:i], comandos[i], comandos[i + 1:]


def percorrer(no):
    """Percorre o plano em pre-ordem."""
    yield no
    for filho in no.get("Plans", []):
        yield from percorrer(filho)


def explain(cur, consulta):
    cur.execute(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {consulta}")
    bruto = cur.fetchone()[0]
    if isinstance(bruto, str):
        bruto = json.loads(bruto)
    return bruto[0]


def acesso_dominante(nos):
    """No de acesso a tabela que mais tempo consome (tempo total x iteracoes).

    Em caso de empate, o que produz mais linhas. Devolve (tipo, relacao).
    """
    candidatos = [n for n in nos if n["Node Type"] in NOS_DE_ACESSO]
    if not candidatos:
        return None, None
    melhor = max(
        candidatos,
        key=lambda n: (n.get("Actual Total Time", 0) * n.get("Actual Loops", 1),
                       n.get("Actual Rows", 0)),
    )
    return melhor["Node Type"], melhor.get("Relation Name")


def resumir(plano_json):
    raiz = plano_json["Plan"]
    nos = list(percorrer(raiz))
    tipos = list(dict.fromkeys(n["Node Type"] for n in nos))  # unicos, em pre-ordem
    tipo_dom, rel_dom = acesso_dominante(nos)
    return {
        "nos": tipos,
        "custo_estimado": raiz["Total Cost"],
        "linhas_estimadas": raiz["Plan Rows"],
        "linhas_reais": raiz["Actual Rows"],
        "buffers": {
            "hit": raiz.get("Shared Hit Blocks", 0),
            "read": raiz.get("Shared Read Blocks", 0),
        },
        "tempo_execucao_ms": plano_json["Execution Time"],
        "acesso_dominante": tipo_dom,
        # apoio para o relatorio
        "relacao_dominante": rel_dom,
        "juncoes": [n["Node Type"] for n in nos if n["Node Type"] in NOS_DE_JUNCAO],
        "tempo_planejamento_ms": plano_json.get("Planning Time"),
    }


def main():
    p = carregar()  # noqa: F841 (os parametros ja estao nos arquivos .sql gerados)
    arquivos = sorted(DIR_CONSULTAS.glob("q*.sql"))
    if not arquivos:
        raise FileNotFoundError(f"nenhuma consulta em {DIR_CONSULTAS}")

    conn = conectar()
    try:
        try:
            conn.autocommit = True  # DDL da Q15 (view) fica visivel e nao acumula transacao
        except Exception:
            pass
        resultado = {}
        with conn.cursor() as cur:
            for arq in arquivos:
                nome = arq.stem  # 'q01', 'q03', ...
                preparo, consulta, limpeza = separar(ler_comandos(arq), nome)
                try:
                    for cmd in preparo:
                        cur.execute(cmd)
                    resultado[nome] = resumir(explain(cur, consulta))
                except Exception as e:
                    raise RuntimeError(f"falha em {arq.name}: {e}") from e
                finally:
                    for cmd in limpeza:
                        cur.execute(cmd)
                r = resultado[nome]
                print(f"{nome}: {r['acesso_dominante']:<16} custo={r['custo_estimado']:>12.1f} "
                      f"est={r['linhas_estimadas']:>9} real={r['linhas_reais']:>9} "
                      f"read={r['buffers']['read']:>8} hit={r['buffers']['hit']:>8} "
                      f"{r['tempo_execucao_ms']:>10.1f} ms")
    finally:
        conn.close()

    salvar("t04", resultado)
    print(f"t04 ok: {len(resultado)} consultas")


if __name__ == "__main__":
    main()
