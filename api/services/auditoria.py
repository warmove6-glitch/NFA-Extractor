import os
import tempfile
import logging
import threading
import time
from typing import Any, List
from fastapi import UploadFile  # noqa: F401 (mantido para compatibilidade de imports externos)
from src.domain.extractor import extrair_notas, NFA, Parte, resumo_geral
from src.domain.xml_parser import parse_xml, NotaFiscalXML
from src.infrastructure.ai_client import analisar_producao
from src.application.reports.pdf_report import gerar_pdf
from src.infrastructure.database_v2 import SessionLocal, Laudo

logger = logging.getLogger(__name__)
_timer_start = None

def _log_tempo(stage: str):
    """Log tempo decorrido desde o início."""
    global _timer_start
    if _timer_start is None:
        _timer_start = time.time()
    elapsed = time.time() - _timer_start
    logger.info(f"⏱️ [{stage}] {elapsed:.1f}s")


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
    modo_relatorio: str = 'simples',  # 'simples' ou 'detalhado'
    formato_relatorio: str = 'pdf',  # 'pdf' (ReportLab) ou 'html' (moderno)
):
    """
    Processo em background seguindo a diretriz AudiOrg de escalabilidade.

    Recebe os bytes já lidos pela rota para evitar problemas de lifecycle do UploadFile:
    UploadFile pode ser fechado pelo ASGI framework antes que a background task execute.
    """
    db = SessionLocal()
    global _timer_start
    _timer_start = time.time()
    try:
        _log_tempo("INÍCIO")
        tasks_status[task_id] = {"status": "extraindo", "progress": 10}

        all_notas = []   # NFA (motor matemático)
        notas_xml = []   # NotaFiscalXML (agentes IA via resumo)
        temp_dir  = tempfile.gettempdir()

        # Processar apenas primeiro arquivo
        if files:
            filename, content = files[0]
            ext = os.path.splitext(filename)[1].lower()

            try:
                t_parse_start = time.time()
                if ext == ".xml":
                    nota_xml = parse_xml(content, modo_resumo="resumido")
                    all_notas.append(_xml_para_nfa(nota_xml))
                    t_parse = time.time() - t_parse_start
                    logger.info(f"⏱️  [XML PARSE] {t_parse:.1f}s — {filename}")
                else:
                    file_path = os.path.join(temp_dir, filename)
                    with open(file_path, "wb") as buf:
                        buf.write(content)
                    t_extract_start = time.time()
                    notas_pdf, _, _ = extrair_notas(file_path)
                    t_extract = time.time() - t_extract_start
                    all_notas.extend(notas_pdf)
                    logger.info(f"⏱️  [PDF EXTRACT] {t_extract:.1f}s — {filename} → {len(notas_pdf)} notas")
            except Exception as exc:
                logger.error(f"Falha ao processar {filename}: {exc}")

        _log_tempo("EXTRAÇÃO COMPLETA")

        tasks_status[task_id] = {"status": "processamento_quantitativo", "progress": 30}

        valor_total_lote = sum(n.valor_total for n in all_notas) if all_notas else 0
        score_risco = 0.5
        nivel_risco = "MÉDIO"

        logger.info(f"Lote: {len(all_notas)} notas, R$ {valor_total_lote:,.2f}")
        
        tasks_status[task_id] = {"status": "analisando_ia", "progress": 50}

        def callback_progresso(texto):
            """Atualizar progresso em tempo real durante análise."""
            logger.info(f"[IA] {texto}")

        logger.info(f"[PRODUCAO] Iniciando análise para {client_name}")
        t_claude_start = time.time()

        # Timeout adaptativo: máximo 8 segundos para análise
        # Se passar disso, usa modo rápido sem IA
        import threading
        resultado_ia = {'veredito': None, 'concluido': False}

        def executar_analise():
            try:
                resultado_ia['veredito'] = analisar_producao(
                    all_notas,
                    callback=callback_progresso,
                    nome_produtor=client_name
                )
            except Exception as e:
                logger.warning(f"Análise IA falhou: {e}")
                resultado_ia['veredito'] = None
            finally:
                resultado_ia['concluido'] = True

        thread_ia = threading.Thread(target=executar_analise, daemon=True)
        thread_ia.start()
        thread_ia.join(timeout=8)  # Espera máximo 8s

        t_claude = time.time() - t_claude_start

        if resultado_ia['veredito']:
            veredito = resultado_ia['veredito']
            logger.info(f"⏱️  [IA COMPLETA] {t_claude:.1f}s")
        else:
            # Modo fallback: análise rápida baseada em KPIs
            # Extrai período das notas
            periodo_str = "N/D"
            if all_notas:
                datas = [n.emissao for n in all_notas if n.emissao]
                if datas:
                    datas_sorted = sorted(datas)
                    periodo_str = f"{datas_sorted[0]} a {datas_sorted[-1]}"

            veredito = f"""[VEREDITO RÁPIDO - Modo Otimizado]

Contribuinte: {client_name}
Período: {periodo_str}
Notas: {len(all_notas)}
Valor Total: R$ {valor_total_lote:,.2f}

ANÁLISE AUTOMÁTICA (SEM IA):
- {len(all_notas)} documentos processados
- Valor agregado: R$ {valor_total_lote:,.2f}
- Status: Processamento concluído em modo rápido

Nota: Análise detalhada indisponível (timeout). Recomenda-se reprocessamento para análise completa.
"""
            logger.info(f"⏱️  [FALLBACK RÁPIDO] {t_claude:.1f}s (sem IA)")

        _log_tempo("ANÁLISE CONCLUÍDA")

        # Geracao de Relatorio PDF (AudiOrg Sovereign)
        tasks_status[task_id] = {"status": "gerando_pdf", "progress": 80}
        pdf_filename = f"Laudo_{task_id[:8]}.pdf"
        pdf_path = os.path.join("data", "laudos", pdf_filename)
        os.makedirs(os.path.join("data", "laudos"), exist_ok=True)

        try:
            t_pdf_start = time.time()
            gerar_pdf(
                notas=all_notas,
                saida=pdf_path,
                analise_ia=veredito,
                nome_contribuinte=client_name,
                cpf_contribuinte=client_cpf,
                risco_nivel=nivel_risco,
                score_risco=score_risco,
                modo_relatorio=modo_relatorio,
                formato=formato_relatorio,
            )
            t_pdf = time.time() - t_pdf_start
            logger.info(f"⏱️  [{formato_relatorio.upper()} TOTAL] {t_pdf:.1f}s — {modo_relatorio}")
            _log_tempo(f"{formato_relatorio.upper()} GERADO")
            logger.info(f"Relatorio {formato_relatorio} gerado: {pdf_path}")
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

        _log_tempo("PERSISTÊNCIA BD")
        logger.info(f"[SUCESSO] Auditoria {task_id} concluída com IA: {ia_utilizada}")

        tasks_status[task_id] = {
            "status": "concluido",
            "progress": 100,
            "resultado": veredito,
            "total_notas": len(all_notas)
        }
        _log_tempo("FIM")

    except Exception as e:
        logger.error(f"Erro no processamento da auditoria {task_id}: {e}")
        tasks_status[task_id] = {"status": "erro", "erro": str(e)}
    finally:
        db.close()
