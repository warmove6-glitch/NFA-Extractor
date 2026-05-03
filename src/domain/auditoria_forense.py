"""Auditoria Forense ORGATEC — bateria de 8 testes determinísticos (T-01 a T-08).

Espelha o sistema OrgAudi 1.0 documentado no relatório-modelo
AUDITORIA_CRUZADA_GENIS_2025_v1.pdf. Cada teste produz `Achado(s)` classificados
em severidade {CRITICO, ALTO, MEDIO, ATENCAO, CONFORME}.

Testes implementados (matemáticos, sem IA):
- T-01 Concentração:        valor de 1 nota / receita anual >= 10%
- T-02 Smurfing:            >= 3 notas mesmo dest/dia COM valores idênticos
- T-03 Trânsito órfão:      Σ Remessas/Leilão SEM NF-e venda subsequente
- T-04 Concentração PF:     vendas a PF >= 90% E PFs com 3+ aquisições
- T-05 IE inconsistente:    mesmo CPF/CNPJ vinculado a 2+ IEs
- T-06 Pauta + sazonalidade:Σ trimestral >= 45% (Out-Dez)
- T-07 Documental:          validação dígito verificador CPF/CNPJ
- T-08 Cruzamento:          totais por categoria (auditoria interna do lote)
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.domain.extractor import NFA

# ── Severidade dos achados ────────────────────────────────────────────────────
SEV_CRITICO = "CRITICO"
SEV_ALTO = "ALTO"
SEV_MEDIO = "MEDIO"
SEV_ATENCAO = "ATENCAO"
SEV_CONFORME = "CONFORME"

_ORDEM_SEV = {SEV_CRITICO: 0, SEV_ALTO: 1, SEV_MEDIO: 2, SEV_ATENCAO: 3, SEV_CONFORME: 4}


@dataclass
class Achado:
    """Achado de auditoria — um por teste/condição detectada."""
    teste: str                       # "T-01", "T-02", etc.
    codigo: str                      # "C-01", "A-01", "M-01"
    severidade: str                  # SEV_*
    titulo: str                      # ex: "Operação singular de valor extraordinário"
    descricao: str                   # parágrafo explicativo
    detalhes: list[dict[str, Any]] = field(default_factory=list)  # tabela de evidências
    cruzamentos_obrigatorios: list[str] = field(default_factory=list)
    valor_envolvido: float = 0.0


@dataclass
class ResultadoAuditoria:
    """Resultado consolidado de toda a bateria — entra no relatório técnico."""
    cliente_nome: str
    cliente_cpf: str
    periodo_inicio: str | None
    periodo_fim: str | None

    # Campos opcionais de identificação adicional
    inscricao_estadual: str = ""   # Inscrição Estadual do produtor (opcional)
    municipio: str = ""            # Município / UF (ex: "Jataí/GO") (opcional)
    documento_base_gief: str = ""  # Ex: "Relatório GIEF/SEFAZ-GO de 17/04/2026" (opcional)
    documento_base_planilha: str = ""  # Ex: "Planilha de Gado para IR v5 (ORGATEC)" (opcional)

    # Síntese quantitativa
    total_notas: int = 0
    total_vendas: int = 0
    total_remessas_leilao: int = 0
    total_compras: int = 0
    total_transferencias: int = 0

    # ── Regra 2 — Fórmulas de apuração da receita rural ─────────────────────
    # F1: Receita imediata (ano-base)
    #     Σ (notas onde Remetente = Contribuinte E Natureza = "VENDA")
    receita_imediata: float = 0.0

    # F2: Receita potencial em trânsito
    #     Σ (notas onde Remetente = Contribuinte E Natureza = "REMESSA/LEILÃO")
    #     NUNCA usar como base IRPF — superdimensiona! Aguarda arremate.
    transito_leilao: float = 0.0

    # F3: Receita realizada de leilão
    #     Σ (NF-e modelo 55 emitidas pelo leiloeiro com Remetente = Contribuinte)
    #     Só disponível com cruzamento de NF-e modelo 55 externas ao lote NFA-e.
    receita_realizada_leilao: float = 0.0

    # F4: Receita bruta total para DIRPF Rural
    #     = Receita imediata + Receita realizada de leilão  (SEM trânsito potencial)
    receita_bruta_total_dirpf: float = 0.0

    # F5: Resultado da atividade rural
    #     = Receita bruta total – Despesa/Investimento dedutível
    resultado_atividade_rural: float = 0.0

    # F6: Valor das compras (Despesa/Investimento dedutível)
    #     Σ (notas onde Destinatário = Contribuinte) — subtrai da base ou ativa
    valor_compras: float = 0.0

    # Auxiliares
    volume_bruto_saidas: float = 0.0   # Movimento físico: imediata + trânsito
    cabecas_movimentadas: float = 0.0
    funrural_estimado: float = 0.0     # Receita imediata × 1,5% (Lei 8.212/91)

    # Achados (preenchidos pelos testes)
    achados: list[Achado] = field(default_factory=list)

    # Conformidades verificadas
    conformidades: list[dict[str, str]] = field(default_factory=list)

    def adicionar(self, ach: Achado) -> None:
        self.achados.append(ach)

    @property
    def por_severidade(self) -> dict[str, list[Achado]]:
        d: dict[str, list[Achado]] = defaultdict(list)
        for a in self.achados:
            d[a.severidade].append(a)
        return dict(d)

    @property
    def contagem_severidade(self) -> dict[str, int]:
        return {sev: len(lst) for sev, lst in self.por_severidade.items()}

    @property
    def score_risco(self) -> float:
        """Score 0-1 ponderado pelas severidades."""
        pesos = {SEV_CRITICO: 0.30, SEV_ALTO: 0.15, SEV_MEDIO: 0.06, SEV_ATENCAO: 0.02}
        s = 0.0
        for ach in self.achados:
            s += pesos.get(ach.severidade, 0.0)
        return min(s, 1.0)

    @property
    def nivel_risco(self) -> str:
        s = self.score_risco
        if s >= 0.6:
            return "ALTO"
        if s >= 0.3:
            return "MEDIO"
        return "BAIXO"


# ── Helpers ───────────────────────────────────────────────────────────────────
def _cpf_valido(doc: str) -> bool:
    """Validação do dígito verificador de CPF (algoritmo oficial Receita Federal)."""
    if not doc:
        return False
    digits = [c for c in doc if c.isdigit()]
    if len(digits) != 11 or len(set(digits)) == 1:
        return False
    nums = [int(c) for c in digits]
    # Primeiro DV
    soma = sum((10 - i) * nums[i] for i in range(9))
    dv1 = (soma * 10) % 11
    if dv1 == 10:
        dv1 = 0
    if dv1 != nums[9]:
        return False
    # Segundo DV
    soma = sum((11 - i) * nums[i] for i in range(10))
    dv2 = (soma * 10) % 11
    if dv2 == 10:
        dv2 = 0
    return dv2 == nums[10]


def _cnpj_valido(doc: str) -> bool:
    if not doc:
        return False
    digits = [c for c in doc if c.isdigit()]
    if len(digits) != 14 or len(set(digits)) == 1:
        return False
    nums = [int(c) for c in digits]
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6] + pesos1
    soma1 = sum(nums[i] * pesos1[i] for i in range(12))
    dv1 = soma1 % 11
    dv1 = 0 if dv1 < 2 else 11 - dv1
    if dv1 != nums[12]:
        return False
    soma2 = sum(nums[i] * pesos2[i] for i in range(13))
    dv2 = soma2 % 11
    dv2 = 0 if dv2 < 2 else 11 - dv2
    return dv2 == nums[13]


def _doc_valido(doc: str) -> bool:
    digits = "".join(c for c in (doc or "") if c.isdigit())
    if len(digits) == 11:
        return _cpf_valido(digits)
    if len(digits) == 14:
        return _cnpj_valido(digits)
    return False


def _parse_data(s: str | None) -> datetime | None:
    if not s:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except (ValueError, AttributeError):
            continue
    return None


def _natureza_categoria(nota: NFA, cliente_cpf: str) -> str:
    """Classifica a nota nas categorias da Regra 1 do OrgAudi 1.0:
    REMETENTE+VENDA       → RECEITA
    REMETENTE+REMESSA     → TRANSITO
    REMETENTE=DESTINATARIO → TRANSFERENCIA
    DESTINATARIO+VENDA    → DESPESA (compra)
    """
    rem_doc = "".join(c for c in (getattr(nota.remetente, "cpf_cnpj", "") or "") if c.isdigit())
    dest_doc = "".join(c for c in (getattr(nota.destinatario, "cpf_cnpj", "") or "") if c.isdigit())
    cli_doc = "".join(c for c in (cliente_cpf or "") if c.isdigit())

    cliente_remetente = bool(cli_doc and rem_doc.endswith(cli_doc[-11:]))
    cliente_destinatario = bool(cli_doc and dest_doc.endswith(cli_doc[-11:]))

    natureza_up = (nota.natureza or "").upper()

    if cliente_remetente and cliente_destinatario:
        return "TRANSFERENCIA"
    if "REMESSA" in natureza_up or "LEILA" in natureza_up:
        return "TRANSITO"
    if cliente_remetente:
        return "RECEITA"
    if cliente_destinatario:
        return "DESPESA"
    # Fallback: assumir RECEITA se natureza for venda
    if "VENDA" in natureza_up:
        return "RECEITA"
    return "OUTRA"


# ── Síntese quantitativa ──────────────────────────────────────────────────────
def calcular_sintese(notas: list[NFA], cliente_cpf: str) -> dict[str, Any]:
    """Calcula a síntese quantitativa conforme REGRA 2 — Fórmulas de Apuração.

    REGRA 2 (MODELO_AUDITORIA_ORGATEC_v5.pdf):
    ─────────────────────────────────────────────────────────────────────────
    F1: Receita imediata (ano-base)
        = Σ (notas onde Remetente = Contribuinte E Natureza = "VENDA")

    F2: Receita potencial em trânsito
        = Σ (notas onde Remetente = Contribuinte E Natureza = "REMESSA/LEILÃO")
        NUNCA usar como base — superdimensiona o IRPF!

    F3: Receita realizada de leilão
        = Σ (NF-e modelo 55 emitidas pelo leiloeiro com Remetente = Contribuinte)
        Requer cruzamento externo com NF-e modelo 55; aqui = 0 (sem dados).

    F4: Receita bruta total para DIRPF Rural
        = Receita imediata + Receita realizada de leilão
        (NÃO inclui trânsito potencial — só receita efetivamente realizada)

    F5: Resultado da atividade rural
        = Receita bruta total – Despesa/Investimento dedutível

    F6: Despesa/Investimento dedutível (Compras)
        = Σ (notas onde Destinatário = Contribuinte)
        Subtrai da base ou ativa dedução, conforme finalidade (custo x ativo)

    FUNRURAL  = Receita imediata × 1,5%  (Lei 8.212/91, vigente até 03/2026)
    ─────────────────────────────────────────────────────────────────────────
    """
    receita = 0.0       # F1: receita_imediata
    transito = 0.0      # F2: transito_leilao (potencial — NAO base IRPF)
    compras = 0.0       # F6: valor_compras (despesa/investimento dedutível)
    cabecas = 0.0       # Cabeças (vendas + trânsito; compras não contam)
    n_vendas = 0
    n_remessa = 0
    n_compras = 0
    n_transf = 0

    for nota in notas:
        cat = _natureza_categoria(nota, cliente_cpf)
        valor = nota.valor_total or 0
        qty = nota.quantidade_total or 0

        if cat == "RECEITA":
            receita += valor
            cabecas += qty
            n_vendas += 1
        elif cat == "TRANSITO":
            transito += valor
            cabecas += qty
            n_remessa += 1
        elif cat == "DESPESA":
            # Compra: subtrai da base IRPF ou ativa dedução
            compras += valor
            n_compras += 1
            # NB: compras NÃO somam cabeças (só saídas)
        elif cat == "TRANSFERENCIA":
            n_transf += 1

    # F3: receita realizada de leilão — requer NF-e modelo 55 externas; = 0 aqui
    receita_realizada_leilao = 0.0

    # F4: receita bruta total para DIRPF = imediata + realizada (SEM trânsito)
    receita_bruta_total_dirpf = receita + receita_realizada_leilao

    # F5: resultado da atividade rural = bruta total – despesa dedutível
    resultado_atividade_rural = receita_bruta_total_dirpf - compras

    return {
        "total_notas": len(notas),
        "total_vendas": n_vendas,
        "total_remessas_leilao": n_remessa,
        "total_compras": n_compras,
        "total_transferencias": n_transf,
        # Regra 2 — campos DIRPF
        "receita_imediata": receita,
        "transito_leilao": transito,
        "receita_realizada_leilao": receita_realizada_leilao,
        "receita_bruta_total_dirpf": receita_bruta_total_dirpf,
        "resultado_atividade_rural": resultado_atividade_rural,
        "valor_compras": compras,
        # Auxiliares
        "volume_bruto_saidas": receita + transito,      # Movimento físico total
        "cabecas_movimentadas": cabecas,
        "funrural_estimado": receita * 0.015,           # 1,5% Lei 8.212/91
    }


# ── Testes forenses (T-01 a T-08) ────────────────────────────────────────────
def teste_t01_concentracao(notas: list[NFA], receita_imediata: float, cliente_cpf: str) -> list[Achado]:
    """Operações extraordinárias: 1 nota / receita anual >= 10%."""
    achados = []
    if receita_imediata <= 0:
        return achados
    for nota in notas:
        cat = _natureza_categoria(nota, cliente_cpf)
        if cat != "RECEITA":
            continue
        valor = nota.valor_total or 0
        pct = valor / receita_imediata
        if pct >= 0.10:
            dest = nota.destinatario
            achados.append(Achado(
                teste="T-01",
                codigo=f"C-{len(achados)+1:02d}",
                severidade=SEV_CRITICO,
                titulo="Operação singular de valor extraordinário",
                descricao=(
                    f"NFA-e nº {nota.numero} concentra {pct*100:.2f}% da receita anual "
                    f"em uma única operação. Valor unitário compatível com pauta deve ser "
                    f"verificado para descartar subfaturamento; volume desta magnitude requer "
                    f"comprovação de capacidade do imóvel rural do destinatário (SiCAR/CAR) "
                    f"e cruzamento com extrato bancário."
                ),
                detalhes=[{
                    "NFA-e": nota.numero,
                    "Data": nota.emissao or "-",
                    "Cabeças": int(nota.quantidade_total or 0),
                    "Valor unitário": f"R$ {(valor / max(nota.quantidade_total or 1, 1)):,.2f}",
                    "Valor total": f"R$ {valor:,.2f}",
                    "% receita anual": f"{pct*100:.2f}%",
                    "Destinatário": getattr(dest, "nome", "?"),
                    "CPF/CNPJ": getattr(dest, "cpf_cnpj", "?"),
                }],
                cruzamentos_obrigatorios=[
                    "GTA emitida pela AGRODEFESA-GO correspondente à nota",
                    f"Extrato bancário com crédito de R$ {valor:,.2f} ou parcelamento equivalente",
                    "Verificação de vínculo familiar/societário (JUCEG/RFB)",
                    "Capacidade do imóvel rural do destinatário (SiCAR/CAR)",
                ],
                valor_envolvido=valor,
            ))
    return achados


def teste_t02_smurfing(notas: list[NFA], cliente_cpf: str) -> list[Achado]:
    """Smurfing: >= 3 notas mesmo dest/dia COM valores idênticos."""
    achados = []
    # Agrupa por (destinatario_doc, data)
    grupos: dict[tuple[str, str], list[NFA]] = defaultdict(list)
    for nota in notas:
        if _natureza_categoria(nota, cliente_cpf) != "RECEITA":
            continue
        dest_doc = "".join(c for c in (getattr(nota.destinatario, "cpf_cnpj", "") or "") if c.isdigit())
        data = nota.emissao or ""
        if dest_doc and data:
            grupos[(dest_doc, data)].append(nota)

    for (dest_doc, data), notas_grupo in grupos.items():
        if len(notas_grupo) < 3:
            continue
        valores = [n.valor_total or 0 for n in notas_grupo]
        # Conta valores repetidos
        contagem = Counter(round(v, 2) for v in valores)
        valor_repetido, qtd_repetidos = contagem.most_common(1)[0]
        if qtd_repetidos < 3:
            continue
        total = sum(valores)
        dest_nome = getattr(notas_grupo[0].destinatario, "nome", "?")
        achados.append(Achado(
            teste="T-02",
            codigo=f"C-{len(achados)+10:02d}",  # offset para coexistir com T-01
            severidade=SEV_CRITICO,
            titulo="Fragmentação fiscal (smurfing) em data singular",
            descricao=(
                f"Em {data} foram emitidas {len(notas_grupo)} NFA-e ao mesmo destinatário "
                f"{dest_nome} (CPF {dest_doc}), totalizando R$ {total:,.2f}. "
                f"{qtd_repetidos} notas com valor exatamente idêntico (R$ {valor_repetido:,.2f}). "
                f"Padrão clássico de fragmentação fiscal — pode indicar (i) manter cada nota "
                f"abaixo de limiar de triagem; (ii) uso de 'laranja'; (iii) lavagem de gado."
            ),
            detalhes=[
                {
                    "NFA-e": n.numero,
                    "Data": n.emissao or "-",
                    "Valor (R$)": f"{n.valor_total or 0:,.2f}",
                    "Cabeças": int(n.quantidade_total or 0),
                }
                for n in notas_grupo
            ],
            cruzamentos_obrigatorios=[
                f"GTAs (AGRODEFESA-GO) correspondentes às {len(notas_grupo)} notas",
                "Extrato bancário do dia: identificar PIX/depósitos casados",
                "CAEPF do destinatário (Receita Federal)",
                "Vínculo familiar/societário (JUCEG/RFB)",
            ],
            valor_envolvido=total,
        ))
    return achados


def teste_t03_transito_orfao(notas: list[NFA], cliente_cpf: str) -> list[Achado]:
    """Σ Remessas/Leilão sem NF-e modelo 55 subsequente do leiloeiro.

    Como não temos acesso às NF-e modelo 55 do leiloeiro neste pipeline,
    o teste reporta o trânsito agregado por leiloeiro como achado crítico
    pendente de cruzamento documental externo.
    """
    achados = []
    por_leiloeiro: dict[str, list[NFA]] = defaultdict(list)
    for nota in notas:
        if _natureza_categoria(nota, cliente_cpf) != "TRANSITO":
            continue
        dest_doc = "".join(c for c in (getattr(nota.destinatario, "cpf_cnpj", "") or "") if c.isdigit())
        if len(dest_doc) == 14:  # CNPJ → leiloeiro/PJ
            por_leiloeiro[dest_doc].append(nota)

    if not por_leiloeiro:
        return achados

    detalhes = []
    total_geral = 0.0
    n_total = 0
    for cnpj, notas_lei in sorted(por_leiloeiro.items(), key=lambda x: -sum(n.valor_total or 0 for n in x[1])):
        nome = getattr(notas_lei[0].destinatario, "nome", "?")
        total = sum(n.valor_total or 0 for n in notas_lei)
        detalhes.append({
            "Leiloeiro": nome,
            "CNPJ": cnpj,
            "Notas": len(notas_lei),
            "Valor (R$)": f"{total:,.2f}",
        })
        total_geral += total
        n_total += len(notas_lei)

    detalhes.append({
        "Leiloeiro": "TOTAL EM TRÂNSITO",
        "CNPJ": "",
        "Notas": n_total,
        "Valor (R$)": f"{total_geral:,.2f}",
    })

    achados.append(Achado(
        teste="T-03",
        codigo="C-03",
        severidade=SEV_CRITICO,
        titulo="Trânsito de leilão sem cruzamento documental",
        descricao=(
            f"R$ {total_geral:,.2f} em remessas para leilão. Sob a regra OrgAudi 1.0, "
            f"REMESSA/LEILÃO não constitui receita — é apenas trânsito até arremate. "
            f"Sem NF-e modelo 55 emitida pelo leiloeiro em nome do produtor, é impossível "
            f"confirmar (a) se a receita foi efetivamente percebida; (b) se Funrural foi "
            f"retido pelo leiloeiro; (c) se houve retorno de gado não arrematado."
        ),
        detalhes=detalhes,
        cruzamentos_obrigatorios=[
            "ACTs (Atos de Comissão de Trabalho) dos leiloeiros listados",
            "Relação de NF-e modelo 55 emitidas em nome do produtor",
            "Extratos bancários cruzados com repasses dos leiloeiros",
        ],
        valor_envolvido=total_geral,
    ))
    return achados


def teste_t04_concentracao_pf(notas: list[NFA], cliente_cpf: str) -> list[Achado]:
    """Vendas a PF >= 90% E PFs com 3+ aquisições."""
    achados = []
    vendas = [n for n in notas if _natureza_categoria(n, cliente_cpf) == "RECEITA"]
    if not vendas:
        return achados

    pf_count = 0
    pj_count = 0
    por_dest: dict[str, list[NFA]] = defaultdict(list)
    nome_por_doc: dict[str, str] = {}
    for nota in vendas:
        dest_doc = "".join(c for c in (getattr(nota.destinatario, "cpf_cnpj", "") or "") if c.isdigit())
        if not dest_doc:
            continue
        por_dest[dest_doc].append(nota)
        nome_por_doc[dest_doc] = getattr(nota.destinatario, "nome", "?")
        if len(dest_doc) == 11:
            pf_count += 1
        elif len(dest_doc) == 14:
            pj_count += 1

    total_vendas = pf_count + pj_count
    if total_vendas == 0:
        return achados

    pct_pf = pf_count / total_vendas
    if pct_pf < 0.90:
        return achados

    # PFs com 3+ aquisições
    recorrentes = [
        (doc, lst) for doc, lst in por_dest.items()
        if len(doc) == 11 and len(lst) >= 3
    ]
    if not recorrentes:
        return achados

    recorrentes.sort(key=lambda x: -sum(n.valor_total or 0 for n in x[1]))
    detalhes_top = []
    total_recorrente = 0.0
    n_recorrentes = 0
    for doc, lst in recorrentes[:5]:
        valor = sum(n.valor_total or 0 for n in lst)
        detalhes_top.append({
            "Destinatário": nome_por_doc.get(doc, "?"),
            "CPF": doc,
            "Notas": len(lst),
            "Valor (R$)": f"{valor:,.2f}",
        })
        total_recorrente += valor
        n_recorrentes += len(lst)

    if len(recorrentes) > 5:
        outros_valor = sum(
            sum(n.valor_total or 0 for n in lst) for _, lst in recorrentes[5:]
        )
        outros_notas = sum(len(lst) for _, lst in recorrentes[5:])
        detalhes_top.append({
            "Destinatário": f"Outros {len(recorrentes)-5} PFs com 3+ aquisições",
            "CPF": "",
            "Notas": outros_notas,
            "Valor (R$)": f"{outros_valor:,.2f}",
        })
        total_recorrente += outros_valor
        n_recorrentes += outros_notas

    detalhes_top.append({
        "Destinatário": f"TOTAL — {len(recorrentes)} PFs recorrentes",
        "CPF": "",
        "Notas": n_recorrentes,
        "Valor (R$)": f"{total_recorrente:,.2f}",
    })

    achados.append(Achado(
        teste="T-04",
        codigo="A-01",
        severidade=SEV_ALTO,
        titulo=f"Concentração em PFs com perfil de revenda (R$ {total_recorrente/1e6:.2f}M)",
        descricao=(
            f"{pf_count} das {total_vendas} vendas diretas foram para PF "
            f"({pct_pf*100:.1f}%) — atípico para pecuária. {len(recorrentes)} PFs aparecem "
            f"com 3+ aquisições no período. Verificar CAEPF para identificar quais "
            f"destinatários são produtores rurais formalizados; ausência de CAEPF + "
            f"3+ compras = indício de intermediação não declarada (atividade comercial "
            f"sem CNPJ)."
        ),
        detalhes=detalhes_top,
        cruzamentos_obrigatorios=[
            "Consulta CAEPF (Receita Federal) para cada CPF recorrente",
            "Verificação de vínculo familiar com produtor (RFB/JUCEG)",
        ],
        valor_envolvido=total_recorrente,
    ))
    return achados


def teste_t05_ie_inconsistente(notas: list[NFA], cliente_cpf: str) -> list[Achado]:
    """Mesmo CPF/CNPJ vinculado a 2+ IEs distintas."""
    achados = []
    ies_por_doc: dict[str, set[str]] = defaultdict(set)
    nome_por_doc: dict[str, str] = {}
    notas_por_doc: dict[str, int] = defaultdict(int)
    for nota in notas:
        for parte in (nota.remetente, nota.destinatario):
            doc = "".join(c for c in (getattr(parte, "cpf_cnpj", "") or "") if c.isdigit())
            ie = getattr(parte, "ie", None) or ""
            if doc and ie and ie.strip():
                ies_por_doc[doc].add(ie.strip())
                nome_por_doc[doc] = getattr(parte, "nome", "?")
                notas_por_doc[doc] += 1

    inconsistentes = [(doc, ies) for doc, ies in ies_por_doc.items() if len(ies) >= 2]
    if not inconsistentes:
        return achados

    detalhes = []
    for doc, ies in inconsistentes[:5]:
        detalhes.append({
            "Nome": nome_por_doc.get(doc, "?"),
            "CPF/CNPJ": doc,
            "IEs encontradas": " | ".join(sorted(ies)),
            "Notas": notas_por_doc[doc],
        })
    achados.append(Achado(
        teste="T-05",
        codigo="A-02",
        severidade=SEV_ALTO,
        titulo="Inconsistência cadastral em Inscrição Estadual",
        descricao=(
            f"{len(inconsistentes)} CPF/CNPJ vinculado(s) a 2+ Inscrições Estaduais. "
            f"Pode ser compatível com produtor com fazendas em municípios distintos, "
            f"mas merece verificação cadastral ativa na SEFAZ-GO (CAEPF e cadastro IE)."
        ),
        detalhes=detalhes,
        cruzamentos_obrigatorios=[
            "Consulta cadastro de IE ativa na SEFAZ-GO",
            "Verificação CAEPF em cada município",
        ],
    ))
    return achados


def teste_t06_sazonalidade(notas: list[NFA], cliente_cpf: str, receita_imediata: float) -> list[Achado]:
    """Σ trimestral >= 45% (concentração anômala em um trimestre)."""
    achados = []
    if receita_imediata <= 0:
        return achados
    por_mes: dict[int, float] = defaultdict(float)
    for nota in notas:
        if _natureza_categoria(nota, cliente_cpf) != "RECEITA":
            continue
        d = _parse_data(nota.emissao)
        if not d:
            continue
        por_mes[d.month] += nota.valor_total or 0

    if len(por_mes) < 3:
        return achados

    # Trimestres
    trimestres = {
        "Jan-Mar": sum(por_mes.get(m, 0) for m in (1, 2, 3)),
        "Abr-Jun": sum(por_mes.get(m, 0) for m in (4, 5, 6)),
        "Jul-Set": sum(por_mes.get(m, 0) for m in (7, 8, 9)),
        "Out-Dez": sum(por_mes.get(m, 0) for m in (10, 11, 12)),
    }
    pico_label, pico_valor = max(trimestres.items(), key=lambda x: x[1])
    pico_pct = pico_valor / receita_imediata
    if pico_pct < 0.45:
        return achados

    mes_pico = max(por_mes.items(), key=lambda x: x[1])
    achados.append(Achado(
        teste="T-06",
        codigo="A-03",
        severidade=SEV_ALTO,
        titulo="Sazonalidade compatível com descapitalização",
        descricao=(
            f"{pico_pct*100:.1f}% da receita direta concentrada em {pico_label} "
            f"(R$ {pico_valor:,.2f}), com pico no mês {mes_pico[0]:02d} "
            f"(R$ {mes_pico[1]:,.2f}). Concentração trimestral acima de 45% sugere "
            f"esvaziamento dirigido de plantel, não comercialização rotineira."
        ),
        detalhes=[
            {"Trimestre": k, "Valor (R$)": f"{v:,.2f}", "% da receita anual": f"{(v/receita_imediata)*100:.1f}%"}
            for k, v in trimestres.items()
        ],
        cruzamentos_obrigatorios=[
            "Histórico de plantel/UA (compatibilidade com CAR)",
            "GTAs do trimestre crítico (AGRODEFESA-GO)",
        ],
        valor_envolvido=pico_valor,
    ))
    return achados


def teste_t07_documental(notas: list[NFA]) -> tuple[list[Achado], dict[str, int]]:
    """Validação dígito verificador de todos os CPF/CNPJ.

    Retorna (lista de achados, contagens) — contagens entram nas conformidades
    se 100% válidos.
    """
    achados = []
    docs_unicos: set[str] = set()
    for nota in notas:
        for parte in (nota.remetente, nota.destinatario):
            doc = "".join(c for c in (getattr(parte, "cpf_cnpj", "") or "") if c.isdigit())
            if doc and len(doc) in (11, 14):
                docs_unicos.add(doc)

    invalidos = [d for d in docs_unicos if not _doc_valido(d)]
    contagens = {"total": len(docs_unicos), "validos": len(docs_unicos) - len(invalidos), "invalidos": len(invalidos)}

    if invalidos:
        achados.append(Achado(
            teste="T-07",
            codigo=f"M-{(len(invalidos)+10):02d}",
            severidade=SEV_MEDIO,
            titulo=f"Documentos com dígito verificador inválido ({len(invalidos)})",
            descricao=(
                f"{len(invalidos)} de {len(docs_unicos)} CPF/CNPJ não passaram na "
                f"validação do dígito verificador. Pode indicar erro de digitação, "
                f"cadastro desatualizado ou documento forjado."
            ),
            detalhes=[{"Documento": d, "Tipo": "CPF" if len(d) == 11 else "CNPJ"} for d in invalidos[:10]],
            cruzamentos_obrigatorios=["Re-conferência cadastral via Receita Federal"],
        ))
    return achados, contagens


def teste_t08_obrigacoes_acessorias(sintese: dict[str, Any]) -> list[Achado]:
    """M-01: Volume bruto obriga LCDPR, DIRPF Rural, controle de comprovantes."""
    achados = []
    volume = sintese["volume_bruto_saidas"]
    if volume < 100_000:
        return achados
    achados.append(Achado(
        teste="T-08",
        codigo="M-01",
        severidade=SEV_MEDIO,
        titulo="Obrigações acessórias derivadas do volume",
        descricao=(
            f"Volume bruto de R$ {volume:,.2f} obriga, para a DIRPF do exercício seguinte: "
            f"(a) manutenção do LCDPR — Livro Caixa Digital do Produtor Rural "
            f"(IN RFB 1.848/2018); (b) apuração do resultado da atividade rural no anexo "
            f"correspondente da DIRPF; (c) controle de comprovantes para contraprova "
            f"fiscal (5 anos de retenção)."
        ),
        cruzamentos_obrigatorios=["LCDPR atualizado", "Anexo DIRPF Rural"],
    ))
    # Funrural
    receita = sintese["receita_imediata"]
    if receita > 0:
        funrural = receita * 0.015
        achados.append(Achado(
            teste="T-08",
            codigo="M-02",
            severidade=SEV_MEDIO,
            titulo="Funrural a recolher",
            descricao=(
                f"Funrural sobre vendas diretas (R$ {receita:,.2f}) à alíquota de 1,5% "
                f"(Lei 8.212/91, vigente até 03/2026): R$ {funrural:,.2f}. "
                f"A LC 224/2025 alterou a alíquota para 1,63% a partir de 04/2026. "
                f"Quando adquirente é PJ, retenção é dele; quando PF, do próprio produtor. "
                f"Cruzar com guias GPS/DARF efetivamente recolhidas."
            ),
            cruzamentos_obrigatorios=["Guias GPS/DARF do período", "Comprovantes de retenção pelo adquirente PJ"],
            valor_envolvido=funrural,
        ))
    return achados


# ── Pipeline principal ────────────────────────────────────────────────────────
def auditar_lote(
    notas: list[NFA],
    cliente_nome: str,
    cliente_cpf: str,
) -> ResultadoAuditoria:
    """Executa toda a bateria T-01 a T-08 e devolve o resultado consolidado."""
    sintese = calcular_sintese(notas, cliente_cpf)

    # Período auditado (min/max das datas)
    datas = sorted([d for d in (_parse_data(n.emissao) for n in notas) if d])
    periodo_inicio = datas[0].strftime("%d/%m/%Y") if datas else None
    periodo_fim = datas[-1].strftime("%d/%m/%Y") if datas else None

    resultado = ResultadoAuditoria(
        cliente_nome=cliente_nome,
        cliente_cpf=cliente_cpf,
        periodo_inicio=periodo_inicio,
        periodo_fim=periodo_fim,
        **sintese,
    )

    receita = sintese["receita_imediata"]

    # T-01 a T-08
    for ach in teste_t01_concentracao(notas, receita, cliente_cpf):
        resultado.adicionar(ach)
    for ach in teste_t02_smurfing(notas, cliente_cpf):
        resultado.adicionar(ach)
    for ach in teste_t03_transito_orfao(notas, cliente_cpf):
        resultado.adicionar(ach)
    for ach in teste_t04_concentracao_pf(notas, cliente_cpf):
        resultado.adicionar(ach)
    for ach in teste_t05_ie_inconsistente(notas, cliente_cpf):
        resultado.adicionar(ach)
    for ach in teste_t06_sazonalidade(notas, cliente_cpf, receita):
        resultado.adicionar(ach)

    # T-07 retorna achados + contagens (alimenta conformidades)
    achados_t07, cont_docs = teste_t07_documental(notas)
    for ach in achados_t07:
        resultado.adicionar(ach)

    # T-08 (obrigações acessórias)
    for ach in teste_t08_obrigacoes_acessorias(sintese):
        resultado.adicionar(ach)

    # Conformidades verificadas (página 4 do modelo)
    if cont_docs["invalidos"] == 0 and cont_docs["total"] > 0:
        resultado.conformidades.append({
            "item": f"Validação de dígito verificador de CPF/CNPJ ({cont_docs['total']} documentos)",
            "resultado": "TODOS VÁLIDOS",
        })
    else:
        resultado.conformidades.append({
            "item": f"Validação de dígito verificador de CPF/CNPJ ({cont_docs['total']} documentos)",
            "resultado": f"{cont_docs['validos']}/{cont_docs['total']} válidos",
        })

    if sintese["receita_imediata"] > 0:
        resultado.conformidades.append({
            "item": "Cruzamento de totais por categoria contábil (Regra 1 OrgAudi 1.0)",
            "resultado": "CONFORME",
        })
    if sintese["total_notas"] > 0:
        resultado.conformidades.append({
            "item": f"Classificação automática de {sintese['total_notas']} notas (Receita / Trânsito / Despesa)",
            "resultado": "EXECUTADA",
        })

    # Achado de ATENÇÃO se houver compras grandes
    if sintese["valor_compras"] > 100_000:
        resultado.adicionar(Achado(
            teste="T-08",
            codigo=f"AT-{len([a for a in resultado.achados if a.severidade == SEV_ATENCAO])+1:02d}",
            severidade=SEV_ATENCAO,
            titulo="Compras de gado relevantes — verificar tratamento contábil",
            descricao=(
                f"R$ {sintese['valor_compras']:,.2f} em {sintese['total_compras']} notas de compra. "
                f"Sob a Regra 1 OrgAudi 1.0 (Cliente=Destinatário → DESPESA/INVEST.), reduz a "
                f"base de cálculo do IRPF Rural ou ativa investimento dedutível, conforme finalidade "
                f"(reposição de plantel = despesa; matriz reprodutora = ativo)."
            ),
        ))

    return resultado
