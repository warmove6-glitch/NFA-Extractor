#!/usr/bin/env python
"""Teste simples de performance."""
import asyncio
import time
from pathlib import Path

import httpx

API_BASE = "http://localhost:8081"
client_id = 1

async def test():
    print("\n[TESTE] Performance de Auditoria\n")

    # Criar XML de teste
    xml = """<?xml version="1.0"?><root><nota numero="001" valor="1000.00"/></root>"""
    test_file = Path("test_tmp.xml")
    test_file.write_text(xml)

    # Upload
    print("[1] Enviando arquivo...")
    t_start = time.time()
    async with httpx.AsyncClient(timeout=30) as client:
        with open(test_file, 'rb') as f:
            resp = await client.post(
                f"{API_BASE}/auditoria/upload/{client_id}",
                files={'files': ('test.xml', f)},
                params={'formato_relatorio': 'html'}
            )
            if resp.status_code != 200:
                print(f"[ERROR] {resp.status_code}: {resp.text[:100]}")
                return

            task_id = resp.json()['task_id']
            print(f"[OK] Task ID: {task_id[:8]}")

    # Polling
    print("\n[2] Aguardando processamento...")
    async with httpx.AsyncClient(timeout=60) as client:
        for _i in range(300):
            resp = await client.get(f"{API_BASE}/auditoria/status/{task_id}")
            if resp.status_code == 200:
                status = resp.json()
                progress = status.get('progress', 0)
                status_str = status.get('status', '?')

                elapsed = time.time() - t_start
                print(f"    [{elapsed:5.1f}s] {status_str:12} {progress:3d}%")

                if status_str == 'concluido':
                    print(f"\n[RESULT] Concluido em {elapsed:.1f}s")
                    return
                elif status_str == 'erro':
                    print(f"\n[ERROR] {status.get('erro')}")
                    return

            await asyncio.sleep(1)

    print("\n[TIMEOUT] Nao terminou em 5 minutos")

if __name__ == '__main__':
    asyncio.run(test())
