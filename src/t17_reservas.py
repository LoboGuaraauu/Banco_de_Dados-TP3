"""T17–T19 — Reserva de assentos.

Implemente as versoes a (um unico BEGIN/COMMIT para os 3 passos) e b (transacao para o passo 1, passo 2 fora
de transacao, transacao para o passo 3). Tabela assentos(num_voo, disp) com params['assentos'] linhas, k agentes
(params['agentes']), niveis READ COMMITTED e SERIALIZABLE, espera de params['tempo_escolha_s'] no passo 2.
Grave cada reserva em reservas_log(config, cliente, assento, tentativas), com config = '<versao>/<isolamento>/k=<k>'
(isolamento: read_committed | serializable). resultados/t17.json:
  {assentos, tempo_escolha_s, experimentos: [{versao, isolamento, k, tempo_total_s, reservas,
   tentativas_max, tentativas_min, tentativas_media}]}
e um grafico por (versao, isolamento): resultados/t18_<versao>_<isolamento>.png (k x tempo total).
Um assento nunca pode ser reservado duas vezes.
"""
import queue
import random
import threading
import time

import psycopg
from psycopg import IsolationLevel

from common import RESULTADOS, conectar, salvar
from params import carregar

ISOLAMENTOS = {
    "read_committed": IsolationLevel.READ_COMMITTED,
    "serializable": IsolationLevel.SERIALIZABLE,
}
VERSOES = ["a", "b"]
BACKOFF_MAX_S = 0.010


def preparar_tabelas():
    with conectar() as con, con.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS reservas_log")
        cur.execute("DROP TABLE IF EXISTS assentos")
        cur.execute("CREATE TABLE assentos (num_voo integer PRIMARY KEY, disp boolean NOT NULL DEFAULT true)")
        cur.execute("CREATE TABLE reservas_log (config text, cliente integer, assento integer, tentativas integer)")


def reiniciar_assentos(n):
    with conectar() as con, con.cursor() as cur:
        cur.execute("TRUNCATE assentos")
        cur.execute("INSERT INTO assentos (num_voo, disp) SELECT g, true FROM generate_series(1, %s) g", (n,))


def _listar_livres(cur):
    cur.execute("SELECT num_voo FROM assentos WHERE disp ORDER BY num_voo")
    return [r[0] for r in cur.fetchall()]


def _gravar(con, cur, config, cliente, assento, tentativas):
    """Passo 3: marca o assento como indisponivel e registra no log. False se o assento ja foi tomado."""
    cur.execute("UPDATE assentos SET disp = false WHERE num_voo = %s AND disp", (assento,))
    if cur.rowcount != 1:
        con.rollback()
        return False
    cur.execute("INSERT INTO reservas_log (config, cliente, assento, tentativas) VALUES (%s, %s, %s, %s)",
                (config, cliente, assento, tentativas))
    con.commit()
    return True


def tentar_a(con, rng, espera, config, cliente, tentativas):
    """Versao a: passos 1, 2 e 3 dentro de uma unica transacao."""
    cur = con.cursor()
    livres = _listar_livres(cur)                    # passo 1 (abre a transacao)
    if not livres:
        con.rollback()
        return False
    assento = rng.choice(livres)                    # passo 2
    time.sleep(espera)
    return _gravar(con, cur, config, cliente, assento, tentativas)   # passo 3 + COMMIT


def tentar_b(con, rng, espera, config, cliente, tentativas):
    """Versao b: transacao para o passo 1, passo 2 fora de transacao, transacao para o passo 3."""
    cur = con.cursor()
    livres = _listar_livres(cur)                    # passo 1
    con.commit()                                    # fim da transacao do passo 1
    if not livres:
        return False
    assento = rng.choice(livres)                    # passo 2: sem transacao aberta
    time.sleep(espera)
    return _gravar(con, cur, config, cliente, assento, tentativas)   # passo 3 (nova transacao)


