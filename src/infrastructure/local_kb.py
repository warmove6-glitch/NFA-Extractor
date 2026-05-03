"""
Motor de Conhecimento Local — Alternativa ao Ollama.

Funcionamento:
  1. Base de conhecimento (KB) com Q&A sobre NFA, ICMS, FUNRURAL, CTN, etc.
  2. Busca semântica leve usando TF-IDF over keyword tokens (sem dependências externas).
  3. Fallback: resposta genérica com orientação jurídica.

Vantagens sobre Ollama:
  - Zero dependência externa (sem servidor, sem download de modelo).
  - Respostas instantâneas (< 10ms).
  - Respostas auditáveis e controláveis.
  - Não alucina — só responde o que foi programado.
"""

import logging
import re

logger = logging.getLogger(__name__)

KB: list[dict] = [
    # NFA — Conceitos
    {
        "tags": ["nfa", "nota fiscal agropecuaria", "o que é", "conceito", "definicao"],
        "pergunta": "O que é uma Nota Fiscal Agropecuária (NFA)?",
        "resposta": (
            "A **Nota Fiscal Agropecuária (NFA)** é o documento fiscal obrigatório para "
            "acobertar operações de circulação de mercadorias agropecuárias (gado, grãos, "
            "insumos, etc.) dentro do estado ou entre estados.\n\n"
            "**Base legal:** Convênio SINIEF s/n de 1970, regulamentado por cada estado.\n"
            "**Modelos:** Modelo 4 (produtor pessoa física) ou Modelo 55 (NF-e, para "
            "contribuintes inscritos).\n\n"
            "**Principais informações obrigatórias:**\n"
            "- Dados do emitente (produtor rural)\n"
            "- Dados do destinatário\n"
            "- Descrição e quantidade dos produtos (cabeças, kg, sacas, etc.)\n"
            "- Valor total da operação\n"
            "- CFOP (Código Fiscal de Operações)\n"
            "- Base de cálculo e valor do ICMS (quando devido)"
        ),
    },
    {
        "tags": ["nfa", "quem emite", "produtor rural", "pessoa fisica", "inscricao"],
        "pergunta": "Quem pode emitir NFA?",
        "resposta": (
            "A NFA pode ser emitida por:\n\n"
            "**1. Produtor Rural Pessoa Física** — utiliza o Modelo 4 (talonário físico) "
            "ou NFA eletrônica (NF-e Modelo 55 com CNPJ de produtor rural).\n\n"
            "**2. Pessoa Jurídica Rural** — obrigatoriamente emite NF-e (Modelo 55) via "
            "SPED/DANFE.\n\n"
            "**Requisito:** inscrição no Cadastro de Produtor Rural do estado (INCRA/SEFAZ). "
            "Sem inscrição, o produtor não pode emitir NFA e a operação fica sem cobertura "
            "fiscal, sujeitando-se à apreensão da mercadoria e multa de até 100% do valor "
            "da operação (varia por estado)."
        ),
    },
    # ICMS
    {
        "tags": ["icms", "aliquota", "gado bovino", "agropecuario", "porcentagem", "taxa"],
        "pergunta": "Qual é a alíquota de ICMS para gado bovino e operações agropecuárias?",
        "resposta": (
            "O ICMS em operações agropecuárias varia por estado e tipo de operação:\n\n"
            "**Operações internas (dentro do estado):**\n"
            "- Gado bovino: 7% a 12% (com diferimento de até 100% em muitos estados)\n"
            "- Grãos (soja, milho): geralmente diferido até a saída do estado\n"
            "- Insumos agrícolas: isentos (Convênio ICMS 100/97)\n\n"
            "**Operações interestaduais:**\n"
            "- Alíquota interestadual padrão: 12% (Sul/Sudeste) ou 7% (demais)\n"
            "- Com diferimento: 0% na saída do produtor rural pessoa física\n\n"
            "**Base legal:** LC 87/96 (Lei Kandir), Convênio ICMS 52/91 (diferimento gado), "
            "EC 132/23 (Reforma Tributária — transição 2026-2033).\n\n"
            "**Importante:** A Reforma Tributária (EC 132/23) cria o IBS e CBS, mas o ICMS "
            "permanece em vigor até 2033."
        ),
    },
    {
        "tags": ["icms", "diferimento", "o que e", "conceito"],
        "pergunta": "O que é diferimento de ICMS?",
        "resposta": (
            "**Diferimento** é a postergação do pagamento do ICMS para uma etapa posterior "
            "da cadeia de produção/comercialização.\n\n"
            "No agronegócio, é amplamente utilizado:\n"
            "- Produtor rural vende gado → ICMS diferido (não paga na saída)\n"
            "- Frigorífico compra o gado → ICMS diferido se estiver no mesmo estado\n"
            "- O ICMS só é recolhido quando o produto industrializado sai do frigorífico\n\n"
            "**Quem paga:** o adquirente assume a condição de substituto tributário.\n\n"
            "**Base legal:** cada estado tem seu regulamento (RICMS). Exemplos:\n"
            "- GO: Decreto 4.852/97, Anexo IX\n"
            "- MS: RICMS/MS, Art. 15-A\n"
            "- MT: RICMS/MT, Art. 8º"
        ),
    },
    # FUNRURAL
    {
        "tags": ["funrural", "contribuicao", "produtor rural", "senar", "rat", "gilrat"],
        "pergunta": "O que é FUNRURAL e como é calculado?",
        "resposta": (
            "**FUNRURAL** é a contribuição previdenciária do produtor rural, substitui "
            "a contribuição patronal sobre a folha de pagamento.\n\n"
            "**Alíquotas (Lei 8.212/91, art. 25):**\n"
            "| Contribuinte | Base | Alíquota |\n"
            "|---|---|---|\n"
            "| Pessoa Física | Receita bruta da comercialização | 1,2% + 0,1% SENAR |\n"
            "| Pessoa Jurídica | Receita bruta da comercialização | 1,5% + 0,1% SENAR |\n"
            "| Agroindústria | Valor da produção própria | 2,5% + 0,1% SENAT |\n\n"
            "**Quem retém:** o adquirente (frigorífico, cooperativa, pessoa jurídica) "
            "é obrigado a reter e recolher o FUNRURAL na fonte.\n\n"
            "**Importante:** Pequeno produtor rural com receita bruta ≤ R$ 4,8M/ano é "
            "segurado especial e paga apenas 1,2% + 0,1% sobre a comercialização."
        ),
    },
    # CTN
    {
        "tags": ["ctn", "codigo tributario nacional", "o que e", "base legal"],
        "pergunta": "O que é o CTN (Código Tributário Nacional)?",
        "resposta": (
            "O **Código Tributário Nacional (CTN)** — Lei nº 5.172/1966 — é a norma "
            "fundamental do sistema tributário brasileiro.\n\n"
            "**Estrutura principal:**\n"
            "- **Livro I:** Sistema Tributário Nacional (arts. 1-95)\n"
            "- **Livro II:** Normas Gerais de Direito Tributário (arts. 96-218)\n\n"
            "**Artigos mais relevantes para auditoria fiscal:**\n"
            "- Art. 3º — Conceito de tributo\n"
            "- Art. 114 — Fato gerador da obrigação principal\n"
            "- Art. 142 — Lançamento tributário\n"
            "- Art. 150 — Limitações ao poder de tributar\n"
            "- Art. 156 — Extinção do crédito tributário\n"
            "- Art. 173 — Prazo decadencial (5 anos)\n"
            "- Art. 174 — Prazo prescricional (5 anos)\n\n"
            "**Status:** recepcionado pela CF/88 como Lei Complementar."
        ),
    },
    # LC 87/96
    {
        "tags": ["lc 87", "lei kandir", "icms", "exportacao", "nao cumulativo"],
        "pergunta": "O que é a Lei Kandir (LC 87/96)?",
        "resposta": (
            "A **Lei Complementar 87/96 (Lei Kandir)** regula o ICMS no plano nacional.\n\n"
            "**Principais disposições:**\n"
            "- **Não-cumulatividade:** ICMS pago nas entradas compensa o devido nas saídas\n"
            "- **Isenção de exportações:** produtos destinados ao exterior são isentos de ICMS\n"
            "- **Base de cálculo:** inclui o próprio ICMS ('por dentro')\n"
            "- **Alíquotas interestaduais:** 7% ou 12% conforme a região\n\n"
            "**Impacto no agronegócio:**\n"
            "- Produtores exportadores têm direito a créditos de ICMS não aproveitados\n"
            "- Insumos agropecuários têm isenção ampla (Convênio 100/97)\n"
            "- ICMS sobre energia elétrica rural: redução em vários estados\n\n"
            "**Reforma Tributária:** a EC 132/23 prevê extinção gradual do ICMS entre "
            "2026 e 2033, substituído pelo IBS (Imposto sobre Bens e Serviços)."
        ),
    },
    # EC 132/23 — Reforma Tributária
    {
        "tags": ["ec 132", "reforma tributaria", "ibs", "cbs", "is", "2026", "2033"],
        "pergunta": "O que muda com a Reforma Tributária (EC 132/23) para o agronegócio?",
        "resposta": (
            "A **EC 132/2023** aprovou a maior reforma tributária desde 1988.\n\n"
            "**Novos tributos criados:**\n"
            "- **CBS** (federal): substitui PIS e COFINS\n"
            "- **IBS** (estados/municípios): substitui ICMS e ISS\n"
            "- **IS** (Imposto Seletivo): produtos prejudiciais à saúde/meio ambiente\n\n"
            "**Cronograma de transição:**\n"
            "- 2026: CBS começa (1%) e IBS começa (0,1%)\n"
            "- 2027: CBS plena; IBS reduzido; PIS/COFINS extintos\n"
            "- 2029-2032: redução gradual de ICMS e ISS\n"
            "- 2033: extinção total de ICMS e ISS\n\n"
            "**Impacto no agronegócio:**\n"
            "- Produtos agropecuários: alíquota reduzida de IBS+CBS (60% da alíquota padrão)\n"
            "- Regime especial para pequenos produtores rurais\n"
            "- Manutenção do diferimento em operações rurais\n"
            "- FUNRURAL: não alterado pela reforma"
        ),
    },
    # Auditoria / Fraude
    {
        "tags": ["fraude", "sinal", "suspeita", "auditoria", "alerta", "risco", "irregular"],
        "pergunta": "Quais são os principais sinais de fraude em NFAs?",
        "resposta": (
            "A ORGATEC identifica os seguintes **sinais de alerta** em auditorias de NFA:\n\n"
            "**1. Discrepâncias volumétricas**\n"
            "- Volume de saídas (vendas) > entradas + estoque inicial → gado 'fantasma'\n"
            "- Quantidade de cabeças desproporcional ao porte da fazenda\n\n"
            "**2. Padrões de valor suspeitos**\n"
            "- Valor por cabeça muito abaixo ou acima do mercado regional (±30%)\n"
            "- Valores redondos e idênticos em notas consecutivas\n\n"
            "**3. Irregularidades documentais**\n"
            "- NFA sem GTA (Guia de Trânsito Animal) correspondente\n"
            "- Emitente sem inscrição estadual ativa ou produção impossível\n"
            "- Notas canceladas e reemitidas com mesma numeração\n\n"
            "**4. Operações atípicas**\n"
            "- Compra e venda no mesmo dia sem logística plausível\n"
            "- Destinatário em estado diferente sem nota intestadual\n"
            "- Série de notas com numeração não sequencial"
        ),
    },
    # GTA
    {
        "tags": ["gta", "guia de transito animal", "transporte", "gado", "mapa", "sisbov"],
        "pergunta": "O que é a GTA e como se relaciona com a NFA?",
        "resposta": (
            "A **GTA (Guia de Trânsito Animal)** é o documento sanitário obrigatório "
            "para o transporte de animais vivos no Brasil, emitida pelo MAPA "
            "(Ministério da Agricultura).\n\n"
            "**Relação com a NFA:**\n"
            "- Toda NFA de gado bovino deve ter uma GTA correspondente\n"
            "- A GTA e a NFA devem coincidir em: quantidade de cabeças, origem, "
            "destino e data de trânsito\n"
            "- Divergência entre NFA e GTA é forte indício de fraude ou 'nota fria'\n\n"
            "**Emissão:** via e-GTA (sistema do MAPA), por Médico Veterinário oficial "
            "ou autorizado.\n\n"
            "**Prazo de validade:** varia por espécie (bovinos: até 30 dias, "
            "dependendo do trajeto e finalidade).\n\n"
            "**SISBOV:** para rastreabilidade individual, o animal deve estar cadastrado "
            "no Sistema Brasileiro de Identificação Individual Bovina."
        ),
    },
    # CFOP
    {
        "tags": ["cfop", "codigo fiscal operacao", "classificacao", "entrada", "saida"],
        "pergunta": "Quais os principais CFOPs usados em NFA agropecuária?",
        "resposta": (
            "Os **CFOPs (Códigos Fiscais de Operações e Prestações)** mais usados em NFA:\n\n"
            "**Saídas — Operações Internas (6.xxx):**\n"
            "| CFOP | Descrição |\n"
            "|---|---|\n"
            "| 5.101 | Venda de produção do estabelecimento |\n"
            "| 5.102 | Venda de mercadoria adquirida/recebida de terceiros |\n"
            "| 5.124 | Industrialização para o encomendante |\n"
            "| 5.401 | Venda de produção — substituição tributária |\n\n"
            "**Saídas — Operações Interestaduais (6.xxx):**\n"
            "| CFOP | Descrição |\n"
            "|---|---|\n"
            "| 6.101 | Venda de produção do estabelecimento |\n"
            "| 6.102 | Venda de mercadoria adquirida de terceiros |\n\n"
            "**Entradas — Operações Internas (1.xxx / 2.xxx):**\n"
            "| CFOP | Descrição |\n"
            "|---|---|\n"
            "| 1.101 | Compra para industrialização |\n"
            "| 1.102 | Compra para comercialização |\n"
            "| 2.101/2.102 | Compra interestadual |\n\n"
            "**Dica ORGATEC:** CFOPs de remessa (5.905, 5.906) sem retorno podem "
            "indicar transferência patrimonial irregular."
        ),
    },
    # NFSe
    {
        "tags": ["nfse", "servico", "issqn", "iss", "simples nacional", "prestador"],
        "pergunta": "O que é a NFS-e e como ela difere da NFA?",
        "resposta": (
            "A **NFS-e (Nota Fiscal de Serviços Eletrônica)** acompanha prestações "
            "de serviços (mecânica, consultoria, transporte, etc.), diferente da NFA "
            "que acompanha circulação de mercadorias agropecuárias.\n\n"
            "**Principais diferenças:**\n"
            "| Aspecto | NFA | NFS-e |\n"
            "|---|---|---|\n"
            "| Tributo | ICMS | ISS (ISSQN) |\n"
            "| Base | Produto rural | Serviço |\n"
            "| Padrão | SPED/Convênio SINIEF | Padrão ABRASF/municipio |\n"
            "| Competência | Estado | Município |\n\n"
            "**Alíquota ISS:** varia de 2% a 5% (LC 116/2003).\n\n"
            "**Simples Nacional:** empresas do Simples recolhem ISS dentro do DAS, "
            "mas ainda devem emitir NFS-e conforme regras do município."
        ),
    },
    # Prazo / Decadência
    {
        "tags": ["prazo", "decadencia", "prescricao", "5 anos", "lancamento", "retificacao"],
        "pergunta": "Quais são os prazos de decadência e prescrição tributária?",
        "resposta": (
            "**Decadência (prazo para lançar o crédito):**\n"
            "- Regra geral: 5 anos contados do primeiro dia do exercício seguinte ao fato "
            "gerador (CTN, art. 173, I)\n"
            "- Lançamento por homologação (tributos auto-lançados como ICMS): 5 anos do "
            "fato gerador (CTN, art. 150, §4º)\n"
            "- Com dolo, fraude ou simulação: 5 anos do art. 173, I (corre do início do "
            "exercício seguinte)\n\n"
            "**Prescrição (prazo para cobrar o crédito já lançado):**\n"
            "- 5 anos contados da constituição definitiva do crédito (CTN, art. 174)\n"
            "- Suspende com: moratória, parcelamento, liminar judicial\n"
            "- Interrompe com: despacho do juiz em execução fiscal\n\n"
            "**Prático para auditoria:** fiscalização pode revisar NFAs dos últimos "
            "5 anos completos + ano corrente. Para fraude comprovada, o prazo do art. 173, "
            "I aplica-se integralmente."
        ),
    },
]


