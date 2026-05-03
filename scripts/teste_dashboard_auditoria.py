"""Simula passo-a-passo o que o usuário faz em /dashboard/auditoria.

Cada step corresponde a uma ação do usuário no frontend:

  Step 1  POST /auth/login                — usuário clica "Entrar" em /login
  Step 2  GET  /clientes/                 — frontend lista clientes no select
  Step 3  POST /clientes/                 — usuário cadastra novo (se necessário)
  Step 4  POST /auditoria/upload/{id}     — usuário faz drop dos PDFs e clica "Iniciar"
  Step 5  GET  /auditoria/status/{id}     — frontend faz polling a cada 2s
  Step 6  GET  /auditoria/download/{id}   — usuário clica "Baixar Laudo PDF"

Roda EXATAMENTE os mesmos requests que o React faz (api.js → axios → backend).
"""
from __future__ import annotations

import sys
import time
from collections import Counter
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.domain.extractor import extrair_notas

API = "http://127.0.0.1:8081"
EMAIL = "admin@orgatec.com.br"
PASSWORD = "Admin@2024!"

PDF_DIR = Path(r"C:\Users\Veloso\NFE_GADO_2026\ARQUIVO_2026_RESUMO_DE_NFE_GADO_2026")
OUT_DIR = Path(r"D:\01_Projetos_Ativos\NFA Extractor\reports_e2e")
OUT_DIR.mkdir(exist_ok=True)


def descobrir_contribuinte(pdfs: list[Path]) -> tuple[str, str]:
    docs = Counter()
    nomes = {}
    for p in pdfs:
        notas, _, _ = extrair_notas(str(p))
        for n in notas:
            doc = "".join(c for c in (n.remetente.cpf_cnpj or "") if c.isdigit())
            if doc and len(doc) == 11:
                docs[doc] += 1
                if n.remetente.nome and "CNPJ" not in n.remetente.nome.upper():
                    nomes[doc] = n.remetente.nome
    if not docs:
        return "12345678901", "TESTE"
    cpf = docs.most_common(1)[0][0]
    return cpf, nomes.get(cpf, "?")


