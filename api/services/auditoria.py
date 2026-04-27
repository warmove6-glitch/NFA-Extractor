import os
import tempfile
import logging
import threading
from typing import Any, List
from fastapi import UploadFile  # noqa: F401 (mantido para compatibilidade de imports externos)
from src.domain.extractor import extrair_notas, NFA, Parte
from src.domain.xml_parser import parse_xml, resumo_lote_para_agentes, NotaFiscalXML
from src.application.analytics_engine import processar_para_dataframe
from src.domain.agents_engine import rodar_auditoria_completa
from src.application.reports.pdf_report import gerar_pdf
from src.infrastructure.database_v2 import SessionLocal, Laudo

logger = logging.getLogger(__name__)


def _xml_para_nfa(nota: NotaFiscalXML) -> NFA:
    """Converte NotaFiscalXML → NFA (compatível com o motor matemático existente)."""
    return NFA(
        numero        = nota.numero,
        natureza      = nota.natureza or nota.tipo,
        emissao       = nota.data_emissao,
        valor_total   = nota.valor_total,
        valor_icms    = nota.valor_imposto,
        quantidade_total = sum(i.quantidade for i in nota.itens) if nota.itens else 0.0,
        chave_acesso  = None,
        local_emissao = f"{nota.municipio}/{nota.uf}",
        remetente     = Parte(nome=nota.emitente_nome, cpf_cnpj=nota.emitente_doc,
                              ie=nota.emitente_ie, municipio=nota.municipio),
        destinatario  = Parte(nome=nota.tomador_nome, cpf_cnpj=nota.tomador_doc),
    )


def _formatar_documento(doc: str) -> str:
    """Formata CPF/CNPJ puro (somente digitos) para o padrao com pontuacao.
    Se ja estiver formatado, retorna sem alteracao.
    CPF  -> XXX.XXX.XXX-XX   (11 digitos)
    CNPJ -> XX.XXX.XXX/XXXX-XX (14 digitos)
    """
    digits = "".join(c for c in doc if c.isdigit())
    if len(digits) == 11:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
    if len(digits) == 14:
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"
    # Ja formatado ou formato desconhecido - devolve como esta
    return doc


# Armazenamento em memoria das tasks ativas.
# TODO (producao): substituir por Redis ou tabela de tasks no PostgreSQL
#   para sobreviver a reinicializacoes e suportar multiplos workers.
_tasks_lock: threading.Lock   = threading.Lock()
_tasks_store: dict[str, Any]  = {}


class _ThreadSafeTasksProxy:
    """Proxy com leitura/escrita atomica sobre o dict de tasks."""

    def __setitem__(self, key: str, value: Any) -> None:
        with _tasks_lock:
            _tasks_store[key] = value

    def __getitem__(self, key: str) -> Any:
        with _tasks_lock:
            return _tasks_store[key]

    def __contains__(self, key: str) -> bool:
        with _tasks_lock:
            return key in _tasks_store

    def get(self, key: str, default: Any = None) -> Any:
        with _tasks_lock:
            return _tasks_store.get(key, default)


tasks_status: _ThreadSafeTasksProxy = _ThreadSafeTasksProxy()

