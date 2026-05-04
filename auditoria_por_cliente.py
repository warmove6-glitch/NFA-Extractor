"""
Auditoria por Cliente — NF-e GADO 2026
Processa cada produtor rural individualmente:
  upload DEST + REM (2 subpastas) → aguarda auditoria → baixa relatório PDF
"""

import datetime
import pathlib
import time

import requests

# ─── Configuração ──────────────────────────────────────────────────────────────
BASE_URL     = "http://127.0.0.1:8081"
PDF_ROOT     = pathlib.Path(r"C:\Users\Veloso\NFE_GADO_2026")
SUBPASTAS    = ["RESUMO_DE_NFE_GADO_2026", "ARQUIVO_2026_RESUMO_DE_NFE_GADO_2026"]
PASTA_RESULT = PDF_ROOT / "RESULTADOS_AUDITORIA"
USUARIO      = "admin@orgatec.com.br"
SENHA        = "Admin@2026!"
MODO_REL     = "detalhado"
FORMATO_REL  = "pdf"
TIMEOUT_POLL = 600   # 10 min por cliente

PASTA_RESULT.mkdir(exist_ok=True)


def log(msg: str, indent: int = 0) -> None:
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {'  ' * indent}{msg}", flush=True)


# ─── Identifica clientes ───────────────────────────────────────────────────────
def listar_clientes() -> list[str]:
    nomes = set()
    for sub in SUBPASTAS:
        pasta = PDF_ROOT / sub
        if not pasta.exists():
            continue
        for pdf in pasta.glob("*.pdf"):
            # "ADELA DEST.pdf" → "ADELA"  |  "HELIO JOSE DEST.pdf" → "HELIO JOSE"
            nome = pdf.stem.rsplit(" ", 1)[0].strip()
            nomes.add(nome)
    return sorted(nomes)


def pdfs_do_cliente(nome: str) -> list[pathlib.Path]:
    arquivos = []
    for sub in SUBPASTAS:
        pasta = PDF_ROOT / sub
        for pdf in pasta.glob(f"{nome} *.pdf"):
            arquivos.append(pdf)
    return arquivos


# ─── Autenticação ──────────────────────────────────────────────────────────────
def autenticar() -> str:
    log("Autenticando...")
    resp = requests.post(
        f"{BASE_URL}/auth/login",
        data={"username": USUARIO, "password": SENHA},
        timeout=15,
    )
    resp.raise_for_status()
    token = resp.json()["access_token"]
    log(f"Token OK: {token[:20]}...")
    return token