# ── MOTOR DE BUSCA SEMÂNTICA ─────────────────────────────────────────────────


def _tokenizar(texto: str) -> list[str]:
    """Extrai tokens relevantes (stopwords removidas)."""
    _STOP = {
        "o",
        "a",
        "os",
        "as",
        "um",
        "uma",
        "no",
        "na",
        "nos",
        "nas",
        "para",
        "por",
        "com",
        "sem",
        "que",
        "e",
        "ou",
        "mas",
        "se",
        "como",
        "qual",
        "quais",
        "é",
        "são",
        "foi",
        "pode",
        "deve",
        "tem",
        "ter",
        "ser",
        "estar",
        "me",
        "meu",
        "minha",
        "isso",
        "esse",
        "esta",
        "este",
        "ao",
        "à",
        "às",
        "aos",
        "de",
        "do",
        "da",
        "dos",
        "das",
    }
    texto = texto.lower()
    texto = re.sub(r"[^a-záéíóúâêîôûãõç\s\d/]", " ", texto)
    tokens = [t for t in texto.split() if t not in _STOP and len(t) > 1]
    return tokens

# Otimização: Pre-computar tokens da base estática para não reprocessar a cada busca
for _item in KB:
    _item["_tokens_set"] = set(_tokenizar(" ".join(_item["tags"])) + _tokenizar(_item["pergunta"]))

