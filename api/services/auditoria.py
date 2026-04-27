import os
import tempfile
import logging
import threading
import time
from typing import Any, List
from fastapi import UploadFile  # noqa: F401 (mantido para compatibilidade de imports externos)
from src.domain.extractor import extrair_notas, NFA, Parte, resumo_geral
from src.domain.xml_parser import parse_xml, NotaFiscalXML
from src.domain.analise_local import calcular_metricas_risco, gerar_veredito_local
from src.domain.planilha_ir import gerar_dados_planilha, gerar_html_planilha
from src.domain.planilha_ir_premium import gerar_html_planilha_premium
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
    formato_relatorio: str = 'html',  # 'html' (moderno, padrão) ou 'pdf' (ReportLab)
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

        tasks_status[task_id] = {"status": "analisando", "progress": 50}

        valor_total_lote = sum(n.valor_total for n in all_notas) if all_notas else 0

        logger.info(f"Lote: {len(all_notas)} notas, R$ {valor_total_lote:,.2f}")

        # Análise local determinística (sem agentes IA)
        t_analise_start = time.time()
        analise = calcular_metricas_risco(all_notas)
        veredito = gerar_veredito_local(all_notas, client_name, analise)
        t_analise = time.time() - t_analise_start

        score_risco = analise['score_risco']
        nivel_risco = analise['nivel_risco']

        logger.info(f"⏱️  [ANÁLISE LOCAL] {t_analise:.2f}s — Score: {score_risco:.3f}, Nível: {nivel_risco}")
        _log_tempo("ANÁLISE CONCLUÍDA")

        # Geração da Planilha IRPF (premium design) — novo formato padrão
        tasks_status[task_id] = {"status": "gerando_planilha", "progress": 65}
        t_planilha_start = time.time()
        try:
            dados_planilha = gerar_dados_planilha(all_notas, client_name)
            html_planilha = gerar_html_planilha_premium(dados_planilha)
            t_planilha = time.time() - t_planilha_start
            logger.info(f"⏱️  [PLANILHA IRPF PREMIUM] {t_planilha:.3f}s")
            _log_tempo("PLANILHA PREMIUM GERADA")
        except Exception as e_planilha:
            logger.error(f"Erro ao gerar planilha premium: {e_planilha}")
            logger.info("Fallback para planilha simples")
            try:
                html_planilha = gerar_html_planilha(dados_planilha)
            except:
                html_planilha = "<p>Erro ao gerar planilha IRPF</p>"

        # Salvar relatório (HTML ou PDF conforme formato)
        tasks_status[task_id] = {"status": "gerando_relatorio", "progress": 80}
        os.makedirs(os.path.join("data", "laudos"), exist_ok=True)
        relatorio_path = None

        if formato_relatorio == 'html':
            # Usar planilha HTML como output principal (rápido, ~1ms)
            planilha_filename = f"Relatorio_IRPF_{task_id[:8]}.html"
            relatorio_path = os.path.join("data", "laudos", planilha_filename)
            try:
                t_html_start = time.time()
                with open(relatorio_path, "w", encoding="utf-8") as f:
                    f.write(html_planilha)
                t_html = time.time() - t_html_start
                logger.info(f"⏱️  [HTML TOTAL] {t_html:.3f}s — {modo_relatorio}")
                _log_tempo("HTML GERADO")
                logger.info(f"Relatorio HTML (planilha IRPF) gerado: {relatorio_path}")
            except Exception as e_html:
                logger.error(f"Erro ao salvar HTML: {e_html}")
                tasks_status[task_id] = {
                    "status": "erro",
                    "erro": f"Falha ao salvar relatório HTML: {e_html}",
                    "progress": 80,
                }
                return
        else:
            # Gerar PDF com ReportLab (compatibilidade)
            pdf_filename = f"Laudo_{task_id[:8]}.pdf"
            relatorio_path = os.path.join("data", "laudos", pdf_filename)

            try:
                t_pdf_start = time.time()
                gerar_pdf(
                    notas=all_notas,
                    saida=relatorio_path,
                    analise_ia=veredito,
                    nome_contribuinte=client_name,
                    cpf_contribuinte=client_cpf,
                    risco_nivel=nivel_risco,
                    score_risco=score_risco,
                    modo_relatorio=modo_relatorio,
                    formato=formato_relatorio,
                )
                t_pdf = time.time() - t_pdf_start
                logger.info(f"⏱️  [PDF TOTAL] {t_pdf:.1f}s — {modo_relatorio}")
                _log_tempo("PDF GERADO")
                logger.info(f"Relatorio PDF gerado: {relatorio_path}")
            except Exception as e_pdf:
                logger.error(f"Erro critico ao gerar PDF: {e_pdf}")
                tasks_status[task_id] = {
                    "status": "erro",
                    "erro": f"Falha na geracao do relatorio PDF: {e_pdf}",
                    "progress": 80,
                }
                return

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

        # Marcar como concluído IMEDIATAMENTE (não-bloqueante)
        tasks_status[task_id] = {
            "status": "concluido",
            "progress": 100,
            "resultado": veredito,
            "total_notas": len(all_notas)
        }

        # Salvar em banco em thread separada (não bloqueia resposta)
        def _salvar_laudo_async(laudo_data):
            try:
                db_async = SessionLocal()
                novo_laudo = Laudo(**laudo_data)
                db_async.add(novo_laudo)
                t_commit_start = time.time()
                db_async.commit()
                t_commit = time.time() - t_commit_start
                logger.info(f"⏱️  [DB COMMIT ASYNC] {t_commit:.2f}s")
                db_async.close()
            except Exception as e:
                logger.error(f"Erro no commit async: {e}")

        laudo_data = {
            'cliente_id': 1,
            'veredito_ia': veredito[:500],
            'qtd_notas': len(all_notas),
            'valor_total': valor_total_lote,
            'qtd_anomalias': veredito.count("ANOMALIA") if "ANOMALIA" in veredito else 0,
            'pdf_path': relatorio_path
        }

        db_thread = threading.Thread(target=_salvar_laudo_async, args=(laudo_data,), daemon=True)
        db_thread.start()

        _log_tempo("FIM")
        logger.info(f"[SUCESSO] Auditoria {task_id} concluída com IA: {ia_utilizada} (BD salvando em background)")

    except Exception as e:
        logger.error(f"Erro no processamento da auditoria {task_id}: {e}")
        tasks_status[task_id] = {"status": "erro", "erro": str(e)}
    finally:
        db.close()
