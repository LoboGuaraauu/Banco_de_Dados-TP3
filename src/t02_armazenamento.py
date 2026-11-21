"""T2 — Armazenamento.

Registre em resultados/t02.json:
  fs_bloco_fundamental  (stat -f -c %S /app), fs_bloco_io_stat (stat -c %o /app),
  pg_block_size (SHOW block_size),
  leitura: {seq_mb_s, aleatorio_iops, razao_custo_aleatorio_sequencial}
A medicao compara leitura sequencial e aleatoria de blocos de 8 KB num arquivo seu.
No relatorio: como alterar o tamanho de bloco (sistema de arquivos e PostgreSQL) e por que
os numeros medidos no contêiner nao sao comparaveis entre maquinas.
"""
import os
import random
import subprocess
import tempfile
import time

from common import conectar, salvar  # noqa: F401
from params import carregar  # noqa: F401

ALVO = "/app" if os.path.isdir("/app") else os.getcwd()  # no contêiner, /app
BLOCO = 8192                                              # mesmo tamanho de pagina do PostgreSQL
ARQUIVO_MB = int(os.environ.get("T2_ARQUIVO_MB", "256"))  # maior que o cache do contêiner/CPU
N_ALEATORIOS = int(os.environ.get("T2_N_ALEATORIOS", "20000"))
SEMENTE = 42


def stat_int(*args):
    """Executa `stat <args> /app` e devolve o inteiro impresso."""
    saida = subprocess.check_output(["stat", *args, ALVO], text=True)
    return int(saida.strip())


def pg_block_size():
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("SHOW block_size")
            return int(cur.fetchone()[0])
    finally:
        conn.close()


def criar_arquivo(nblocos):
    """Cria arquivo com dados aleatorios (nao esparso) e devolve o caminho."""
    try:
        fd, caminho = tempfile.mkstemp(prefix=".t02_", suffix=".bin", dir=ALVO)
    except OSError:  # /app indisponivel ou somente leitura
        fd, caminho = tempfile.mkstemp(prefix=".t02_", suffix=".bin")
    with os.fdopen(fd, "wb") as f:
        restante = nblocos * BLOCO
        while restante > 0:
            n = min(restante, 1 << 20)
            f.write(os.urandom(n))
            restante -= n
        f.flush()
        os.fsync(f.fileno())
    return caminho


def esvaziar_cache(fd):
    """Remove do page cache as paginas do arquivo, para que a leitura va ao disco."""
    os.fsync(fd)
    os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)


def ler_sequencial(fd, nblocos):
    esvaziar_cache(fd)
    t0 = time.perf_counter()
    for i in range(nblocos):
        os.pread(fd, BLOCO, i * BLOCO)
    return time.perf_counter() - t0


def ler_aleatorio(fd, nblocos, n):
    esvaziar_cache(fd)
    rnd = random.Random(SEMENTE)
    blocos = rnd.sample(range(nblocos), n)  # sem repeticao: nenhum bloco lido duas vezes
    t0 = time.perf_counter()
    for b in blocos:
        os.pread(fd, BLOCO, b * BLOCO)
    return time.perf_counter() - t0


def medir_leitura():
    nblocos = ARQUIVO_MB * 1024 * 1024 // BLOCO
    n_alea = min(N_ALEATORIOS, nblocos)
    caminho = criar_arquivo(nblocos)
    try:
        fd = os.open(caminho, os.O_RDONLY)
        try:
            t_seq = ler_sequencial(fd, nblocos)
            t_alea = ler_aleatorio(fd, nblocos, n_alea)
        finally:
            os.close(fd)
    finally:
        os.unlink(caminho)

    seq_mb_s = (nblocos * BLOCO / (1024 * 1024)) / t_seq
    aleatorio_iops = n_alea / t_alea
    custo_seq_bloco = t_seq / nblocos       # s por bloco, leitura sequencial
    custo_alea_bloco = t_alea / n_alea      # s por bloco, leitura aleatoria
    return {
        "seq_mb_s": round(seq_mb_s, 2),
        "aleatorio_iops": round(aleatorio_iops, 2),
        "razao_custo_aleatorio_sequencial": round(custo_alea_bloco / custo_seq_bloco, 2),
        # detalhes para a discussao no relatorio
        "detalhes": {
            "bloco_bytes": BLOCO,
            "arquivo_mb": ARQUIVO_MB,
            "blocos_sequenciais": nblocos,
            "blocos_aleatorios": n_alea,
            "tempo_seq_s": round(t_seq, 4),
            "tempo_aleatorio_s": round(t_alea, 4),
            "us_por_bloco_seq": round(custo_seq_bloco * 1e6, 3),
            "us_por_bloco_aleatorio": round(custo_alea_bloco * 1e6, 3),
        },
    }


def main():
    p = carregar()  # noqa: F841 (nao ha parametro individual nesta tarefa)
    resultado = {
        "fs_bloco_fundamental": stat_int("-f", "-c", "%S"),
        "fs_bloco_io_stat": stat_int("-c", "%o"),
        "pg_block_size": pg_block_size(),
        "leitura": medir_leitura(),
    }
    salvar("t02", resultado)
    print("t02 ok:", resultado)


if __name__ == "__main__":
    main()
