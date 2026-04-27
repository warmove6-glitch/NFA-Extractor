import os
import tempfile
import logging
import threading
from typing import Any, List
from fastapi import UploadFile  # noqa: F401 (mantido para compatibilidade de imports externos)
from src.domain.extractor import extrair_notas, NFA, Parte, resumo_geral
from src.domain.xml_parser import parse_xml, NotaFiscalXML
from src.infrastructure.ai_client import analisar_producao
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

        tasks_status[task_id] = {"status": "processamento_quantitativo", "progress": 30}

        resumo = resumo_geral(all_notas, nome_contribuinte=client_name)

        # Score simplificado: baseado apenas em análise de risco qualitativa
        score_risco = 0.5  # Neutral (será refinado pela IA)
        nivel_risco = "MÉDIO"  # Will be overridden by IA veredito

        logger.info(f"GROUND TRUTH SIMPLIFICADO: Valor Total {valor_total_lote}, {len(all_notas)} notas")
        
        tasks_status[task_id] = {"status": "analisando_ia", "progress": 50}

        def callback_progresso(texto):
            """Atualizar progresso em tempo real durante análise."""
            logger.info(f"[IA] {texto}")

        logger.info(f"[PRODUÇÃO] Iniciando análise com Claude Vision para {client_name}")
        veredito = analisar_producao(
            all_notas,
            callback=callback_progresso,
            nome_produtor=client_name
        )


        
        # Geracao de Relatorio PDF (AudiOrg Sovereign)
        tasks_status[task_id] = {"status": "gerando_pdf", "progress": 80}
        pdf_filename = f"Laudo_{task_id[:8]}.pdf"
        pdf_path = os.path.join("data", "laudos", pdf_filename)
        os.makedirs(os.path.join("data", "laudos"), exist_ok=True)
        
        try:
            gerar_pdf(
                notas=all_notas,
                saida=pdf_path,
                analise_ia=veredito,
                nome_contribuinte=client_name,
                cpf_contribuinte=client_cpf,
                risco_nivel=nivel_risco,
                score_risco=score_risco,
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

        # Detectar qual IA foi usada e refinar score de risco
        ia_utilizada = "Claude"
        if "[Swift" in veredito:
            ia_utilizada = "Swift (Fallback Local)"
        elif "[KB Local" in veredito:
            ia_utilizada = "KB Local (Contingência)"

        # Score refinado baseado no veredito da IA
        if "ANOMALIA" in veredito or "fraude" in veredito.lower() or "risco alto" in veredito.lower():
            score_risco = 0.8
            nivel_risco = "ALTO"
        elif "consistência" in veredito.lower() or "cuidado" in veredito.lower():
            score_risco = 0.6
            nivel_risco = "MÉDIO"
        else:
            score_risco = 0.3
            nivel_risco = "BAIXO"

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

        logger.info(f"[SUCESSO] Auditoria {task_id} concluída com IA: {ia_utilizada}")

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
