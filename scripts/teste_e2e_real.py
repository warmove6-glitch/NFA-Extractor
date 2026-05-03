"""Teste E2E real com PDFs do diretório NFE_GADO_2026.

Fluxo: login → criar cliente → upload → polling → download laudo.
Salva o laudo em reports_e2e/ para inspeção visual.
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

# Cliente de teste — usa um par DEST/REM real (ADELA)
NOME_CLIENTE = "ADELA TESTE E2E"
CPF_CLIENTE = "12345678901"
PDFS = ["ADELA DEST.pdf", "ADELA REM.pdf"]

OUT_DIR = Path(r"D:\01_Projetos_Ativos\NFA Extractor\reports_e2e")
OUT_DIR.mkdir(exist_ok=True)


def main() -> int:
    client = httpx.Client(base_url=API, timeout=60)

    # 1) Login
    print("=" * 60)
    print("[1/5] LOGIN")
    print("=" * 60)
    r = client.post(
        "/auth/login",
        data={"username": EMAIL, "password": PASSWORD},
    )
    if r.status_code != 200:
        print(f"❌ Login falhou: {r.status_code} {r.text}")
        return 1
    token = r.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    print(f"✅ Token obtido ({len(token)} chars)")

    # 2) Criar cliente (ou reusar se já existe)
    print()
    print("=" * 60)
    print("[2/5] CRIAR CLIENTE")
    print("=" * 60)
    r = client.post("/clientes/", json={"nome": NOME_CLIENTE, "cpf_cnpj": CPF_CLIENTE})
    if r.status_code == 201:
        cliente_id = r.json()["id"]
        print(f"✅ Cliente criado id={cliente_id}")
    elif r.status_code == 409:
        # Já existe — buscar
        r2 = client.get("/clientes/")
        cliente = next(c for c in r2.json() if c["cpf_cnpj"] == CPF_CLIENTE)
        cliente_id = cliente["id"]
        print(f"♻️  Cliente já existia, usando id={cliente_id}")
    else:
        print(f"❌ Falha criar cliente: {r.status_code} {r.text}")
        return 1

    # 3) Upload PDFs
    print()
    print("=" * 60)
    print("[3/5] UPLOAD")
    print("=" * 60)
    files = []
    for nome in PDFS:
        path = PDF_DIR / nome
        if not path.exists():
            print(f"❌ Arquivo não encontrado: {path}")
            return 1
        files.append(("files", (nome, path.read_bytes(), "application/pdf")))
        print(f"   📄 {nome} ({path.stat().st_size / 1024:.1f} KB)")

    r = client.post(f"/auditoria/upload/{cliente_id}", files=files)
    if r.status_code != 200:
        print(f"❌ Upload falhou: {r.status_code} {r.text}")
        return 1
    task_id = r.json()["task_id"]
    print(f"✅ Task criada: {task_id}")

    # 4) Polling
    print()
    print("=" * 60)
    print("[4/5] PROCESSAMENTO")
    print("=" * 60)
    last_status = ""
    inicio = time.time()
    for _ciclo in range(150):  # 5 min max
        r = client.get(f"/auditoria/status/{task_id}")
        if r.status_code != 200:
            print(f"❌ Status {r.status_code}: {r.text}")
            return 1
        data = r.json()
        status = data.get("status", "?")
        progress = data.get("progress", 0)
        if status != last_status:
            elapsed = time.time() - inicio
            print(f"   [{elapsed:5.1f}s] {status:25s} {progress:3d}%")
            last_status = status
        if status == "concluido":
            print(f"✅ Concluído em {time.time() - inicio:.1f}s")
            print(f"   total_notas: {data.get('total_notas', '?')}")
            resultado = data.get("resultado", "")
            if resultado:
                print(f"   resultado: {resultado[:200]}...")
            break
        if status == "erro":
            print(f"❌ Erro: {data.get('erro', 'desconhecido')}")
            return 1
        time.sleep(2)
    else:
        print("❌ Timeout (300s)")
        return 1

    # 5) Download laudo
    print()
    print("=" * 60)
    print("[5/5] DOWNLOAD LAUDO")
    print("=" * 60)
    r = client.get(f"/auditoria/download/{task_id}")
    if r.status_code != 200:
        print(f"❌ Download falhou: {r.status_code} {r.text}")
        return 1
    out_path = OUT_DIR / f"laudo_{task_id[:8]}.pdf"
    out_path.write_bytes(r.content)
    print(f"✅ PDF salvo: {out_path}")
    print(f"   Tamanho: {len(r.content) / 1024:.1f} KB")

    # Detecta tipo (header PDF deve ser %PDF-)
    if r.content[:4] == b"%PDF":
        print("   ✅ Header PDF válido")
    else:
        print(f"   ⚠️  Não parece PDF: {r.content[:20]!r}")

    print()
    print("=" * 60)
    print("🎉 TESTE E2E COMPLETO")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
