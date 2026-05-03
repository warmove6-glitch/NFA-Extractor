import logging
import os
import tempfile
import threading
import time
from typing import Any

from fastapi import UploadFile  # noqa: F401 (mantido para compatibilidade de imports externos)

from pdf_report_OTIMIZADO import gerar_pdf
from src.application.reports.orgaudi import gerar_laudo_orgaudi
from src.application.reports.relatorio_tecnico_orgatec import gerar_relatorio_tecnico_pdf
from src.domain.analise_local import calcular_metricas_risco, gerar_veredito_local
from src.domain.auditoria_forense import auditar_lote
from src.domain.extractor import NFA, Parte, extrair_notas
from src.domain.planilha_ir import gerar_dados_planilha, gerar_html_planilha
from src.domain.planilha_ir_premium import gerar_html_planilha_premium
from src.domain.xml_parser import NotaFiscalXML, parse_xml
from src.infrastructure.audit_task_repo import (
    cleanup_old_tasks,
    get_task,
    task_exists,
    upsert_task,
)
from src.infrastructure.database_v2 import (
    Laudo,
    SessionLocal,
    _get_or_create_cliente,
    salvar_notas_bd,
)
from src.integrations.horizon_squad import executar_squad_para_lote

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


# Persistência de status de tasks via PostgreSQL/SQLite (tabela `audit_tasks`).
# Substitui o antigo `_tasks_store` em memória — agora sobrevive a reinicialização
# e suporta `uvicorn --workers N` (cada worker enxerga o estado vigente).


class _DbTasksProxy:
    """Backend persistente para status de tasks (substitui `_ThreadSafeTasksProxy`).

    Mantém a mesma interface (`__setitem__`, `__getitem__`, `__contains__`, `get`)
    para zero impacto nos callers existentes em `processar_lote_auditoria`.

    Cleanup oportunístico: chamado no write, mas com throttle interno
    (no máximo 1 vez por minuto) para não martelar o DB a cada update.
    """

    def __init__(self, ttl_seconds: int = 3600, cleanup_interval: float = 60.0):
        self.ttl = ttl_seconds
        self._cleanup_interval = cleanup_interval
        self._last_cleanup = 0.0
        self._cleanup_lock = threading.Lock()

    def _maybe_cleanup(self) -> None:
        now = time.time()
        # leitura sem lock primeiro (rápida); só pega o lock se for hora de limpar
        if now - self._last_cleanup < self._cleanup_interval:
            return
        with self._cleanup_lock:
            # double-check sob lock (outro worker pode ter limpado entre a leitura e o lock)
            if time.time() - self._last_cleanup < self._cleanup_interval:
                return
            try:
                deletados = cleanup_old_tasks(self.ttl)
                if deletados:
                    logger.info(f"audit_tasks cleanup: {deletados} task(s) antigas removidas")
            except Exception as exc:
                logger.warning(f"cleanup audit_tasks falhou: {exc}")
            finally:
                self._last_cleanup = time.time()

    def __setitem__(self, key: str, value: Any) -> None:
        self._maybe_cleanup()
        upsert_task(key, value)

    def __getitem__(self, key: str) -> Any:
        data = get_task(key)
        if data is None:
            raise KeyError(key)
        return data

    def __contains__(self, key: str) -> bool:
        return task_exists(key)

    def get(self, key: str, default: Any = None) -> Any:
        data = get_task(key)
        return default if data is None else data


tasks_status: _DbTasksProxy = _DbTasksProxy()

