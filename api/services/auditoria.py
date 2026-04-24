import os
import tempfile
import logging
import threading
from typing import Any
from fastapi import UploadFile
from src.domain.extractor import extrair_notas
from src.application.analytics_engine import processar_para_dataframe
from src.domain.agents_engine import rodar_auditoria_completa
from src.application.reports.pdf_report import gerar_pdf
from src.infrastructure.database_v2 import SessionLocal, Laudo

logger = logging.getLogger(__name__)

# Armazenamento em memória das tasks ativas.
# TODO (produção): substituir por Redis ou tabela de tasks no PostgreSQL
#   para sobreviver a reinicializações e suportar múltiplos workers.
_tasks_lock: threading.Lock   = threading.Lock()
_tasks_store: dict[str, Any]  = {}


class _ThreadSafeTasksProxy:
    """Proxy com leitura/escrita atômica sobre o dict de tasks."""

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

async def processar_lote_auditoria(task_id: str, files: List[UploadFile], client_name: str, client_cpf: str):
    """
    Processo em background seguindo a diretriz AudiOrg de escalabilidade.
    """
    db = SessionLocal()
    try:
        tasks_status[task_id] = {"status": "extraindo", "progress": 10}
        
        all_notas = []
        temp_dir = tempfile.gettempdir()
        
        valor_total_lote = 0
        for file in files:
            file_path = os.path.join(temp_dir, file.filename)
            with open(file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
            
            # Extração
            notas, _, _ = extrair_notas(file_path)
            all_notas.extend(notas)
            valor_total_lote += sum(n.valor_total for n in notas)
        
        tasks_status[task_id] = {"status": "processamento_quantitativo", "progress": 30}
        
        # Motor Matemático (Ground Truth)
        from src.domain.extractor import resumo_geral
        from src.domain.schemas import AuditoriaMacroSchema
        from src.application.sovereign_engine import AntiGravityQuantEngine
        
        resumo = resumo_geral(all_notas, nome_contribuinte=client_name)
        dto = AuditoriaMacroSchema(
            contribuinte_id=client_cpf,
            total_cabecas_compradas=int(resumo.get('total_cabecas', 0)) if "REM" not in str(resumo) else 0, # Lógica simplificada
            total_cabecas_vendidas=int(resumo.get('total_cabecas', 0)),
            total_receita_bruta=resumo.get('total_valor', 0.0),
            avg_preco_venda=resumo.get('ticket_medio', 0.0)
        )
        
        # Rodar Engine Quantitativa
        engine = AntiGravityQuantEngine()
        dto_final = engine.execute_xgboost_bayesian_proxy(dto)
        logger.info(f"GROUND TRUTH: Score {dto_final.score_xgboost_final}, Flag {dto_final.fraud_flag_level}")
        
        tasks_status[task_id] = {"status": "analisando_ia", "progress": 50}

        
        # Orquestração Squad (IA) enriquecida com Ground Truth
        contexto_quant = {
            "risk_score": dto_final.score_xgboost_final,
            "fraud_level": dto_final.fraud_flag_level,
            "resumo_estatistico": resumo
        }
        
        analise_state = rodar_auditoria_completa(all_notas, client_name, contexto_quant=contexto_quant)
        veredito = analise_state.get('veredito_final', 'Veredito não gerado.')
        
        # Fallback de Veredito (Resiliência Squad Delta)
        if "[Gemini Falhou" in veredito or "não gerado" in veredito.lower():
            logger.warning("Falha Crítica na IA. Ativando Parecer de Contingência Quantitativa.")
            veredito = f"""
### PARECER TÉCNICO DE CONTINGÊNCIA (SQUAD ANTIGRAVITY)
**PROTOCOLO:** SOBERANO - MODO OFF-GRID
**STATUS:** IA CLOUD INDISPONÍVEL (QUOTA EXCEDIDA)

**ANÁLISE QUANTITATIVA (GROUND TRUTH):**
- **Score de Risco Matemático:** {dto_final.score_xgboost_final}
- **Nível de Fraude Detectado:** {dto_final.fraud_flag_level}
- **Veredito do Motor:** O sistema identificou inconsistências que resultaram em um score de risco. 
A análise qualitativa da Squad foi omitida para garantir a entrega imediata dos dados numéricos.

**DADOS DO LOTE AUDITADO:**
- Volume de Notas: {len(all_notas)}
- Montante Total: R$ {valor_total_lote:,.2f}
"""


        
        # Geração de Relatório PDF (AudiOrg Sovereign)
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
            )
            logger.info(f"Relatório PDF gerado: {pdf_path}")
        except Exception as e_pdf:
            logger.error(f"Erro crítico ao gerar PDF: {e_pdf}")
            tasks_status[task_id] = {
                "status": "erro",
                "erro": f"Falha na geração do relatório PDF: {e_pdf}",
                "progress": 80,
            }
            return  # Interrompe — não persistir laudo sem relatório

        
        # Persistência Soberana (SQUAD ALFA)
        novo_laudo = Laudo(
            cliente_id=1, # Mock para o cliente de teste
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

