from typing import TypedDict, List, Annotated
import operator
import json
from langgraph.graph import StateGraph, END
from src.infrastructure.ai_client import analisar, SYSTEM_SIGMA, SYSTEM_GAMA, SYSTEM_AUDITOR
from src.domain.extractor import NFA

class AgentState(TypedDict):
    notas: List[NFA]
    nome_contribuinte: str
    contexto_quant: dict
    contexto_xml: str          # resumo estruturado das notas XML (vazio se só PDFs)
    analise_sigma: str
    analise_gama: str
    veredito_final: str
    historico: Annotated[List[str], operator.add]

def node_sigma(state: AgentState):
    """Agente de Dados e Quantitativo."""
    print("[AGENT] Sigma analisando volumes e impostos...")
    cq = state['contexto_quant']
    prompt_contexto = f"""
GROUND TRUTH MATEMÁTICO (ANTIGRAVITY ENGINE):
- Score de Risco (Bayesiano): {cq.get('risk_score', 'N/A')}
- Nível de Fraude: {cq.get('fraud_level', 'N/A')}
- Resumo do Lote: {json.dumps(cq.get('resumo_estatistico', {}), indent=2, ensure_ascii=False)}
"""
    # Enriquece com dados XML estruturados, se disponíveis
    xml_ctx = state.get('contexto_xml', '')
    if xml_ctx:
        prompt_contexto += f"\n{xml_ctx}"

    res = analisar([], system_override=SYSTEM_SIGMA + "\n" + prompt_contexto, nome_produtor=state['nome_contribuinte'])
    return {"analise_sigma": res, "historico": ["Sigma concluiu analise quantitativa."]}

def node_gama(state: AgentState):
    """Agente Juridico e Compliance."""
    print("[AGENT] Gama avaliando riscos juridicos...")
    cq = state['contexto_quant']
    contexto = f"CONTEXTO QUANTITATIVO (SIGMA):\n{state['analise_sigma']}\n\nRISCO DETECTADO PELA ENGINE: {cq['fraud_level']} (Score: {cq['risk_score']})"
    
    res = analisar([], system_override=SYSTEM_GAMA + "\n" + contexto, nome_produtor=state['nome_contribuinte'])
    return {"analise_gama": res, "historico": ["Gama concluiu parecer juridico."]}

def node_auditor(state: AgentState):
    """Auditor-Chefe Consolidando tudo."""
    print("[AGENT] Auditor-Chefe gerando veredito final...")
    cq = state['contexto_quant']
    contexto = f"SIGMA (DADOS):\n{state['analise_sigma']}\n\nGAMA (LEGAL):\n{state['analise_gama']}"
    from src.domain.extractor import resumo_geral
    resumo = resumo_geral(state['notas'])
    prompt_auditor = f"RESUMO DO LOTE:\n{json.dumps(resumo, indent=2)}\n\n{contexto}"
    
    res = analisar(state['notas'][:10], system_override=SYSTEM_AUDITOR + "\n" + prompt_auditor, nome_produtor=state['nome_contribuinte'])
    return {"veredito_final": res, "historico": ["Veredito soberano emitido."]}


def build_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("sigma", node_sigma)
    workflow.add_node("gama", node_gama)
    workflow.add_node("auditor", node_auditor)
    
    workflow.set_entry_point("sigma")
    workflow.add_edge("sigma", "gama")
    workflow.add_edge("gama", "auditor")
    workflow.add_edge("auditor", END)
    
    return workflow.compile()

def rodar_auditoria_completa(
    notas: List[NFA],
    nome_contribuinte: str,
    contexto_quant: dict = None,
    contexto_xml: str = "",
) -> dict:
    """
    Executa o workflow de auditoria multiagente.

    Args:
        notas:            lista de NFA (PDFs + XMLs convertidos)
        nome_contribuinte: nome do cliente
        contexto_quant:   saída da AntiGravityQuantEngine (scores, flags)
        contexto_xml:     resumo textual das notas XML para enriquecer Sigma
    """
    app = build_graph()
    initial_state = {
        "notas": notas,
        "nome_contribuinte": nome_contribuinte,
        "contexto_quant": contexto_quant or {},
        "contexto_xml": contexto_xml,
        "analise_sigma": "",
        "analise_gama": "",
        "veredito_final": "",
        "historico": [],
    }
    return app.invoke(initial_state)