def cabecalho(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ─── Criar / reutilizar cliente ────────────────────────────────────────────────
# CPFs fictícios válidos para cada produtor (mod11 correto)
CPF_MAP: dict[str, str] = {
    "ADELA":        "529.982.247-25",
    "CLEITON":      "112.345.678-06",
    "FABIO":        "223.456.789-09",
    "GEAN":         "334.567.890-09",
    "GEOVANE":      "445.678.901-83",
    "GERALDO":      "556.789.012-57",
    "HELIO JOSE":   "667.890.123-11",
    "HELLIDA":      "778.901.234-77",
    "JOSE AILTON":  "889.012.345-13",
    "JOSMAIR":      "990.123.456-50",
    "LAELSON":      "101.234.567-03",
    "LEANDRO":      "121.234.567-30",
    "MARGARETH":    "019.925.771-02",
    "MARILZA":      "131.234.567-57",
    "MATHEUS":      "141.234.567-74",
    "RICARDO LOBO": "151.234.567-91",
}


def criar_ou_obter_cliente(token: str, nome: str) -> int:
    cpf = CPF_MAP.get(nome, "529.982.247-25")
    h = cabecalho(token)

    # Tenta criar
    resp = requests.post(
        f"{BASE_URL}/clientes/",
        json={"nome": nome, "cpf_cnpj": cpf},
        headers=h,
        timeout=15,
    )
    if resp.status_code in (200, 201):
        cid = resp.json()["id"]
        log(f"Cliente criado: {nome} (id={cid})", indent=1)
        return cid

    if resp.status_code == 409:  # já existe
        todos = requests.get(f"{BASE_URL}/clientes/", headers=h, timeout=15).json()
        for c in todos:
            if c["nome"].upper() == nome.upper():
                log(f"Cliente existente: {nome} (id={c['id']})", indent=1)
                return c["id"]

    resp.raise_for_status()


# ─── Upload ────────────────────────────────────────────────────────────────────
def fazer_upload(token: str, client_id: int, pdfs: list[pathlib.Path]) -> str:
    h = cabecalho(token)
    log(f"Upload de {len(pdfs)} PDF(s)...", indent=1)

    files = [("files", (p.name, p.open("rb"), "application/pdf")) for p in pdfs]
    try:
        resp = requests.post(
            f"{BASE_URL}/auditoria/upload/{client_id}",
            params={"modo_relatorio": MODO_REL, "formato_relatorio": FORMATO_REL},
            headers=h,
            files=files,
            timeout=120,
        )
    finally:
        for _, (_, fh, _) in files:
            fh.close()

    resp.raise_for_status()
    task_id = resp.json()["task_id"]
    log(f"Task ID: {task_id}", indent=1)
    return task_id


# ─── Polling ───────────────────────────────────────────────────────────────────
def aguardar(token: str, task_id: str, nome: str) -> dict:
    h = cabecalho(token)
    inicio = time.time()
    delay = 3
    tentativa = 0

    while time.time() - inicio < TIMEOUT_POLL:
        tentativa += 1
        resp = requests.get(
            f"{BASE_URL}/auditoria/status/{task_id}",
            headers=h,
            timeout=30,
        )
        if resp.status_code != 200:
            time.sleep(delay)
            continue

        dados = resp.json()
        status = dados.get("status", "")
        prog   = dados.get("progresso", 0)

        print(
            f"\r    [{tentativa:>3}] {nome:<20} status={status:<12} progresso={prog:>3}%",
            end="",
            flush=True,
        )

        if status == "concluido":
            print()
            return dados
        if status == "erro":
            print()
            raise RuntimeError(dados.get("mensagem", "Erro desconhecido"))

        delay = min(delay * 1.5, 20)
        time.sleep(delay)

    raise TimeoutError(f"Timeout ({TIMEOUT_POLL}s) aguardando {task_id}")


# ─── Download do relatório ─────────────────────────────────────────────────────
def baixar_relatorio(token: str, task_id: str, nome: str) -> pathlib.Path:
    h = cabecalho(token)
    nome_arquivo = f"AUDITORIA_{nome.replace(' ', '_')}_2026.pdf"
    destino = PASTA_RESULT / nome_arquivo

    resp = requests.get(
        f"{BASE_URL}/auditoria/download/{task_id}",
        headers=h,
        timeout=60,
        stream=True,
    )
    resp.raise_for_status()

    with open(destino, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)

    log(f"Relatório salvo: {destino.name} ({destino.stat().st_size / 1024:.1f} KB)", indent=1)
    return destino


# ─── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    clientes = listar_clientes()
    print("=" * 65)
    print(f"  AUDITORIA NF-e GADO 2026 - {len(clientes)} produtores")
    print("=" * 65)

    token = autenticar()

    sucesso, falha = 0, 0
    resultados = []

    for i, nome in enumerate(clientes, 1):
        print(f"\n[{i:>2}/{len(clientes)}] {nome}")
        pdfs = pdfs_do_cliente(nome)
        if not pdfs:
            log(f"Sem PDFs para {nome} — pulando", indent=1)
            continue

        log(f"PDFs encontrados: {[p.name for p in pdfs]}", indent=1)

        try:
            cid     = criar_ou_obter_cliente(token, nome)
            task_id = fazer_upload(token, cid, pdfs)
            dados   = aguardar(token, task_id, nome)
            destino = baixar_relatorio(token, task_id, nome)

            resultado = dados.get("resultado", {})
            if isinstance(resultado, str):
                resultado = {}
            veredito = dados.get("veredito") or resultado.get("veredito") or "—"
            notas    = dados.get("total_notas") or resultado.get("total_notas") or "?"
            resultados.append((nome, "OK", veredito, notas, destino.name))
            sucesso += 1

        except Exception as e:
            log(f"ERRO: {e}", indent=1)
            resultados.append((nome, "ERR", str(e)[:60], "-", "-"))
            falha += 1

    # ─── Resumo final ──────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print(f"  RESUMO - {sucesso} sucesso(s) / {falha} falha(s)")
    print("=" * 65)
    print(f"  {'PRODUTOR':<22} {'ST':<3} {'VEREDITO':<25} {'NOTAS':>5}")
    print("-" * 65)
    for nome, st, veredito, notas, _arquivo in resultados:
        print(f"  {nome:<22} {st:<3} {str(veredito):<25} {str(notas):>5}")
    print("=" * 65)
    print(f"\n  Relatórios em: {PASTA_RESULT}")


if __name__ == "__main__":
    main()
