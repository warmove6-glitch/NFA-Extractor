"""OrgAudi 1.0 — Motor paramétrico de auditoria forense."""

from .orgaudi_adapter import gerar_laudo_orgaudi
from .orgaudi_tipologias import (
    CATALOGO_ANOMALIAS,
    Anomalia,
    CodigoAnomalia,
    EixoAnomalia,
    Gravidade,
    buscar_por_eixo,
    buscar_por_gravidade,
)
from .orgaudi_v4 import (
    Achado,
    CategoriaContabil,
    Contribuinte,
    Etapa,
    LaudoOrgAudi,
    NaturezaNota,
    NotaFiscal,
    Periodo,
    PlanilhaMensal,
    ResumoFiscal,
    Severidade,
    apurar_resumo,
    classificar_nota,
    construir_planilha_mensal,
    fmt_brl,
    hash_laudo,
    mascara_cnpj,
    mascara_cpf,
    teste_t01_concentracao,
    teste_t02_smurfing,
    teste_t04_concentracao_pf,
    teste_t07_documental,
    validar_cnpj,
    validar_cpf,
)

__all__ = [
    "LaudoOrgAudi", "Contribuinte", "Periodo", "NotaFiscal", "NaturezaNota",
    "CategoriaContabil", "Severidade", "Achado", "Etapa", "ResumoFiscal",
    "PlanilhaMensal", "classificar_nota", "apurar_resumo",
    "construir_planilha_mensal", "teste_t01_concentracao", "teste_t02_smurfing",
    "teste_t04_concentracao_pf", "teste_t07_documental", "hash_laudo",
    "validar_cpf", "validar_cnpj", "mascara_cpf", "mascara_cnpj", "fmt_brl",
    "CATALOGO_ANOMALIAS", "EixoAnomalia", "Gravidade", "CodigoAnomalia",
    "Anomalia", "buscar_por_eixo", "buscar_por_gravidade",
    "gerar_laudo_orgaudi",
]
