from typing import TypedDict, List, Annotated
import operator
from langgraph.graph import StateGraph, END
from ai_client import analisar, SYSTEM_SIGMA, SYSTEM_GAMA, SYSTEM_AUDITOR
from extractor import NFA

class AgentState(TypedDict):
    notas: List[NFA]
    nome_contribuinte: str
    analise_sigma: str
    analise_gama: str
    veredito_final: str
    historico: Annotated[List[str], operator.add]

def node_sigma(state: AgentState):
    """Agente de Dados e Quantitativo."""
    print("[AGENT] Sigma analisando volumes e impostos...")
    res = analisar(state['notas'], system_override=SYSTEM_SIGMA, nome_produtor=state['nome_contribuinte'])
    return {"analise_sigma": res, "historico": ["Sigma concluiu analise quantitativa."]}

def node_gama(state: AgentState):
    """Agente Juridico e Compliance."""
    print("[AGENT] Gama avaliando riscos juridicos...")
    # Gama recebe a analise de Sigma para contexto extra
    contexto = f"CONTEXTO QUANTITATIVO (SIGMA):\n{state['analise_sigma']}"
    res = analisar(state['notas'], system_override=SYSTEM_GAMA + "\n" + contexto, nome_produtor=state['nome_contribuinte'])
    return {"analise_gama": res, "historico": ["Gama concluiu parecer juridico."]}

def node_auditor(state: AgentState):
    """Auditor-Chefe Consolidando tudo."""
    print("[AGENT] Auditor-Chefe gerando veredito final...")
    contexto = f"SIGMA (DADOS):\n{state['analise_sigma']}\n\nGAMA (LEGAL):\n{state['analise_gama']}"
    res = analisar(state['notas'], system_override=SYSTEM_AUDITOR + "\n" + contexto, nome_produtor=state['nome_contribuinte'])
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

def rodar_auditoria_completa(notas: List[NFA], nome_contribuinte: str):
    app = build_graph()
    inputs = {
        "notas": notas,
        "nome_contribuinte": nome_contribuinte,
        "analise_sigma": "",
        "analise_gama": "",
        "veredito_final": "",
        "historico": []
    }
    return app.invoke(inputs)