def agente(versao, isolamento, config, fila, espera, barreira, erros, seed):
    rng = random.Random(seed)
    tentar = tentar_a if versao == "a" else tentar_b
    try:
        con = conectar(autocommit=False)
        con.isolation_level = ISOLAMENTOS[isolamento]
    except Exception as e:  # noqa: BLE001
        erros.append(e)
        barreira.abort()
        return
    try:
        barreira.wait()
        while True:
            try:
                cliente = fila.get_nowait()
            except queue.Empty:
                break
            tentativas = 0
            while True:
                tentativas += 1
                try:
                    ok = tentar(con, rng, espera, config, cliente, tentativas)
                except psycopg.Error as e:
                    # classe 40 = rollback de transacao (40001 serializacao, 40P01 deadlock); em psycopg 3
                    # essas excecoes nao tem um pai comum alem de OperationalError, entao testa-se o SQLSTATE.
                    # A falha pode vir do COMMIT (ex.: "pivot" do SSI), ja dentro de tentar().
                    if not (e.sqlstate or "").startswith("40"):
                        raise
                    con.rollback()
                    ok = False
                if ok:
                    break
                time.sleep(rng.uniform(0, BACKOFF_MAX_S))
    except threading.BrokenBarrierError:
        pass
    except Exception as e:  # noqa: BLE001
        erros.append(e)
    finally:
        con.close()


def executar(versao, isolamento, k, n, espera):
    config = f"{versao}/{isolamento}/k={k}"
    reiniciar_assentos(n)
    fila = queue.Queue()
    for c in range(1, n + 1):
        fila.put(c)
    barreira = threading.Barrier(k + 1)
    erros = []
    threads = [threading.Thread(target=agente,
                                args=(versao, isolamento, config, fila, espera, barreira, erros, 1000 * k + i))
               for i in range(k)]
    for t in threads:
        t.start()
    try:
        barreira.wait()                              # todos os agentes conectados
    except threading.BrokenBarrierError:
        pass
    t0 = time.perf_counter()
    for t in threads:
        t.join()
    total = time.perf_counter() - t0
    if erros:
        raise RuntimeError(f"{config}: erro em agente: {erros[0]!r}")

    # confere a integridade e resume a partir do proprio log
    with conectar() as con, con.cursor() as cur:
        cur.execute("""SELECT count(*), count(DISTINCT assento), count(DISTINCT cliente),
                              max(tentativas), min(tentativas), avg(tentativas)
                       FROM reservas_log WHERE config = %s""", (config,))
        reservas, assentos_distintos, clientes, tmax, tmin, tmed = cur.fetchone()
        cur.execute("SELECT count(*) FROM assentos WHERE disp")
        livres = cur.fetchone()[0]
    if not (reservas == assentos_distintos == clientes == n and livres == 0):
        raise RuntimeError(f"{config}: inconsistencia (reservas={reservas}, assentos distintos="
                           f"{assentos_distintos}, clientes={clientes}, assentos livres={livres})")
    print(f"{config}: {total:.2f}s, tentativas max={tmax} media={float(tmed):.2f}")
    return {"versao": versao, "isolamento": isolamento, "k": k, "tempo_total_s": round(total, 3),
            "reservas": reservas, "tentativas_max": tmax, "tentativas_min": tmin,
            "tentativas_media": round(float(tmed), 4)}


def grafico(versao, isolamento, exps):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    pontos = sorted((e["k"], e["tempo_total_s"]) for e in exps
                    if e["versao"] == versao and e["isolamento"] == isolamento)
    ks, ts = zip(*pontos)
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(ks, ts, marker="o")
    ax.set_xlabel("número de agentes (k)")
    ax.set_ylabel("tempo total (s)")
    ax.set_title(f"Reservas — versão {versao}, {isolamento.replace('_', ' ').upper()}")
    ax.set_xticks(list(ks))
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    RESULTADOS.mkdir(exist_ok=True)
    caminho = RESULTADOS / f"t18_{versao}_{isolamento}.png"
    fig.savefig(caminho, dpi=150)
    plt.close(fig)
    print(f"gravado {caminho}")


def main():
    p = carregar()
    n = p["assentos"]
    espera = p["tempo_escolha_s"]
    preparar_tabelas()

    experimentos = []
    for versao in VERSOES:
        for isolamento in ISOLAMENTOS:
            for k in p["agentes"]:
                experimentos.append(executar(versao, isolamento, k, n, espera))

    salvar("t17", {"assentos": n, "tempo_escolha_s": espera, "experimentos": experimentos})
    for versao in VERSOES:
        for isolamento in ISOLAMENTOS:
            grafico(versao, isolamento, experimentos)


if __name__ == "__main__":
    main()