"""
Extrator de NFA (Nota Fiscal Avulsa) — SEFAZ-GO
Uso: python extrair_nfa.py <arquivo.pdf> [saida.xlsx]
"""

import argparse
import sys
from pathlib import Path

from extractor import extrair_notas
from excel_export import exportar_excel


def main() -> None:
    """Ponto de entrada da CLI."""
    parser = argparse.ArgumentParser(
        description='Extrator de Notas Fiscais Avulsas (NFA) SEFAZ-GO → Excel',
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument('pdf', help='Arquivo PDF contendo as NFAs')
    parser.add_argument(
        '--saida', '-o',
        help='Arquivo Excel de saída (padrão: <nome_do_pdf>_extraido.xlsx)',
        default=None,
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f'Erro: arquivo não encontrado: {pdf_path}', file=sys.stderr)
        sys.exit(1)
    if not pdf_path.suffix.lower() == '.pdf':
        print(f'Erro: o arquivo deve ser um PDF: {pdf_path}', file=sys.stderr)
        sys.exit(1)

    saida = args.saida or str(pdf_path.stem) + '_extraido.xlsx'

    print(f'Lendo {pdf_path}...')
    try:
        notas = extrair_notas(str(pdf_path))
    except Exception as e:
        print(f'Erro ao extrair notas: {e}', file=sys.stderr)
        sys.exit(1)

    print(f'  > {len(notas)} notas encontradas')

    total_cabecas = sum(n.quantidade_total for n in notas)
    total_valor   = sum(n.valor_total for n in notas)
    print(f'  > {total_cabecas:.0f} cabeças  |  R$ {total_valor:,.2f} em valor total')

    print(f'Exportando para {saida}...')
    exportar_excel(notas, saida)
    print(f'Salvo: {saida}')


if __name__ == '__main__':
    main()
