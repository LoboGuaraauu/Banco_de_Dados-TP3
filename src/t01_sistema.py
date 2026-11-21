"""T1 — Identificacao do sistema.

Registre em resultados/t01.json (use common.salvar("t01", {...})):
  cpu_modelo, cpu_nucleos, ram_mb, disco_bytes, caches (dict), so, kernel,
  postgres: {server_version, block_size, shared_buffers, effective_cache_size,
             seq_page_cost, random_page_cost, work_mem, default_statistics_target}
Os valores de 'postgres' devem ser os de SHOW <parametro>. Execute dentro do contêiner.
"""
import glob
import os
import platform
import re
import shutil
import subprocess

from common import conectar, salvar  # noqa: F401
from params import carregar  # noqa: F401

PARAMS_PG = [
    "server_version",
    "block_size",
    "shared_buffers",
    "effective_cache_size",
    "seq_page_cost",
    "random_page_cost",
    "work_mem",
    "default_statistics_target",
]


def _ler(caminho):
    try:
        with open(caminho, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def _lscpu():
    """Saida do lscpu como dict {campo: valor} (vazio se indisponivel)."""
    try:
        saida = subprocess.check_output(["lscpu"], text=True, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.CalledProcessError):
        return {}
    campos = {}
    for linha in saida.splitlines():
        if ":" in linha:
            chave, valor = linha.split(":", 1)
            campos[chave.strip()] = valor.strip()
    return campos


def cpu_modelo(lscpu):
    for linha in _ler("/proc/cpuinfo").splitlines():
        if linha.lower().startswith("model name"):
            return linha.split(":", 1)[1].strip()
    # Em ARM /proc/cpuinfo nao traz 'model name'; o lscpu traz.
    if lscpu.get("Model name"):
        return lscpu["Model name"]
    return platform.processor() or platform.machine()


def cpu_nucleos():
    return os.cpu_count()


def ram_mb():
    m = re.search(r"MemTotal:\s+(\d+)\s*kB", _ler("/proc/meminfo"))
    return int(m.group(1)) // 1024 if m else None


def disco_bytes():
    alvo = "/app" if os.path.exists("/app") else "/"
    return shutil.disk_usage(alvo).total


def caches(lscpu):
    """Caches da CPU: {'L1d': '32K', 'L1i': '32K', 'L2': '1024K', 'L3': '32768K'}.

    Le /sys/devices/system/cpu/cpu0/cache; se nao existir (comum em VMs de
    Docker Desktop), usa o lscpu.
    """
    res = {}
    for d in sorted(glob.glob("/sys/devices/system/cpu/cpu0/cache/index*")):
        nivel = _ler(os.path.join(d, "level")).strip()
        tipo = _ler(os.path.join(d, "type")).strip()
        tam = _ler(os.path.join(d, "size")).strip()
        if not (nivel and tam):
            continue
        sufixo = {"Data": "d", "Instruction": "i"}.get(tipo, "")
        res[f"L{nivel}{sufixo}"] = tam
    if res:
        return res
    for chave, valor in lscpu.items():
        m = re.fullmatch(r"(L\d[di]?) cache", chave)
        if m:
            res[m.group(1)] = valor
    return res


def so():
    for linha in _ler("/etc/os-release").splitlines():
        if linha.startswith("PRETTY_NAME="):
            return linha.split("=", 1)[1].strip().strip('"')
    return platform.platform()


def parametros_postgres(conn):
    res = {}
    with conn.cursor() as cur:
        for nome in PARAMS_PG:
            cur.execute(f"SHOW {nome}")
            res[nome] = cur.fetchone()[0]
    return res


def main():
    p = carregar()  # noqa: F841 (nao ha parametro individual nesta tarefa)
    conn = conectar()
    try:
        lscpu = _lscpu()
        resultado = {
            "cpu_modelo": cpu_modelo(lscpu),
            "cpu_nucleos": cpu_nucleos(),
            "ram_mb": ram_mb(),
            "disco_bytes": disco_bytes(),
            "caches": caches(lscpu),
            "so": so(),
            "kernel": platform.release(),
            "postgres": parametros_postgres(conn),
        }
    finally:
        conn.close()
    salvar("t01", resultado)
    print("t01 ok:", resultado)


if __name__ == "__main__":
    main()
