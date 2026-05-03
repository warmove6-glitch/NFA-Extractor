"""Teste E2E de stress: TODOS os 32 PDFs em uma única auditoria.

Mede tempo total, tamanho do laudo e quantidade de notas extraídas.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx

API = "http://127.0.0.1:8081"
EMAIL = "admin@orgatec.com.br"
PASSWORD = "Admin@2024!"

PDF_DIR = Path(r"C:\Users\Veloso\NFE_GADO_2026\ARQUIVO_2026_RESUMO_DE_NFE_GADO_2026")

NOME_CLIENTE = "LOTE COMPLETO 2026"
CPF_CLIENTE = "98765432100"

OUT_DIR = Path(r"D:\01_Projetos_Ativos\NFA Extractor\reports_e2e")
OUT_DIR.mkdir(exist_ok=True)


def main() -> int:
    client = httpx.Client(base_url=API, timeout=600)

    # 1) Login
    r = client.post("/auth/login", data={"username": EMAIL, "password": PASSWORD})
    r.raise_for_status()
    token = r.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    print("Login OK")

    # 2) Cliente
    r = client.post("/clientes/", json={"nome": NOME_CLIENTE, "cpf_cnpj": CPF_CLIENTE})
    if r.status_code == 201:
        cliente_id = r.json()["id"]
    elif r.status_code == 409:
        r2 = client.get("/clientes/")
        cliente_id = next(c for c in r2.json() if c["cpf_cnpj"] == CPF_CLIENTE)["id"]
    else:
        print(f"Erro cliente: {r.status_code} {r.text}")
        return 1
    print(f"Cliente id={cliente_id}")

    # 3) Upload TODOS os PDFs
    pdfs = sorted(PDF_DIR.glob("*.pdf"))
    print(f"Encontrados {len(pdfs)} PDFs")
    total_kb = sum(p.stat().st_size for p in pdfs) / 1024
    print(f"Tamanho total: {total_kb:.1f} KB")

    files = [("files", (p.name, p.read_bytes(), "application/pdf")) for p in pdfs]
    t_upload_start = time.time()
    r = client.post(f"/auditoria/upload/{cliente_id}", files=files)
    r.raise_for_status()
    t_upload = time.time() - t_upload_start
    task_id = r.json()["task_id"]
    print(f"Upload OK ({t_upload:.1f}s) → task {task_id}")

    # 4) Polling
    inicio = time.time()
    last = ""
    for _ciclo in range(300):  # 10 min
        r = client.get(f"/auditoria/status/{task_id}")
        if r.status_code != 200:
            print(f"Erro status: {r.status_code} {r.text[:200]}")
            return 1
        data = r.json()
        status = data.get("status", "?")
        progress = data.get("progress", 0)
        if status != last:
            print(f"  [{time.time() - inicio:6.1f}s] {status:25s} {progress:3d}%")
            last = status
        if status == "concluido":
            elapsed = time.time() - inicio
            print(f"\nConcluído em {elapsed:.1f}s")
            print(f"Total notas: {data.get('total_notas')}")
            break
        if status == "erro":
            print(f"ERRO: {data.get('erro', '?')}")
            return 1
        time.sleep(2)

    # 5) Download
    r = client.get(f"/auditoria/download/{task_id}")
    r.raise_for_status()
    out_path = OUT_DIR / f"laudo_LOTE_{task_id[:8]}.pdf"
    out_path.write_bytes(r.content)
    is_pdf = r.content[:4] == b"%PDF"
    print(f"\nLaudo: {out_path}")
    print(f"  Tamanho: {len(r.content) / 1024:.1f} KB")
    print(f"  PDF válido: {is_pdf}")

    # Bônus: planilha HTML
    r = client.get(f"/auditoria/planilha/{task_id}")
    if r.status_code == 200:
        html_path = OUT_DIR / f"planilha_{task_id[:8]}.html"
        html_path.write_text(r.text, encoding="utf-8")
        print(f"  Planilha HTML: {html_path} ({len(r.text) / 1024:.1f} KB)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
