"""Teste E2E usando o CPF REAL do remetente extraído do PDF.

Permite que a bateria forense (T-01..T-08) calcule corretamente Receita,
Trânsito, Compras e Funrural (em vez de zerar tudo por incompatibilidade
entre CPF do cliente cadastrado e CPF do remetente nas notas).
"""
from __future__ import annotations

import sys
import time
from collections import Counter
from pathlib import Path

import httpx

# Permite importar src/* mesmo rodando como script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.domain.extractor import extrair_notas

API = "http://127.0.0.1:8081"
EMAIL = "admin@orgatec.com.br"
PASSWORD = "Admin@2024!"

PDF_DIR = Path(r"C:\Users\Veloso\NFE_GADO_2026\ARQUIVO_2026_RESUMO_DE_NFE_GADO_2026")
OUT_DIR = Path(r"D:\01_Projetos_Ativos\NFA Extractor\reports_e2e")
OUT_DIR.mkdir(exist_ok=True)


def descobrir_cpf_dominante(pdfs: list[Path]) -> tuple[str, str]:
    """Extrai notas e identifica o CPF mais comum no remetente (= contribuinte real)."""
    docs = Counter()
    nomes = {}
    for p in pdfs:
        notas, _, _ = extrair_notas(str(p))
        for n in notas:
            doc = "".join(c for c in (n.remetente.cpf_cnpj or "") if c.isdigit())
            if doc and len(doc) == 11:
                docs[doc] += 1
                nomes[doc] = n.remetente.nome or "?"
    if not docs:
        return "12345678901", "TESTE"
    cpf, qtd = docs.most_common(1)[0]
    return cpf, nomes.get(cpf, "?")


def main() -> int:
    # Pega 2 PDFs de um produtor (ADELA DEST + ADELA REM)
    pdfs = [PDF_DIR / "ADELA DEST.pdf", PDF_DIR / "ADELA REM.pdf"]
    cpf, nome = descobrir_cpf_dominante(pdfs)
    print(f"Contribuinte detectado: {nome} ({cpf})")

    client = httpx.Client(base_url=API, timeout=600)

    # Login
    r = client.post("/auth/login", data={"username": EMAIL, "password": PASSWORD})
    r.raise_for_status()
    client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"

    # Cria/reusa cliente com CPF REAL
    r = client.post("/clientes/", json={"nome": nome, "cpf_cnpj": cpf})
    if r.status_code == 201:
        cliente_id = r.json()["id"]
    elif r.status_code == 409:
        r2 = client.get("/clientes/")
        cliente_id = next(c for c in r2.json() if c["cpf_cnpj"] == cpf)["id"]
    else:
        print(f"Erro: {r.status_code} {r.text}")
        return 1
    print(f"Cliente id={cliente_id}")

    # Upload
    files = [("files", (p.name, p.read_bytes(), "application/pdf")) for p in pdfs]
    r = client.post(f"/auditoria/upload/{cliente_id}", files=files)
    r.raise_for_status()
    task_id = r.json()["task_id"]
    print(f"Task: {task_id}")

    # Polling
    inicio = time.time()
    last = ""
    for _ in range(150):
        r = client.get(f"/auditoria/status/{task_id}")
        d = r.json()
        s = d.get("status", "?")
        if s != last:
            print(f"  [{time.time() - inicio:5.1f}s] {s:25s} {d.get('progress', 0):3d}%")
            last = s
        if s == "concluido":
            print(f"\nConcluído: total_notas={d.get('total_notas')}")
            break
        if s == "erro":
            print(f"ERRO: {d.get('erro')}")
            return 1
        time.sleep(2)

    # Download
    r = client.get(f"/auditoria/download/{task_id}")
    r.raise_for_status()
    out = OUT_DIR / f"laudo_PRODUTOR_{cpf[-4:]}_{task_id[:8]}.pdf"
    out.write_bytes(r.content)
    print(f"\nLaudo: {out}")
    print(f"  {len(r.content)/1024:.1f} KB | PDF: {r.content[:4] == b'%PDF'}")

    # Inspeciona
    import fitz
    doc = fitz.open(out)
    print(f"  Páginas: {len(doc)}")
    txt_p1 = doc[0].get_text()
    print("\n--- PÁGINA 1 (síntese) ---")
    for linha in txt_p1.splitlines():
        if linha.strip() and any(s in linha for s in ("R$", "notas", "Volume", "Receita", "Trânsito", "Cabeças", "Funrural", "Período")):
            print(f"  {linha}")
    doc.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
