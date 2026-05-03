"""
Teste de Carga — NF-e GADO 2026
Faz upload de todos os PDFs da pasta NFE_GADO_2026, aguarda a auditoria
e baixa o relatório para C:\\Users\\Veloso\\NFE_GADO_2026\\RESULTADOS_AUDITORIA\\
"""

import datetime
import pathlib
import sys
import time

import requests

# ─── Configuração ──────────────────────────────────────────────────────────────
BASE_URL      = "http://127.0.0.1:8085"
PDF_ROOT      = pathlib.Path(r"C:\Users\Veloso\NFE_GADO_2026")
PASTA_RESULT  = PDF_ROOT / "RESULTADOS_AUDITORIA"
USUARIO       = "admin@orgatec.com.br"
SENHA         = "Admin@2026!"
CLIENTE_NOME  = "NF-e GADO 2026"
CLIENTE_CPF   = "12345678909"          # CPF válido (dígitos verificadores corretos)
MODO_REL      = "detalhado"
FORMATO_REL   = "pdf"
TIMEOUT_TOTAL = 600                    # 10 minutos máximo de espera


def log(msg: str) -> None:
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def barra(progresso: int, label: str = "") -> None:
    preenchido = int(progresso / 5)
    barra_str  = "#" * preenchido + "-" * (20 - preenchido)
    print(f"\r  [{barra_str}] {progresso:3d}%  {label:<40}", end="", flush=True)


# ─── 1. Autenticação ───────────────────────────────────────────────────────────
def autenticar() -> str:
    log("Autenticando...")
    resp = requests.post(
        f"{BASE_URL}/auth/login",
        data={"username": USUARIO, "password": SENHA},
        timeout=15,
    )
    resp.raise_for_status()
    token = resp.json()["access_token"]
    log(f"Token obtido: {token[:20]}...")
    return token


# ─── 2. Criar / reutilizar cliente ────────────────────────────────────────────
def criar_cliente(token: str) -> int:
    log(f"Criando cliente '{CLIENTE_NOME}'...")
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.post(
        f"{BASE_URL}/clientes/",
        json={"nome": CLIENTE_NOME, "cpf_cnpj": CLIENTE_CPF},
        headers=headers,
        timeout=15,
    )
    if resp.status_code == 409:
        # Cliente já existe — busca o ID existente
        log("Cliente ja existe, buscando ID...")
        lista = requests.get(f"{BASE_URL}/clientes/", headers=headers, timeout=15)
        lista.raise_for_status()
        dados = lista.json()
        # suporta lista direta ou paginado {"items": [...]}
        itens = dados if isinstance(dados, list) else dados.get("items", dados.get("clientes", []))
        for c in itens:
            if c.get("cpf_cnpj", "").replace(".", "").replace("-", "") == CLIENTE_CPF:
                log(f"Cliente encontrado: ID={c['id']}")
                return c["id"]
        raise RuntimeError("Cliente duplicado mas nao encontrado na listagem.")
    resp.raise_for_status()
    client_id = resp.json()["id"]
    log(f"Cliente criado: ID={client_id}")
    return client_id


# ─── 3. Coletar PDFs ──────────────────────────────────────────────────────────
def coletar_pdfs() -> list[pathlib.Path]:
    # Exclui a subpasta de resultados
    pdfs = sorted(
        p for p in PDF_ROOT.rglob("*.pdf")
        if "RESULTADOS_AUDITORIA" not in p.parts
    )
    total_mb = sum(p.stat().st_size for p in pdfs) / 1_048_576
    log(f"Encontrados {len(pdfs)} PDFs ({total_mb:.1f} MB)")
    for p in pdfs:
        print(f"   - {p.relative_to(PDF_ROOT)}")
    return pdfs