async def processar_lote_auditoria(
    task_id: str,
    files: List[tuple],   # lista de (filename: str, content: bytes) — lidos na rota
    client_name: str,
    client_cpf: str,
):
    """
    Processo em background seguindo a diretriz AudiOrg de escalabilidade.

    Recebe os bytes já lidos pela rota para evitar problemas de lifecycle do UploadFile:
    UploadFile pode ser fechado pelo ASGI framework antes que a background task execute.
    """
    db = SessionLocal()
    try:
        tasks_status[task_id] = {"status": "extraindo", "progress": 10}

        all_notas = []   # NFA (motor matemático)
        notas_xml = []   # NotaFiscalXML (agentes IA via resumo)
        temp_dir  = tempfile.gettempdir()

        for filename, content in files:
            ext = os.path.splitext(filename)[1].lower()

            if ext == ".xml":
                # ── Caminho XML ──────────────────────────────────────────
                try:
                    nota_xml = parse_xml(content, modo_resumo="resumido")
                    notas_xml.append(nota_xml)
                    all_notas.append(_xml_para_nfa(nota_xml))
                    logger.info(f"XML processado: {filename} → {nota_xml.tipo} #{nota_xml.numero}")
                except Exception as exc:
                    logger.error(f"Falha ao parsear XML {filename}: {exc}")

            else:
                # ── Caminho PDF (legado) ─────────────────────────────────
                file_path = os.path.join(temp_dir, filename)
                with open(file_path, "wb") as buf:
                    buf.write(content)
                try:
                    notas_pdf, _, _ = extrair_notas(file_path)
                    all_notas.extend(notas_pdf)
                except Exception as exc:
                    logger.error(f"Falha ao extrair PDF {filename}: {exc}")

        valor_total_lote = sum(n.valor_total for n in all_notas)

        # Bloco de contexto XML para os agentes (adicional ao resumo do PDF)
        contexto_xml = ""
        if notas_xml:
            contexto_xml = "\n\n=== DADOS XML (parsados diretamente) ===\n"
            contexto_xml += resumo_lote_para_agentes(notas_xml, modo="resumido")
        
        tasks_status[task_id] = {"status": "processamento_quantitativo", "progress": 30}
        
        # Motor Matematico (Ground Truth)
        from src.domain.extractor import resumo_geral
        from src.domain.schemas import AuditoriaMacroSchema
        from src.application.sovereign_engine import AntiGravityQuantEngine
        
        resumo = resumo_geral(all_notas, nome_contribuinte=client_name)
        dto = AuditoriaMacroSchema(
            contribuinte_id=_formatar_documento(client_cpf),
            total_cabecas_compradas=int(resumo.get('total_cabecas', 0)) if "REM" not in str(resumo) else 0,
            total_cabecas_vendidas=int(resumo.get('total_cabecas', 0)),
            total_receita_bruta=resumo.get('total_valor', 0.0),
            avg_preco_venda=resumo.get('ticket_medio', 0.0)
        )
        
        # Rodar Engine Quantitativa
        engine = AntiGravityQuantEngine()
        dto_final = engine.execute_xgboost_bayesian_proxy(dto)
        logger.info(f"GROUND TRUTH: Score {dto_final.score_xgboost_final}, Flag {dto_final.fraud_flag_level}")
        
        tasks_status[task_id] = {"status": "analisando_ia", "progress": 50}

        
        # Orquestracao Squad (IA) enriquecida com Ground Truth
        contexto_quant = {
            "risk_score": dto_final.score_xgboost_final,
            "fraud_level": dto_final.fraud_flag_level,
            "resumo_estatistico": resumo
        }
        
        analise_state = rodar_auditoria_completa(
            all_notas,
            client_name,
            contexto_quant=contexto_quant,
            contexto_xml=contexto_xml,
        )
        veredito = analise_state.get('veredito_final', 'Veredito nao gerado.')
        
        # Fallback de Veredito (Resiliencia Squad Delta)
        if "[Gemini Falhou" in veredito or "nao gerado" in veredito.lower():
            logger.warning("Falha Critica na IA. Ativando Parecer de Contingencia Quantitativa.")
            veredito = f"""
### PARECER TECNICO DE CONTINGENCIA (SQUAD ANTIGRAVITY)
**PROTOCOLO:** SOBERANO - MODO OFF-GRID
**STATUS:** IA CLOUD INDISPONIVEL (QUOTA EXCEDIDA)

**ANALISE QUANTITATIVA (GROUND TRUTH):**
- **Score de Risco Matematico:** {dto_final.score_xgboost_final}
- **Nivel de Fraude Detectado:** {dto_final.fraud_flag_level}
- **Veredito do Motor:** O sistema identificou inconsistencias que resultaram em um score de risco. 
A analise qualitativa da Squad foi omitida para garantir a entrega imediata dos dados numericos.

**DADOS DO LOTE AUDITADO:**
- Volume de Notas: {len(all_notas)}
- Montante Total: R$ {valor_total_lote:,.2f}
"""


        
        # Geracao de Relatorio PDF (AudiOrg Sovereign)
        tasks_status[task_id] = {"status": "gerando_pdf", "progress": 80}
        pdf_filename = f"Laudo_{task_id[:8]}.pdf"
        pdf_path = os.path.join("data", "laudos", pdf_filename)
        os.makedirs(os.path.join("data", "laudos"), exist_ok=True)
        
        try:
            from src.application.reports.pdf_report import gerar_pdf
            gerar_pdf(
                notas=all_notas,
                saida=pdf_path,
                analise_ia=veredito,
                nome_contribuinte=client_name,
                cpf_contribuinte=client_cpf,
                risco_nivel=dto_final.fraud_flag_level,
                score_risco=float(dto_final.score_xgboost_final or 0),
            )
            logger.info(f"Relatorio PDF gerado: {pdf_path}")
        except Exception as e_pdf:
            logger.error(f"Erro critico ao gerar PDF: {e_pdf}")
            tasks_status[task_id] = {
                "status": "erro",
                "erro": f"Falha na geracao do relatorio PDF: {e_pdf}",
                "progress": 80,
            }
            return  # Interrompe - nao persistir laudo sem relatorio

        # Persistencia Soberana (SQUAD ALFA)
        novo_laudo = Laudo(
            cliente_id=1,  # Mock para o cliente de teste
            veredito_ia=veredito,
            qtd_notas=len(all_notas),
            valor_total=valor_total_lote,
            qtd_anomalias=veredito.count("ANOMALIA") if "ANOMALIA" in veredito else 0,
            pdf_path=pdf_path
        )
        db.add(novo_laudo)
        db.commit()

        tasks_status[task_id] = {
            "status": "concluido",
            "progress": 100,
            "resultado": veredito,
            "total_notas": len(all_notas)
        }

    except Exception as e:
        logger.error(f"Erro no processamento da auditoria {task_id}: {e}")
        tasks_status[task_id] = {"status": "erro", "erro": str(e)}
    finally:
        db.close()
