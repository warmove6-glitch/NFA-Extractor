#!/usr/bin/env python
"""Teste end-to-end de performance: simula upload e polling."""
import asyncio
import time
from pathlib import Path

import httpx

API_BASE = "http://localhost:8081"
FRONTEND_BASE = "http://localhost:5173"

async def test_auditoria_performance():
    """Teste completo de performance."""
    print("\n" + "="*70)
    print("TESTE DE PERFORMANCE - End-to-End")
    print("="*70)

    # 1. Verificar se API está rodando
    print("\n[1] Verificando API...")
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            # Listar clientes
            resp = await client.get(f"{API_BASE}/clientes")
            if resp.status_code == 200:
                clients = resp.json()
                print(f"   [OK] API respondendo ({len(clients)} clientes)")
                client_id = clients[0]['id'] if clients else 1
            else:
                print(f"   [ERROR] API retornou {resp.status_code}")
                return
        except Exception as e:
            print(f"   [ERROR] Erro: {e}")
            return

    # 2. Criar arquivo de teste (XML simples)
    print("\n[2] Criando arquivo de teste...")
    test_xml = """<?xml version="1.0" encoding="UTF-8"?>
<NFe xmlns="http://www.portalfiscal.inf.br/nfe">
  <infNFe Id="NFe12345678901234567890123456789012345678901234">
    <ide>
      <cUF>35</cUF>
      <natOp>VENDA</natOp>
      <indPag>1</indPag>
      <mod>55</mod>
      <serie>1</serie>
      <nNF>1234</nNF>
      <dhEmi>2024-01-15T10:30:00</dhEmi>
      <dhSaiEnt>2024-01-15T10:30:00</dhSaiEnt>
      <tpNF>1</tpNF>
      <idDest>1</idDest>
      <cMunFG>3500400</cMunFG>
      <tpImp>1</tpImp>
      <tpEmis>1</tpEmis>
      <cDV>12</cDV>
      <tpAmb>2</tpAmb>
      <finNFe>1</finNFe>
      <indFinal>0</indFinal>
      <indPres>1</indPres>
      <procEmi>0</procEmi>
      <verProc>1.0</verProc>
    </ide>
    <emit>
      <CNPJ>12345678901234</CNPJ>
      <xNome>Fornecedor Teste</xNome>
      <xFant>Teste</xFant>
      <enderEmit>
        <xLgr>Rua Teste</xLgr>
        <nro>123</nro>
        <xCpl>Apto 100</xCpl>
        <xBairro>Centro</xBairro>
        <cMun>3500400</cMun>
        <xMun>Sao Paulo</xMun>
        <UF>SP</UF>
        <CEP>01310100</CEP>
        <cPais>1058</cPais>
        <xPais>Brasil</xPais>
      </enderEmit>
      <IE>123456789012345</IE>
    </emit>
    <dest>
      <CNPJ>87654321098765</CNPJ>
      <xNome>Cliente Teste</xNome>
      <enderDest>
        <xLgr>Av. Teste</xLgr>
        <nro>456</nro>
        <xBairro>Vila</xBairro>
        <cMun>3500400</cMun>
        <xMun>Sao Paulo</xMun>
        <UF>SP</UF>
        <CEP>01310200</CEP>
        <cPais>1058</cPais>
        <xPais>Brasil</xPais>
      </enderDest>
      <IE>987654321098765</IE>
      <indIEDest>1</indIEDest>
    </dest>
    <det nItem="1">
      <prod>
        <code>SKU123</code>
        <xProd>Produto Teste</xProd>
        <NCM>12345678</NCM>
        <CFOP>5102</CFOP>
        <uCom>UN</uCom>
        <qCom>100.00</qCom>
        <vUnCom>50.00</vUnCom>
        <vProd>5000.00</vProd>
        <cEAN>1234567890123</cEAN>
        <cEANTrib>1234567890123</cEANTrib>
        <indTot>1</indTot>
        <infAdProd>Info adicional</infAdProd>
      </prod>
      <imposto>
        <ICMS>
          <ICMS00>
            <orig>0</orig>
            <CST>00</CST>
            <modBC>0</modBC>
            <vBC>5000.00</vBC>
            <pICMS>12</pICMS>
            <vICMS>600.00</vICMS>
            <modBCST>0</modBCST>
            <pMVAST>0</pMVAST>
            <pBCOp>0</pBCOp>
            <VBCST>0</VBCST>
            <pICMSST>0</pICMSST>
            <vICMSST>0</vICMSST>
            <vBCFCP>0</vBCFCP>
            <pFCP>0</pFCP>
            <vFCP>0</vFCP>
          </ICMS00>
        </ICMS>
      </imposto>
    </det>
    <total>
      <ICMSTot>
        <vBC>5000.00</vBC>
        <vICMS>600.00</vICMS>
        <vICMSDeson>0</vICMSDeson>
        <vFCP>0</vFCP>
        <vBCST>0</vBCST>
        <vST>0</vST>
        <vFCPST>0</vFCPST>
        <vFCPSTRet>0</vFCPSTRet>
        <vProd>5000.00</vProd>
        <vFrete>0</vFrete>
        <vSeg>0</vSeg>
        <vDesc>0</vDesc>
        <vII>0</vII>
        <vIPI>0</vIPI>
        <vIPIDevol>0</vIPIDevol>
        <vPIS>0</vPIS>
        <vCOFINS>0</vCOFINS>
        <vOutro>0</vOutro>
        <vNF>5600.00</vNF>
      </ICMSTot>
    </total>
    <transp>
      <modFrete>9</modFrete>
    </transp>
    <cobr>
      <dup>
        <nDup>001</nDup>
        <dVenc>2024-02-15</dVenc>
        <vDup>5600.00</vDup>
      </dup>
    </cobr>
    <pag>
      <detPag>
        <tPag>01</tPag>
        <vPag>5600.00</vPag>
      </detPag>
      <vtraxadesc>0</vtraxaDesc>
      <vtraxaJuros>0</vtraxaJuros>
    </pag>
    <infIntermed>
      <CNPJ>00000000000191</CNPJ>
      <idCad>1234567</idCad>
      <xCont>Teste Intermediario</xCont>
      <email>teste@intermediario.com</email>
    </infIntermed>
    <infAdic>
      <infCpl>Informacao complementar teste</infCpl>
    </infAdic>
  </infNFe>
</NFe>"""

    test_file = Path("/tmp/test_nota.xml")
    test_file.write_text(test_xml, encoding='utf-8')
    print(f"   [OK] Arquivo criado: {test_file} ({len(test_xml)} bytes)")

    # 3. Upload
    print("\n[3] Enviando arquivo para processamento...")
    t_upload_start = time.time()

    async with httpx.AsyncClient(timeout=30) as client:
        with open(test_file, 'rb') as f:
            files = {'files': ('test_nota.xml', f, 'application/xml')}
            try:
                resp = await client.post(
                    f"{API_BASE}/auditoria/upload/{client_id}",
                    files=files,
                    params={'formato_relatorio': 'html'}
                )
                t_upload = time.time() - t_upload_start

                if resp.status_code == 200:
                    data = resp.json()
                    task_id = data.get('task_id')
                    print(f"   [OK] Upload OK em {t_upload:.2f}s")
                    print(f"   [OK] Task ID: {task_id[:8]}...")
                else:
                    print(f"   [ERROR] Erro: {resp.status_code} - {resp.text[:100]}")
                    return
            except Exception as e:
                print(f"   [ERROR] Erro no upload: {e}")
                return

    # 4. Polling até conclusão
    print("\n[4] Aguardando processamento...")
    t_poll_start = time.time()
    poll_count = 0
    max_polls = 300  # 5 minutos com 1s de intervalo
    last_progress = 0

    async with httpx.AsyncClient(timeout=10) as client:
        while poll_count < max_polls:
            try:
                resp = await client.get(f"{API_BASE}/auditoria/status/{task_id}")
                if resp.status_code == 200:
                    status = resp.json()
                    progress = status.get('progress', 0)
                    status_str = status.get('status', 'unknown')

                    if progress > last_progress or poll_count % 5 == 0:
                        t_elapsed = time.time() - t_poll_start
                        print(f"   [{t_elapsed:6.1f}s] {status_str:12} - {progress:3d}%")
                        last_progress = progress

                    if status_str == 'concluido':
                        t_total = time.time() - t_upload_start
                        print(f"\n   [OK] CONCLUIDO em {t_total:.1f}s")
                        result = status.get('resultado', '')[:100]
                        print(f"   Resultado: {result}...")
                        return True
                    elif status_str == 'erro':
                        print(f"\n   [ERROR] ERRO: {status.get('erro', 'desconhecido')}")
                        return False

            except Exception as e:
                print(f"   (erro transiente: {type(e).__name__})")

            poll_count += 1
            await asyncio.sleep(1)

    print(f"\n   [ERROR] Timeout apos {max_polls}s")
    return False

if __name__ == '__main__':
    try:
        result = asyncio.run(test_auditoria_performance())
        print("\n" + "="*70)
        if result:
            print("[OK] TESTE PASSOU")
        else:
            print("[ERROR] TESTE FALHOU")
        print("="*70 + "\n")
    except KeyboardInterrupt:
        print("\n[Interrompido pelo usuario]")
    except Exception as e:
        print(f"\n[ERROR] Erro critico: {e}")
        import traceback
        traceback.print_exc()