def main() -> int:
    print("=" * 75)
    print("SIMULAÇÃO DE USUÁRIO — http://127.0.0.1:5173/dashboard/auditoria")
    print("=" * 75)

    # Vamos auditar 4 contribuintes diferentes pra ter dados ricos
    contribuintes_pdfs = [
        ("ADELA", [PDF_DIR / "ADELA DEST.pdf", PDF_DIR / "ADELA REM.pdf"]),
        ("FABIO", [PDF_DIR / "FABIO DEST.pdf", PDF_DIR / "FABIO REM.pdf"]),
        ("GERALDO", [PDF_DIR / "GERALDO DEST.pdf", PDF_DIR / "GERALDO REM.pdf"]),
        ("RICARDO", [PDF_DIR / "RICARDO LOBO DEST.pdf", PDF_DIR / "RICARDO LOBO REM.pdf"]),
    ]

    client = httpx.Client(base_url=API, timeout=600)

    # ── STEP 1: Login (usuário em /login digita e-mail/senha e clica "Entrar") ─
    print("\n[STEP 1] Login")
    print(f"  POST /auth/login  username={EMAIL}")
    r = client.post("/auth/login", data={"username": EMAIL, "password": PASSWORD})
    r.raise_for_status()
    token = r.json()["access_token"]
    user = r.json()["user"]
    client.headers["Authorization"] = f"Bearer {token}"
    print(f"  ✓ Logado: {user['nome']} ({user['role']})")

    # ── STEP 2: Frontend carrega lista de clientes (useEffect no AuditoriaModule) ─
    print("\n[STEP 2] Listar clientes")
    print("  GET /clientes/")
    r = client.get("/clientes/")
    clientes = r.json()
    print(f"  ✓ {len(clientes)} cliente(s) já cadastrado(s)")

    resultados = []
    for nome_curto, pdfs in contribuintes_pdfs:
        for p in pdfs:
            if not p.exists():
                print(f"  ⚠ {p.name} não encontrado — pulando contribuinte {nome_curto}")
                break
        else:
            print(f"\n{'─' * 75}")
            print(f"AUDITANDO: {nome_curto}")
            print(f"{'─' * 75}")

            cpf, nome_completo = descobrir_contribuinte(pdfs)
            print(f"  Detectado: {nome_completo} (CPF {cpf})")

            # ── STEP 3: Cliente — usuário seleciona/cadastra ──────────────
            existente = next((c for c in clientes if c["cpf_cnpj"] == cpf), None)
            if existente:
                cliente_id = existente["id"]
                print(f"  ✓ Cliente já cadastrado: id={cliente_id}")
            else:
                print(f"  POST /clientes/  nome={nome_completo}")
                r = client.post("/clientes/", json={"nome": nome_completo, "cpf_cnpj": cpf})
                if r.status_code == 201:
                    cliente_id = r.json()["id"]
                    clientes.append(r.json())
                    print(f"  ✓ Cliente cadastrado: id={cliente_id}")
                elif r.status_code == 409:
                    r2 = client.get("/clientes/")
                    cliente_id = next(c for c in r2.json() if c["cpf_cnpj"] == cpf)["id"]
                    print(f"  ✓ Cliente já existia: id={cliente_id}")
                else:
                    print(f"  ✗ Erro: {r.status_code} {r.text[:100]}")
                    continue

            # ── STEP 4: Upload (usuário arrasta PDFs e clica "Iniciar Auditoria") ─
            print(f"  POST /auditoria/upload/{cliente_id}")
            files = []
            tamanho_total = 0
            for p in pdfs:
                conteudo = p.read_bytes()
                tamanho_total += len(conteudo)
                files.append(("files", (p.name, conteudo, "application/pdf")))
                print(f"    📎 {p.name} ({len(conteudo)/1024:.1f} KB)")
            r = client.post(f"/auditoria/upload/{cliente_id}", files=files)
            r.raise_for_status()
            task_id = r.json()["task_id"]
            print(f"  ✓ Upload OK → task_id={task_id[:8]}…")

            # ── STEP 5: Polling (frontend mostra a barra de progresso) ────
            print("  GET /auditoria/status/{task_id}  (polling 2s)")
            inicio = time.time()
            last = ""
            for _ in range(120):
                r = client.get(f"/auditoria/status/{task_id}")
                d = r.json()
                s = d.get("status", "?")
                pct = d.get("progress", 0)
                if s != last:
                    el = time.time() - inicio
                    print(f"    [{el:5.1f}s] {s:25s} {pct:3d}%")
                    last = s
                if s == "concluido":
                    total = d.get("total_notas", 0)
                    elapsed = time.time() - inicio
                    print(f"  ✓ Concluído em {elapsed:.1f}s | {total} notas processadas")
                    break
                if s == "erro":
                    print(f"  ✗ ERRO: {d.get('erro', '?')}")
                    break
                time.sleep(2)

            # ── STEP 6: Download (usuário clica "Baixar Laudo PDF") ───────
            print(f"  GET /auditoria/download/{task_id}")
            r = client.get(f"/auditoria/download/{task_id}")
            r.raise_for_status()
            out = OUT_DIR / f"laudo_{nome_curto}_{task_id[:8]}.pdf"
            out.write_bytes(r.content)
            ehpdf = r.content[:4] == b"%PDF"
            print(f"  ✓ PDF: {out.name} ({len(r.content)/1024:.1f} KB) — válido={ehpdf}")

            resultados.append({
                "contribuinte": nome_completo,
                "cpf": cpf,
                "task_id": task_id[:8],
                "notas": total,
                "tempo_s": round(elapsed, 1),
                "pdf": out.name,
                "tamanho_kb": round(len(r.content) / 1024, 1),
            })

    # ── Resumo final ──────────────────────────────────────────────────────
    print("\n" + "=" * 75)
    print("RESUMO DOS LAUDOS GERADOS")
    print("=" * 75)
    print(f"{'Contribuinte':<35} {'CPF':<14} {'Notas':>6} {'Tempo':>7} {'PDF KB':>8}")
    print("-" * 75)
    for r in resultados:
        print(f"{r['contribuinte'][:34]:<35} {r['cpf']:<14} {r['notas']:>6} "
              f"{r['tempo_s']:>6.1f}s {r['tamanho_kb']:>8.1f}")
    print()
    print(f"Total auditado: {len(resultados)} contribuintes")
    print(f"PDFs salvos em: {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
