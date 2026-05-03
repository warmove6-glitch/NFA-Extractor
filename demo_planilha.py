#!/usr/bin/env python
"""Demo: Gera uma planilha IRPF de exemplo mostrando o novo layout."""

from src.domain.extractor import NFA, Parte
from src.domain.planilha_ir import gerar_dados_planilha, gerar_html_planilha


def criar_notas_exemplo() -> list[NFA]:
    """Cria notas de exemplo para demonstração."""
    return [
        NFA(
            numero="NF000001",
            natureza="VENDA",
            emissao="05/04/2026",
            valor_total=12500.0,
            valor_icms=2250.0,
            quantidade_total=250.0,
            remetente=Parte(nome="Fazenda São José", cpf_cnpj="12.345.678/0001-90"),
            destinatario=Parte(nome="Frigorífico ABC", cpf_cnpj="98.765.432/0001-10"),
        ),
        NFA(
            numero="NF000002",
            natureza="VENDA",
            emissao="12/04/2026",
            valor_total=8750.0,
            valor_icms=1575.0,
            quantidade_total=175.0,
            remetente=Parte(nome="Fazenda São José", cpf_cnpj="12.345.678/0001-90"),
            destinatario=Parte(nome="Frigorífico DEF", cpf_cnpj="11.222.333/0001-44"),
        ),
        NFA(
            numero="NF000003",
            natureza="VENDA",
            emissao="20/04/2026",
            valor_total=10250.0,
            valor_icms=1845.0,
            quantidade_total=205.0,
            remetente=Parte(nome="Fazenda São José", cpf_cnpj="12.345.678/0001-90"),
            destinatario=Parte(nome="Frigorífico XYZ", cpf_cnpj="55.666.777/0001-88"),
        ),
        NFA(
            numero="NF000004",
            natureza="REMESSA",
            emissao="08/04/2026",
            valor_total=4500.0,
            valor_icms=810.0,
            quantidade_total=90.0,
            remetente=Parte(nome="Fazenda São José", cpf_cnpj="12.345.678/0001-90"),
            destinatario=Parte(nome="Pasto Temporário", cpf_cnpj="22.333.444/0001-55"),
        ),
        NFA(
            numero="NF000005",
            natureza="TRANSFERENCIA",
            emissao="15/04/2026",
            valor_total=3200.0,
            valor_icms=576.0,
            quantidade_total=64.0,
            remetente=Parte(nome="Fazenda São José", cpf_cnpj="12.345.678/0001-90"),
            destinatario=Parte(nome="Fazenda Matriz", cpf_cnpj="12.345.678/0001-91"),
        ),
        NFA(
            numero="NF000006",
            natureza="OUTRAS",
            emissao="25/04/2026",
            valor_total=2000.0,
            valor_icms=360.0,
            quantidade_total=40.0,
            remetente=Parte(nome="Fazenda São José", cpf_cnpj="12.345.678/0001-90"),
            destinatario=Parte(nome="Terceiros", cpf_cnpj="99.888.777/0001-66"),
        ),
    ]


if __name__ == "__main__":
    print("[DEBUG] Gerando planilha IRPF de exemplo...\n")

    notas = criar_notas_exemplo()
    nome_produtor = "Genis Carlos Luiz de Oliveira"

    print(f"[OK] Notas criadas: {len(notas)}")
    print(f"[OK] Total de cabecas: {sum(n.quantidade_total for n in notas):.0f}")
    print(f"[OK] Faturamento total: R$ {sum(n.valor_total for n in notas):,.2f}\n")

    # Gerar dados estruturados
    print("Gerando dados da planilha...")
    dados = gerar_dados_planilha(notas, nome_produtor)

    print(f"[OK] Produtor: {dados['produtor']}")
    print(f"[OK] Periodo: {dados['periodo']}")
    print(f"[OK] Total de notas: {dados['total_notas']}")
    print(f"[OK] Total de cabecas: {dados['total_cabecas']:.0f}")
    print(f"[OK] Faturamento total: R$ {dados['faturamento_total']:,.2f}")
    print(f"[OK] Totais por natureza: {list(dados['totais_natureza'].keys())}\n")

    # Gerar HTML
    print("Gerando HTML da planilha...")
    html = gerar_html_planilha(dados)

    # Salvar em arquivo
    output_file = "data/demo_planilha_irpf.html"
    import os
    os.makedirs("data", exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[OK] Planilha salva em: {output_file}")
    print(f"[OK] Tamanho do arquivo: {len(html):,} bytes")
    print("\nAbra o arquivo no navegador para visualizar a planilha IRPF com layout moderno!")