# ─── 4. Upload em lote ────────────────────────────────────────────────────────
def upload_lote(token: str, client_id: int, pdfs: list[pathlib.Path]) -> str:
    log(f"Enviando {len(pdfs)} PDFs para cliente {client_id}...")
    headers = {"Authorization": f"Bearer {token}"}
    arquivos = []
    try:
        for p in pdfs:
            arquivos.append(("files", (p.name, open(p, "rb"), "application/pdf")))
        resp = requests.post(
            f"{BASE_URL}/auditoria/upload/{client_id}",
            params={"modo_relatorio": MODO_REL, "formato_relatorio": FORMATO_REL},
            files=arquivos,
            headers=headers,
            timeout=120,
        )
        resp.raise_for_status()
        dados  = resp.json()
        task_id = dados["task_id"]
        log(f"Upload OK — task_id={task_id}")
        log(f"  PDFs recebidos: {dados.get('arquivos', {})}")
        return task_id
    finally:
        for _, (_, fobj, _) in arquivos:
            fobj.close()


# ─── 5. Polling de status ─────────────────────────────────────────────────────
def aguardar(task_id: str) -> dict:
    log("Aguardando processamento...")
    print()
    inicio  = time.time()
    ciclo   = 0
    delays  = [2, 2, 4, 4, 8, 8, 16]   # backoff

    while True:
        tempo = time.time() - inicio
        if tempo > TIMEOUT_TOTAL:
            raise TimeoutError(f"Timeout de {TIMEOUT_TOTAL}s atingido.")

        resp = requests.get(f"{BASE_URL}/auditoria/status/{task_id}", timeout=15)
        resp.raise_for_status()
        dados    = resp.json()
        status   = dados.get("status", "")
        progresso = dados.get("progress", 0)
        label    = dados.get("label") or status

        barra(progresso, label)

        if status == "concluido":
            print()
            log(f"Auditoria concluida em {tempo:.0f}s")
            return dados
        if status == "erro":
            print()
            raise RuntimeError(f"Erro na auditoria: {dados.get('erro','')}")

        delay = delays[min(ciclo, len(delays) - 1)]
        ciclo += 1
        time.sleep(delay)


# ─── 6. Download do relatório ─────────────────────────────────────────────────
def baixar_relatorio(token: str, task_id: str) -> pathlib.Path:
    PASTA_RESULT.mkdir(parents=True, exist_ok=True)
    log(f"Baixando relatorio para {PASTA_RESULT}...")

    headers  = {"Authorization": f"Bearer {token}"}
    resp     = requests.get(
        f"{BASE_URL}/auditoria/download/{task_id}",
        headers=headers,
        timeout=60,
        allow_redirects=True,
    )
    resp.raise_for_status()

    # Detecta extensao pelo content-type
    ct  = resp.headers.get("content-type", "")
    ext = ".pdf" if "pdf" in ct else ".html"

    ts       = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    destino  = PASTA_RESULT / f"AUDITORIA_GADO_2026_{ts}{ext}"

    destino.write_bytes(resp.content)
    log(f"Relatorio salvo: {destino}  ({len(resp.content) / 1024:.1f} KB)")
    return destino


# ─── main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    print("=" * 60)
    print("  NFA EXTRACTOR — TESTE DE CARGA / NF-e GADO 2026")
    print("=" * 60)
    inicio_total = time.time()

    try:
        token     = autenticar()
        client_id = criar_cliente(token)
        pdfs      = coletar_pdfs()

        if not pdfs:
            log("Nenhum PDF encontrado. Verifique o caminho.")
            sys.exit(1)

        task_id   = upload_lote(token, client_id, pdfs)
        resultado = aguardar(task_id)
        destino   = baixar_relatorio(token, task_id)

        tempo_total = time.time() - inicio_total
        print()
        print("=" * 60)
        print("  RESULTADO FINAL")
        print("=" * 60)
        print(f"  Tempo total    : {tempo_total:.0f}s")
        print(f"  PDFs enviados  : {len(pdfs)}")
        print(f"  Status         : {resultado.get('status')}")
        veredito = resultado.get("resultado") or ""
        if veredito:
            print(f"  Veredito       : {veredito[:200]}")
        print(f"  Relatorio      : {destino}")
        print("=" * 60)

    except KeyboardInterrupt:
        print("\nInterrompido pelo usuario.")
        sys.exit(1)
    except Exception as exc:
        print()
        log(f"ERRO: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