def processar_lote_auditoria(
    task_id: str,
    files: list[tuple],   # lista de (filename: str, content: bytes) — lidos na rota
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

    t_req_start = time.time()
    def _log_tempo(stage: str):
        """Log tempo decorrido thread-safe para esta requisicao especifica."""
        elapsed = time.time() - t_req_start
        logger.info(f"⏱️ [{stage}] {elapsed:.1f}s")

    try:
        _log_tempo("INÍCIO")
        tasks_status[task_id] = {"status": "extraindo", "progress": 10}

        all_notas = []   # NFA (motor matemático)
        temp_dir  = tempfile.gettempdir()

        # Processar TODOS os arquivos enviados
        total_arquivos = len(files)
        for idx, (filename, content) in enumerate(files, start=1):
            ext = os.path.splitext(filename)[1].lower()
            # Atualiza progresso a cada arquivo (10% → 45% durante extração)
            pct = 10 + int(35 * idx / max(total_arquivos, 1))
            tasks_status[task_id] = {"status": "extraindo", "progress": pct}

            try:
                t_parse_start = time.time()
                if ext == ".xml":
                    nota_xml = parse_xml(content, modo_resumo="resumido")
                    all_notas.append(_xml_para_nfa(nota_xml))
                    t_parse = time.time() - t_parse_start
                    logger.info(f"⏱️  [XML PARSE {idx}/{total_arquivos}] {t_parse:.1f}s — {filename}")
                else:
                    file_path = os.path.join(temp_dir, filename)
                    with open(file_path, "wb") as buf:
                        buf.write(content)
                    t_extract_start = time.time()
                    notas_pdf, _, _ = extrair_notas(file_path)
                    t_extract = time.time() - t_extract_start
                    all_notas.extend(notas_pdf)
                    logger.info(f"⏱️  [PDF EXTRACT {idx}/{total_arquivos}] {t_extract:.1f}s — {filename} → {len(notas_pdf)} notas")
            except Exception as exc:
                logger.error(f"Falha ao processar {filename}: {exc}")

        logger.info(f"⏱️  [LOTE COMPLETO] {total_arquivos} arquivos → {len(all_notas)} notas")

        _log_tempo("EXTRAÇÃO COMPLETA")

        tasks_status[task_id] = {"status": "analisando", "progress": 50}

        valor_total_lote = sum(n.valor_total for n in all_notas) if all_notas else 0

        logger.info(f"Lote: {len(all_notas)} notas, R$ {valor_total_lote:,.2f}")

        # Métricas determinísticas (rápidas, ~1ms) — sempre rodam
        analise = calcular_metricas_risco(all_notas, client_cpf)
        score_risco = analise['score_risco']
        nivel_risco = analise['nivel_risco']

        # Tenta squad multiagente Horizon-Blue (Claude) primeiro;
        # cai para análise local determinística se squad indisponível ou falhar.
        veredito = None
        t_analise_start = time.time()
        try:
            veredito = executar_squad_para_lote(all_notas, client_name, client_cpf)
        except Exception as exc:
            logger.warning("Squad Horizon-Blue lançou exceção inesperada: %s", exc)
            veredito = None

        if veredito:
            t_squad = time.time() - t_analise_start
            logger.info(f"⏱️  [SQUAD HORIZON-BLUE] {t_squad:.1f}s — multiagente Claude OK")
        else:
            # Fallback local determinístico
            veredito = gerar_veredito_local(all_notas, client_name, analise)
            t_analise = time.time() - t_analise_start
            logger.info(
                f"⏱️  [ANÁLISE LOCAL] {t_analise:.2f}s — Score: {score_risco:.3f}, Nível: {nivel_risco}"
            )
        _log_tempo("ANÁLISE CONCLUÍDA")

        # Geração da Planilha IRPF (premium design) — novo formato padrão
        tasks_status[task_id] = {"status": "gerando_planilha", "progress": 65}
        dados_planilha = None          # inicializado antes do try — usado também pelo PDF
        t_planilha_start = time.time()
        try:
            dados_planilha = gerar_dados_planilha(all_notas, client_name, client_cpf)
            html_planilha = gerar_html_planilha_premium(dados_planilha)
            t_planilha = time.time() - t_planilha_start
            logger.info(f"⏱️  [PLANILHA IRPF PREMIUM] {t_planilha:.3f}s")
            _log_tempo("PLANILHA PREMIUM GERADA")
        except Exception as e_planilha:
            logger.error(f"Erro ao gerar planilha premium: {e_planilha}")
            logger.info("Fallback para planilha simples")
            try:
                html_planilha = gerar_html_planilha(dados_planilha)
            except Exception as e_fallback:
                logger.error(f"Erro no fallback da planilha: {e_fallback}")
                html_planilha = "<p>Erro ao gerar planilha IRPF</p>"

        # Salvar AMBOS: planilha HTML (visualização) + Laudo PDF (download).
        # São outputs complementares e o frontend usa cada um pra um propósito.
        tasks_status[task_id] = {"status": "gerando_relatorio", "progress": 80}
        os.makedirs(os.path.join("data", "laudos"), exist_ok=True)
        relatorio_path = None

        # 1) Planilha HTML (rápido, ~1ms) — endpoint /planilha/{task_id}
        planilha_filename = f"Relatorio_IRPF_{task_id[:8]}.html"
        planilha_path = os.path.join("data", "laudos", planilha_filename)
        try:
            t_html_start = time.time()
            with open(planilha_path, "w", encoding="utf-8") as f:
                f.write(html_planilha)
            t_html = time.time() - t_html_start
            logger.info(f"⏱️  [HTML TOTAL] {t_html:.3f}s — {modo_relatorio}")
            _log_tempo("HTML GERADO")
        except Exception as e_html:
            logger.error(f"Erro ao salvar HTML: {e_html}")
            # HTML falhar não é fatal — segue para gerar PDF
            planilha_path = None

        # 2) LAUDO ORGAUDI 1.0 — motor paramétrico forense (PRIMARIO)
        #    PDF profissional 11 páginas: Regra 1, F1-F6, T-01..T-08, IRPF, Funrural
        pdf_filename = f"Laudo_{task_id[:8]}.pdf"
        pdf_path = os.path.join("data", "laudos", pdf_filename)
        # Roda a bateria forense (compativel com gerador antigo, ainda usada para score)
        try:
            resultado_forense = auditar_lote(all_notas, client_name, client_cpf)
            score_risco = resultado_forense.score_risco
            nivel_risco = resultado_forense.nivel_risco
        except Exception as e_for:
            logger.warning(f"Bateria forense legada falhou (nao-fatal): {e_for}")
            resultado_forense = None

        try:
            t_pdf_start = time.time()
            # Gera PDF OrgAudi 1.0 (preferencial) — motor parametrico completo
            gerar_laudo_orgaudi(
                notas=all_notas,
                cliente_nome=client_name,
                cliente_cpf=client_cpf,
                saida=pdf_path,
                veredito_ia=veredito,
            )
            t_pdf = time.time() - t_pdf_start
            logger.info(f"⏱️  [LAUDO ORGAUDI 1.0] {t_pdf:.1f}s — {pdf_filename}")
            _log_tempo("PDF GERADO")
            relatorio_path = pdf_path
        except Exception as e_oa:
            logger.error(f"OrgAudi 1.0 falhou — fallback para legado: {e_oa}", exc_info=True)
            # Fallback 1: gerador ORGATEC antigo
            try:
                if resultado_forense is None:
                    resultado_forense = auditar_lote(all_notas, client_name, client_cpf)
                gerar_relatorio_tecnico_pdf(resultado_forense, pdf_path, dados_planilha)
                logger.warning("Usando gerador ORGATEC legado (fallback 1).")
                relatorio_path = pdf_path
                _log_tempo("PDF GERADO (fallback)")
            except Exception as e_pdf:
                logger.error(f"Gerador ORGATEC tambem falhou: {e_pdf}")
                # Fallback 2: gerador antigo simplificado
                try:
                    gerar_pdf(
                        notas=all_notas,
                        saida=pdf_path,
                        analise_ia=veredito,
                        nome_contribuinte=client_name,
                        cpf_contribuinte=client_cpf,
                        risco_nivel=nivel_risco,
                        score_risco=score_risco,
                        modo_relatorio=modo_relatorio,
                        formato='pdf',
                    )
                    relatorio_path = pdf_path
                    logger.warning("Usando gerador legado simplificado (fallback 2).")
                except Exception as e_legado:
                    logger.error(f"Todos os geradores falharam: {e_legado}")
                    if planilha_path:
                        relatorio_path = planilha_path
                    else:
                        tasks_status[task_id] = {
                            "status": "erro",
                            "erro": f"Falha na geração de relatórios: {e_oa}",
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

        # Upload para Supabase Storage (não-bloqueante, falha silenciosa)
        try:
            from src.infrastructure.supabase_client import supabase_configurado, upload_laudo
            if supabase_configurado() and relatorio_path and os.path.exists(relatorio_path):
                with open(relatorio_path, "rb") as _f:
                    _conteudo = _f.read()
                _ct = "application/pdf" if relatorio_path.endswith(".pdf") else "text/html"
                upload_laudo(os.path.basename(relatorio_path), _conteudo, _ct)
        except Exception as _e_storage:
            logger.warning(f"Upload Supabase Storage falhou (arquivo mantido local): {_e_storage}")

        # Marcar como concluído IMEDIATAMENTE (não-bloqueante)
        tasks_status[task_id] = {
            "status": "concluido",
            "progress": 100,
            "resultado": veredito,
            "total_notas": len(all_notas)
        }

        # Salvar em banco em thread separada (não bloqueia resposta)
        def _salvar_laudo_async(laudo_data_parcial, cli_name, cli_cpf, notas_extraidas):
            for tentativa in range(3):
                db_async = None
                try:
                    db_async = SessionLocal()
                    cli_cpf_fmt = _formatar_documento(cli_cpf)
                    cliente = _get_or_create_cliente(db_async, cli_name, cli_cpf_fmt)
                    laudo_data_parcial['cliente_id'] = cliente.id
                    novo_laudo = Laudo(**laudo_data_parcial)
                    db_async.add(novo_laudo)
                    t_commit_start = time.time()
                    db_async.commit()
                    t_commit = time.time() - t_commit_start
                    logger.info(f"⏱️  [DB COMMIT ASYNC] {t_commit:.2f}s (Tentativa {tentativa + 1})")
                    break  # Sucesso, sai do loop
                except Exception as e:
                    if db_async:
                        db_async.rollback()
                    logger.error(f"Erro no commit async (Tentativa {tentativa + 1}/3): {e}")
                    time.sleep(1) # Aguarda 1s antes de tentar novamente
                finally:
                    if db_async:
                        db_async.close()

            try:
                salvas, ignoradas = salvar_notas_bd(notas_extraidas, laudo_data_parcial.get("veredito_ia", ""))
                logger.info(f"⏱️  [DB NOTAS] Salvas: {salvas} | Ignoradas: {ignoradas}")
            except Exception as e_bd:
                logger.error(f"Erro ao salvar notas no BD: {e_bd}")

            # Gera embeddings semânticos para as notas salvas (Voyage AI → Supabase)
            # Executado em thread daemon para não bloquear a resposta da auditoria.
            # Falha silenciosa — embeddings são best-effort, não críticos para o fluxo.
            def _indexar_embeddings():
                try:
                    import os

                    from api.services.embeddings import salvar_embedding
                    from src.infrastructure.database_v2 import NotaModel, ProdutoModel
                    from src.infrastructure.database_v2 import SessionLocal as _SL
                    if not os.getenv("VOYAGE_API_KEY"):
                        return  # Voyage não configurado — pula silenciosamente
                    db_emb = _SL()
                    try:
                        cliente_id_emb = laudo_data_parcial.get("cliente_id")
                        for nfa in notas_extraidas:
                            # Busca a nota recém-salva pelo número
                            nota_db = db_emb.query(NotaModel).filter(
                                NotaModel.numero == nfa.numero
                            ).order_by(NotaModel.id.desc()).first()
                            if not nota_db:
                                continue
                            prods = db_emb.query(ProdutoModel).filter(
                                ProdutoModel.nota_id == nota_db.id
                            ).all()
                            desc_prods = "; ".join(
                                p.descricao for p in prods if p.descricao
                            ) or None
                            salvar_embedding(
                                nota_id=nota_db.id,
                                cliente_id=cliente_id_emb,
                                cliente_nome=cli_name,
                                natureza=nota_db.natureza,
                                emissao=nota_db.emissao,
                                numero=nota_db.numero,
                                descricao_produtos=desc_prods,
                            )
                    finally:
                        db_emb.close()
                    logger.info(f"[EMBEDDINGS] Indexação concluída para {len(notas_extraidas)} notas")
                except Exception as e_emb:
                    logger.warning(f"[EMBEDDINGS] Falha na indexação (não crítico): {e_emb}")

            threading.Thread(target=_indexar_embeddings, daemon=True).start()

        laudo_data = {
            'veredito_ia': veredito[:500],
            'qtd_notas': len(all_notas),
            'valor_total': valor_total_lote,
            'qtd_anomalias': veredito.count("ANOMALIA") if "ANOMALIA" in veredito else 0,
            'pdf_path': relatorio_path
        }

        db_thread = threading.Thread(target=_salvar_laudo_async, args=(laudo_data, client_name, client_cpf, all_notas), daemon=True)
        db_thread.start()

        _log_tempo("FIM")
        logger.info(f"[SUCESSO] Auditoria {task_id} concluída com IA: {ia_utilizada} (BD salvando em background)")

    except Exception as e:
        logger.error(f"Erro no processamento da auditoria {task_id}: {e}")
        tasks_status[task_id] = {"status": "erro", "erro": str(e)}