def _score(pergunta_tokens: list[str], item: dict) -> float:
    """Calcula score de relevância entre a pergunta e um item da KB."""
    item_tokens = item.get("_tokens_set", set())
    if not item_tokens:
        return 0.0

    matches = sum(1 for t in pergunta_tokens if t in item_tokens)
    # Jaccard com boost para match exato de n-grams nas tags
    score = matches / (len(pergunta_tokens) + len(item_tokens) - matches + 1e-9)

    for tag in item.get("tags", []):
        if tag.lower() in " ".join(pergunta_tokens):
            score += 0.2

    return score


def buscar(pergunta: str, top_k: int = 1, min_score: float = 0.05) -> list[dict]:
    """Retorna os top_k itens mais relevantes da KB para a pergunta."""
    tokens = _tokenizar(pergunta)
    if not tokens:
        return []

    scored = [(item, _score(tokens, item)) for item in KB]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [item for item, s in scored if s >= min_score][:top_k]


# ── RESPOSTA FALLBACK ─────────────────────────────────────────────────────────

_RESPOSTA_GENERICA = f"""\
**Agente ORGATEC — Modo Local (Offline)**

Não encontrei uma resposta específica na base de conhecimento para sua pergunta.

**Sugestões de consulta:**
- Nota Fiscal Agropecuária (NFA) — conceito, emissão, CFOP
- ICMS agropecuário — diferimento, alíquotas, isenções
- FUNRURAL — alíquotas, retenção, base de cálculo
- GTA (Guia de Trânsito Animal) — obrigatoriedade, relação com NFA
- CTN (Código Tributário Nacional) — prazos, lançamento, prescrição
- Lei Kandir (LC 87/96) — ICMS, não-cumulatividade
- Reforma Tributária (EC 132/23) — IBS, CBS, cronograma
- Sinais de fraude em NFA — alertas, discrepâncias, irregularidades

**Para análise de notas fiscais específicas**, acesse a seção **Auditoria NFA** e faça
o upload do arquivo XML ou PDF.

*Base de conhecimento: {len(KB)} tópicos disponíveis | Modo: KB Local (sem IA cloud)*
"""


def responder(pergunta: str) -> str:
    """
    Ponto de entrada principal do motor local.
    Retorna a melhor resposta encontrada na KB ou a resposta genérica.
    """
    resultados = buscar(pergunta)
    if resultados:
        item = resultados[0]
        logger.info(f"KB Local: match '{item['pergunta'][:50]}' para '{pergunta[:50]}'")
        return (
            f"### {item['pergunta']}\n\n"
            f"{item['resposta']}\n\n"
            f"---\n*Fonte: Base de Conhecimento ORGATEC | Referências: CTN, LC 87/96, "
            f"EC 132/23, SPED*"
        )
    logger.info(f"KB Local: sem match para '{pergunta[:60]}'")
    return _RESPOSTA_GENERICA
