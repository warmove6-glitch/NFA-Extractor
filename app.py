"""
OrgExtNF — SEFAZ
Interface gráfica moderna com extração, IA e geração de PDF/Excel.
"""

import sys
import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from datetime import datetime

import customtkinter as ctk
from PIL import Image
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

LOGO_PATH = Path(__file__).parent / 'assets' / 'logo.png'

# Configuração visual
ctk.set_appearance_mode('dark')
ctk.set_default_color_theme('blue')

from constants import hex_cor

# ── Paleta — Enterprise Dark (SEFAZ/Auditoria) ───────────────────────────────
BG       = hex_cor('BG')
BG2      = hex_cor('BG2')
BG3      = hex_cor('BG3')
BG4      = hex_cor('BG4')
BORDER   = hex_cor('BORDER')
CYAN     = hex_cor('CYAN')
PRIMARY  = hex_cor('PRIMARY')
GREEN    = hex_cor('GREEN')
ORANGE   = hex_cor('ORANGE')
RED      = hex_cor('RED')
TEXT     = hex_cor('TEXT')
TEXT_DIM = hex_cor('TEXT_DIM')
WHITE    = hex_cor('WHITE')


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title('OrgExtNF — SEFAZ')
        self.geometry('1280x820')
        self.minsize(960, 640)
        self.configure(fg_color=BG)

        self.notas = []
        self.analise_texto = ''
        self._pdf_path = ''
        self._after_id = None

        self._build_ui()

    # ── UI ───────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # Cabeçalho
        header = ctk.CTkFrame(self, fg_color=BG2, corner_radius=0, height=64)
        header.pack(fill='x', side='top')
        header.pack_propagate(False)

        # Logo no header
        if LOGO_PATH.exists():
            _img = Image.open(LOGO_PATH).resize((40, 40), Image.LANCZOS)
            self._logo_ctk = ctk.CTkImage(light_image=_img, dark_image=_img, size=(40, 40))
            ctk.CTkLabel(header, image=self._logo_ctk, text='').pack(side='left', padx=(16, 4), pady=12)

        ctk.CTkLabel(header, text='OrgExtNF  —  SEFAZ',
                     font=ctk.CTkFont('Segoe UI', 17, 'bold'),
                     text_color=CYAN).pack(side='left', padx=(4, 0), pady=14)

        ctk.CTkLabel(header, text='Estado de Goiás · Notas Fiscais Avulsas',
                     font=ctk.CTkFont('Segoe UI', 12),
                     text_color=TEXT_DIM).pack(side='left', padx=10)

        # Barra de ação (selecionar PDF)
        action = ctk.CTkFrame(self, fg_color=BG3, corner_radius=0, height=56)
        action.pack(fill='x', side='top')
        action.pack_propagate(False)

        self.lbl_arquivo = ctk.CTkLabel(action, text='Nenhum arquivo selecionado',
                                         font=ctk.CTkFont('Segoe UI', 12),
                                         text_color=TEXT_DIM)
        self.lbl_arquivo.pack(side='left', padx=16, pady=14)

        self.btn_extrair = ctk.CTkButton(action, text='Extrair Dados',
                                          fg_color=PRIMARY, text_color=WHITE, hover_color=CYAN,
                                          font=ctk.CTkFont('Segoe UI', 12, 'bold'),
                                          width=140, height=34, corner_radius=6,
                                          command=self._extrair, state='disabled')
        self.btn_extrair.pack(side='right', padx=12, pady=11)

        ctk.CTkButton(action, text='Selecionar PDF',
                       fg_color=BG2, hover_color=BG4, border_color=BORDER, border_width=1,
                       text_color=TEXT, font=ctk.CTkFont('Segoe UI', 12),
                       width=148, height=34, corner_radius=6,
                       command=self._selecionar_pdf).pack(side='right', padx=4, pady=11)

        # Barra de progresso
        self.progress_frame = ctk.CTkFrame(self, fg_color=BG, corner_radius=0, height=4)
        self.progress_frame.pack(fill='x')
        self.progress = ctk.CTkProgressBar(self.progress_frame, fg_color=BG3,
                                            progress_color=CYAN, height=4, corner_radius=0)
        self.progress.set(0)
        self.progress.pack(fill='x')

        # Cards KPI
        self.cards_frame = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.cards_frame.pack(fill='x', padx=14, pady=(10, 0))
        self._build_cards()

        # Notebook (abas)
        self.notebook = ctk.CTkTabview(self, fg_color=BG2, corner_radius=6,
                                        segmented_button_fg_color=BG3,
                                        segmented_button_selected_color=CYAN,
                                        segmented_button_selected_hover_color=CYAN,
                                        text_color=TEXT)
        self.notebook.pack(fill='both', expand=True, padx=14, pady=10)

        for tab in ('Notas Fiscais', 'Itens Detalhados', 'Por Destinatario', 'Graficos', 'Tabela IR', 'Analise IA'):
            self.notebook.add(tab)

        self._build_tab_notas()
        self._build_tab_itens()
        self._build_tab_dest()
        self._build_tab_graficos()
        self._build_tab_ir()
        self._build_tab_ia()

        # Barra inferior de ações
        bottom = ctk.CTkFrame(self, fg_color=BG3, corner_radius=0, height=56)
        bottom.pack(fill='x', side='bottom')
        bottom.pack_propagate(False)

        self.lbl_status = ctk.CTkLabel(bottom, text='Aguardando arquivo PDF...',
                                        font=ctk.CTkFont('Segoe UI', 11),
                                        text_color=TEXT_DIM)
        self.lbl_status.pack(side='left', padx=16)

        _btn_cfg = dict(fg_color=BG2, border_width=1, height=34, corner_radius=6,
                        font=ctk.CTkFont('Segoe UI', 12))

        self.btn_pdf = ctk.CTkButton(bottom, text='Gerar PDF',
                                      border_color=GREEN, hover_color='#166534',
                                      text_color=GREEN, width=130, state='disabled',
                                      command=self._gerar_pdf, **_btn_cfg)
        self.btn_pdf.pack(side='right', padx=8, pady=11)

        self.btn_excel = ctk.CTkButton(bottom, text='Exportar Excel',
                                        border_color=ORANGE, hover_color='#92400E',
                                        text_color=ORANGE, width=138, state='disabled',
                                        command=self._exportar_excel, **_btn_cfg)
        self.btn_excel.pack(side='right', padx=4, pady=11)

        self.btn_db = ctk.CTkButton(bottom, text='Salvar no BD',
                                     border_color='#10B981', hover_color='#065F46',
                                     text_color='#10B981', width=130, state='disabled',
                                     command=self._salvar_postgres, **_btn_cfg)
        self.btn_db.pack(side='right', padx=4, pady=11)

        self.btn_ia = ctk.CTkButton(bottom, text='Analisar com IA',
                                     border_color=CYAN, hover_color=PRIMARY,
                                     text_color=CYAN, width=148, state='disabled',
                                     command=self._analisar_ia, **_btn_cfg)
        self.btn_ia.pack(side='right', padx=4, pady=11)

        self.btn_limpar = ctk.CTkButton(bottom, text='Limpar Dados',
                                         border_color=RED, hover_color='#7F1D1D',
                                         text_color=RED, width=130, state='disabled',
                                         command=self._limpar_dados, **_btn_cfg)
        self.btn_limpar.pack(side='right', padx=4, pady=11)

    def _build_cards(self):
        for w in self.cards_frame.winfo_children():
            w.destroy()

        if not self.notas:
            for label, cor in [('Total de Notas', CYAN), ('Cabeças', GREEN),
                                ('Valor Total', ORANGE), ('Ticket Médio', TEXT_DIM),
                                ('Período', TEXT_DIM)]:
                card = ctk.CTkFrame(self.cards_frame, fg_color=BG2, corner_radius=8,
                                    border_color=BORDER, border_width=1)
                card.pack(side='left', padx=5, fill='both', expand=True)
                # barra de cor no topo do card
                ctk.CTkFrame(card, fg_color=cor, height=3, corner_radius=0
                             ).pack(fill='x')
                ctk.CTkLabel(card, text=label.upper(), font=ctk.CTkFont('Segoe UI', 10, 'bold'),
                             text_color=TEXT_DIM).pack(padx=14, pady=(10, 0), anchor='w')
                ctk.CTkLabel(card, text='—', font=ctk.CTkFont('Segoe UI', 20, 'bold'),
                             text_color=cor).pack(padx=14, pady=(3, 12), anchor='w')
            return

        from extractor import resumo_geral
        res = resumo_geral(self.notas)
        periodo_min = min(n.emissao for n in self.notas if n.emissao)
        periodo_max = max(n.emissao for n in self.notas if n.emissao)
        cat = res['por_categoria']

        def _card(parent, titulo, valor_principal, cor, subtitulo=None, subcor=None):
            card = ctk.CTkFrame(parent, fg_color=BG2, corner_radius=8,
                                border_color=BORDER, border_width=1)
            card.pack(side='left', padx=5, fill='both', expand=True)
            # barra de cor no topo do card
            ctk.CTkFrame(card, fg_color=cor, height=3, corner_radius=0
                         ).pack(fill='x')
            ctk.CTkLabel(card, text=titulo.upper(), font=ctk.CTkFont('Segoe UI', 10, 'bold'),
                         text_color=TEXT_DIM).pack(padx=14, pady=(10, 0), anchor='w')
            ctk.CTkLabel(card, text=valor_principal,
                         font=ctk.CTkFont('Segoe UI', 22, 'bold'),
                         text_color=cor).pack(padx=14, pady=(2, 0), anchor='w')
            if subtitulo:
                ctk.CTkLabel(card, text=subtitulo, font=ctk.CTkFont('Segoe UI', 10),
                             text_color=subcor or TEXT_DIM).pack(padx=14, pady=(2, 12), anchor='w')
            else:
                ctk.CTkLabel(card, text='', height=12).pack()

        # Card 1 — Notas totais com breakdown
        rem   = cat.get('REMESSA',      {})
        trf   = cat.get('TRANSFERENCIA',{})
        out   = cat.get('OUTRAS',       {})
        vnd   = cat.get('VENDA',        {})
        sub_nat = (
            f"V:{vnd.get('notas',0)}  "
            f"R:{rem.get('notas',0)}  "
            f"T:{trf.get('notas',0)}  "
            f"O:{out.get('notas',0)}"
        )
        _card(self.cards_frame, 'Total de Notas',
              str(res['total_notas']), CYAN,
              sub_nat, TEXT_DIM)

        # Card 2 — Cabeças: vendas vs total
        _card(self.cards_frame, 'Cabecas (Vendas)',
              f"{res['vendas_cabecas']:.0f}", GREEN,
              f"Total geral: {res['total_cabecas']:.0f} cab", TEXT_DIM)

        # Card 3 — Valor Tributável (somente vendas)
        _card(self.cards_frame, 'Valor Tributavel (Vendas)',
              f"R$ {res['vendas_valor']:,.2f}", ORANGE,
              f"Total c/ remessas: R$ {res['total_valor']:,.2f}", TEXT_DIM)

        # Card 4 — Remessas + Transferências (não tributáveis)
        val_nao_trib = rem.get('valor', 0) + trf.get('valor', 0)
        _card(self.cards_frame, 'Nao Tributavel (Rem+Transf)',
              f"R$ {val_nao_trib:,.2f}", RED,
              f"R:{rem.get('notas',0)} notas  T:{trf.get('notas',0)} notas", TEXT_DIM)

        # Card 5 — Business Intelligence (Preço Médio e HHI)
        _card(self.cards_frame, 'Preco Medio (Vendas)',
              f"R$ {res['preco_medio_cabeca']:,.2f}",
              CYAN, f"Risco: {res['risco_hhi']}", TEXT_DIM)

    # ── Tabelas ──────────────────────────────────────────────────────────────
    def _make_treeview(self, parent, colunas: list[tuple], height=22):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Dark.Treeview',
                         background=BG2, foreground=TEXT,
                         fieldbackground=BG2, rowheight=30,
                         bordercolor=BG2, lightcolor=BG2, borderwidth=0,
                         font=('Segoe UI', 11))
        style.configure('Dark.Treeview.Heading',
                         background=BG3, foreground=CYAN,
                         relief='flat', font=('Segoe UI', 11, 'bold'))
        style.map('Dark.Treeview',
                  background=[('selected', PRIMARY)],
                  foreground=[('selected', WHITE)])

        frame = ctk.CTkFrame(parent, fg_color=BG2, corner_radius=0)
        frame.pack(fill='both', expand=True)

        ids = [c[0] for c in colunas]
        tv = ttk.Treeview(frame, columns=ids, show='headings',
                           style='Dark.Treeview', height=height)

        vsb = ttk.Scrollbar(frame, orient='vertical',   command=tv.yview)
        hsb = ttk.Scrollbar(frame, orient='horizontal',  command=tv.xview)
        tv.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        for col_id, titulo, largura, ancora in colunas:
            tv.heading(col_id, text=titulo,
                       command=lambda c=col_id: self._sort_tree(tv, c, False))
            tv.column(col_id, width=largura, anchor=ancora, minwidth=50)

        vsb.pack(side='right', fill='y')
        hsb.pack(side='bottom', fill='x')
        tv.pack(fill='both', expand=True)

        tv.tag_configure('odd',  background=BG2)
        tv.tag_configure('even', background=BG4)
        tv.tag_configure('venda',   foreground='#79C0FF')
        tv.tag_configure('remessa', foreground='#D2A8FF')

        return tv

    def _sort_tree(self, tv, col, reverse):
        data = [(tv.set(k, col), k) for k in tv.get_children('')]
        try:
            data.sort(key=lambda x: float(x[0].replace('.','').replace(',','.')), reverse=reverse)
        except ValueError:
            data.sort(key=lambda x: x[0], reverse=reverse)
        for i, (_, k) in enumerate(data):
            tv.move(k, '', i)
        tv.heading(col, command=lambda: self._sort_tree(tv, col, not reverse))

    def _build_tab_notas(self):
        tab = self.notebook.tab('Notas Fiscais')
        colunas = [
            ('num',       'Num. NFA',    90,  'w'),
            ('emissao',   'Emissao',     90,  'center'),
            ('natureza',  'Natureza',    140, 'w'),
            ('local',     'Local Emissao', 180, 'w'),
            ('dest',      'Destinatario', 220, 'w'),
            ('dest_cpf',  'CPF/CNPJ Dest', 140, 'w'),
            ('dest_mun',  'Municipio Dest', 140, 'w'),
            ('transp',    'Transportador', 180, 'w'),
            ('cabecas',   'Cabecas',     70,  'e'),
            ('valor',     'Valor Total', 110, 'e'),
            ('chave',     'Chave de Acesso', 340, 'w'),
        ]
        self.tv_notas = self._make_treeview(tab, colunas)

    def _build_tab_itens(self):
        tab = self.notebook.tab('Itens Detalhados')
        colunas = [
            ('num',      'NFA',         80,  'w'),
            ('emissao',  'Emissao',     90,  'center'),
            ('dest',     'Destinatario', 200, 'w'),
            ('cod',      'Codigo',      60,  'center'),
            ('desc',     'Descricao',   300, 'w'),
            ('qtd',      'Qtd.',        60,  'e'),
            ('unit',     'Vlr. Unit.',  100, 'e'),
            ('icms',     'Vlr. ICMS',   90,  'e'),
            ('total',    'Vlr. Total',  110, 'e'),
        ]
        self.tv_itens = self._make_treeview(tab, colunas)

    def _build_tab_dest(self):
        tab = self.notebook.tab('Por Destinatario')
        colunas = [
            ('nome',     'Destinatario',  260, 'w'),
            ('cpf',      'CPF/CNPJ',      140, 'w'),
            ('mun',      'Municipio',     140, 'w'),
            ('notas',    'Notas',         60,  'e'),
            ('cabecas',  'Cabecas',       80,  'e'),
            ('valor',    'Valor Total',   120, 'e'),
            ('medio',    'Ticket Medio',  120, 'e'),
        ]
        self.tv_dest = self._make_treeview(tab, colunas)

    def _build_tab_graficos(self):
        tab = self.notebook.tab('Graficos')
        self._graf_frame = ctk.CTkFrame(tab, fg_color=BG, corner_radius=0)
        self._graf_frame.pack(fill='both', expand=True)
        self._graf_canvas_widgets = []
        ctk.CTkLabel(self._graf_frame,
                     text='Extraia os dados para visualizar os gráficos.',
                     font=ctk.CTkFont('Segoe UI', 11), text_color=TEXT_DIM
                     ).pack(pady=40)

    def _atualizar_graficos(self):
        for w in self._graf_frame.winfo_children():
            w.destroy()
        self._graf_canvas_widgets.clear()

        from extractor import resumo_geral
        res = resumo_geral(self.notas)

        # Tema matplotlib escuro
        plt.rcParams.update({
            'figure.facecolor':  '#161B22',
            'axes.facecolor':    '#0D1117',
            'axes.edgecolor':    '#30363D',
            'axes.labelcolor':   '#E6EDF3',
            'xtick.color':       '#8B949E',
            'ytick.color':       '#8B949E',
            'text.color':        '#E6EDF3',
            'grid.color':        '#21262D',
            'grid.linewidth':    0.6,
        })

        # ── Linha 1: Evolução Mensal (valor) + Cabeças por Mês ───────────────
        row1 = ctk.CTkFrame(self._graf_frame, fg_color=BG, corner_radius=0)
        row1.pack(fill='both', expand=True, padx=6, pady=(6,3))

        meses          = list(res['por_mes'].keys())
        valores_total  = [v['valor']          for v in res['por_mes'].values()]
        valores_vendas = [v['vendas_valor']    for v in res['por_mes'].values()]
        cabecas_total  = [v['cabecas']         for v in res['por_mes'].values()]
        cabecas_vendas = [v['vendas_cabecas']  for v in res['por_mes'].values()]
        x = range(len(meses))

        # Gráfico 1 — Faturamento: Vendas vs Total (agrupado)
        fig1, ax1 = plt.subplots(figsize=(5.5, 2.8), tight_layout=True)
        w = 0.38
        bars_t = ax1.bar([i - w/2 for i in x], valores_total,  width=w,
                         color='#30363D', edgecolor='#58A6FF', linewidth=0.6, label='Total')
        bars_v = ax1.bar([i + w/2 for i in x], valores_vendas, width=w,
                         color='#1F6FEB', edgecolor='#58A6FF', linewidth=0.6, label='Vendas')
        ax1.set_title('Faturamento Mensal — Total vs Vendas (R$)', fontsize=8.5, pad=6)
        ax1.yaxis.set_major_formatter(mticker.FuncFormatter(
            lambda x, _: f'R${x/1000:.0f}k' if x >= 1000 else f'R${x:.0f}'))
        ax1.set_xticks(list(x)); ax1.set_xticklabels(meses, fontsize=7, rotation=35)
        ax1.tick_params(axis='y', labelsize=7)
        ax1.legend(fontsize=7, framealpha=0.2)
        ax1.grid(axis='y', linestyle='--')
        self._embed_fig(fig1, row1, side='left')

        # Gráfico 2 — Cabeças: Vendas vs Total
        fig2, ax2 = plt.subplots(figsize=(5.5, 2.8), tight_layout=True)
        ax2.plot(list(x), cabecas_total,  color='#30363D', marker='s', linewidth=1.5,
                 markersize=4, linestyle='--', label='Total')
        ax2.plot(list(x), cabecas_vendas, color='#3FB950', marker='o', linewidth=2,
                 markersize=5, label='Vendas')
        ax2.fill_between(list(x), cabecas_vendas, alpha=0.12, color='#3FB950')
        ax2.set_xticks(list(x)); ax2.set_xticklabels(meses, fontsize=7, rotation=35)
        ax2.tick_params(axis='y', labelsize=7)
        ax2.set_title('Cabeças por Mês — Total vs Vendas', fontsize=8.5, pad=6)
        ax2.legend(fontsize=7, framealpha=0.2)
        ax2.grid(linestyle='--')
        self._embed_fig(fig2, row1, side='left')

        # Gráfico 3 — Pizza por categoria fiscal
        fig3, ax3 = plt.subplots(figsize=(3.2, 2.8), tight_layout=True)
        cat_map    = res['por_categoria']
        cat_ordem  = ['VENDA', 'REMESSA', 'TRANSFERENCIA', 'OUTRAS']
        cat_labels = [c for c in cat_ordem if c in cat_map]
        cat_vals   = [cat_map[c]['valor'] for c in cat_labels]
        cores_cat  = {'VENDA': '#1F6FEB', 'REMESSA': '#D29922',
                      'TRANSFERENCIA': '#8B949E', 'OUTRAS': '#F85149'}
        cores_pie  = [cores_cat.get(c, '#58A6FF') for c in cat_labels]
        wedges, _, autotexts = ax3.pie(
            cat_vals, labels=None, autopct='%1.0f%%',
            colors=cores_pie, startangle=90,
            pctdistance=0.75, wedgeprops=dict(linewidth=0.5, edgecolor='#21262D'))
        for at in autotexts:
            at.set_fontsize(7)
        leg_labels = [f"{c} ({cat_map[c]['notas']})" for c in cat_labels]
        ax3.legend(leg_labels, loc='lower center', fontsize=6.5,
                   bbox_to_anchor=(0.5, -0.22), ncol=2,
                   framealpha=0, labelcolor='#E6EDF3')
        ax3.set_title('Valor por Categoria Fiscal', fontsize=8.5, pad=6)
        self._embed_fig(fig3, row1, side='left')

        # ── Linha 2: Top compradores + Tabela resumo ──────────────────────────
        row2 = ctk.CTkFrame(self._graf_frame, fg_color=BG, corner_radius=0)
        row2.pack(fill='both', expand=True, padx=6, pady=(3,6))

        top = res['top_dest'][:8]
        nomes_top = [d['nome'][:22] for d in top]
        vals_top  = [d['valor'] for d in top]

        # Gráfico 4 — Top compradores horizontal
        fig4, ax4 = plt.subplots(figsize=(7.0, 3.0), tight_layout=True)
        cores_bar = ['#58A6FF' if i == 0 else '#1F6FEB' for i in range(len(nomes_top))]
        hbars = ax4.barh(nomes_top[::-1], vals_top[::-1], color=cores_bar[::-1],
                         edgecolor='#30363D', linewidth=0.4, height=0.6)
        ax4.xaxis.set_major_formatter(mticker.FuncFormatter(
            lambda x, _: f'R${x/1000:.0f}k'))
        ax4.tick_params(axis='y', labelsize=7)
        ax4.tick_params(axis='x', labelsize=7)
        ax4.set_title('Top Compradores por Valor (R$)', fontsize=9, pad=6)
        ax4.grid(axis='x', linestyle='--')
        for bar, v in zip(hbars, vals_top[::-1]):
            ax4.text(bar.get_width() * 1.01, bar.get_y() + bar.get_height()/2,
                     f'R${v/1000:.0f}k', va='center', fontsize=6.5, color='#58A6FF')
        self._embed_fig(fig4, row2, side='left')

        # Tabela resumo dos compradores
        self._build_tabela_resumo(row2, res)

    def _embed_fig(self, fig, parent, side='left'):
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        w = canvas.get_tk_widget()
        w.configure(bg='#0D1117', highlightthickness=0)
        w.pack(side=side, fill='both', expand=True, padx=4, pady=2)
        self._graf_canvas_widgets.append(canvas)
        plt.close(fig)

    def _build_tabela_resumo(self, parent, res):
        frame = ctk.CTkFrame(parent, fg_color=BG2, corner_radius=6,
                             border_color=BORDER, border_width=1)
        frame.pack(side='left', fill='both', expand=False, padx=4, pady=2, ipadx=6, ipady=6)

        ctk.CTkLabel(frame, text='RESUMO GERAL',
                     font=ctk.CTkFont('Segoe UI', 9, 'bold'),
                     text_color=CYAN).grid(row=0, column=0, columnspan=2,
                                           pady=(8,6), padx=12, sticky='w')

        top1_pct = (res['top_dest'][0]['valor'] / res['vendas_valor'] * 100
                    ) if res['top_dest'] and res['vendas_valor'] else 0
        top3_val = sum(d['valor'] for d in res['top_dest'][:3])
        top3_pct = top3_val / res['vendas_valor'] * 100 if res['vendas_valor'] else 0
        cat      = res['por_categoria']

        linhas = [
            ('── VENDAS (tributável) ──', '',           True),
            ('Notas de Venda',           str(res['vendas_notas'])),
            ('Cabeças (Vendas)',          f"{res['vendas_cabecas']:.0f}"),
            ('Valor Tributável',          f"R$ {res['vendas_valor']:,.2f}"),
            ('Ticket Médio (Vendas)',     f"R$ {res['vendas_ticket_medio']:,.2f}"),
            ('── NÃO TRIBUTÁVEL ──',      '',           True),
            ('Remessas',                  f"{cat.get('REMESSA',{}).get('notas',0)} notas  "
                                          f"R$ {cat.get('REMESSA',{}).get('valor',0):,.2f}"),
            ('Transferências',            f"{cat.get('TRANSFERENCIA',{}).get('notas',0)} notas  "
                                          f"R$ {cat.get('TRANSFERENCIA',{}).get('valor',0):,.2f}"),
            ('Outras',                    f"{cat.get('OUTRAS',{}).get('notas',0)} notas  "
                                          f"R$ {cat.get('OUTRAS',{}).get('valor',0):,.2f}"),
            ('── GERAL ──',               '',           True),
            ('Total de Notas',            str(res['total_notas'])),
            ('Valor Total (todas)',        f"R$ {res['total_valor']:,.2f}"),
            ('Conc. Top 1 (s/ vendas)',   f"{top1_pct:.1f}%"),
            ('Conc. Top 3 (s/ vendas)',   f"{top3_pct:.1f}%"),
        ]
        for i, entrada in enumerate(linhas, 1):
            is_header = len(entrada) == 3
            label, valor = entrada[0], entrada[1]
            if is_header:
                row_f = ctk.CTkFrame(frame, fg_color=BG3, corner_radius=0)
                row_f.grid(row=i, column=0, columnspan=2, sticky='ew', padx=4, pady=(4,1))
                ctk.CTkLabel(row_f, text=label, font=ctk.CTkFont('Segoe UI', 7, 'bold'),
                             text_color=CYAN).pack(padx=8, pady=2, anchor='w')
            else:
                bg = BG4 if i % 2 == 0 else BG2
                row_f = ctk.CTkFrame(frame, fg_color=bg, corner_radius=0)
                row_f.grid(row=i, column=0, columnspan=2, sticky='ew', padx=4, pady=1)
                ctk.CTkLabel(row_f, text=label, font=ctk.CTkFont('Segoe UI', 8),
                             text_color=TEXT_DIM, width=155, anchor='w'
                             ).pack(side='left', padx=(8,4), pady=3)
                ctk.CTkLabel(row_f, text=valor, font=ctk.CTkFont('Segoe UI', 8, 'bold'),
                             text_color=TEXT, anchor='e'
                             ).pack(side='right', padx=(4,8), pady=3)

    def _build_tab_ir(self):
        tab = self.notebook.tab('Tabela IR')

        # ── Barra de ação com botão de exportação PDF ──────────────────────
        barra = ctk.CTkFrame(tab, fg_color=BG2, height=40, corner_radius=0)
        barra.pack(fill='x', side='top')
        barra.pack_propagate(False)
        self.btn_ir_pdf = ctk.CTkButton(
            barra, text='⬇  Exportar PDF — Planilha IR',
            font=ctk.CTkFont('Segoe UI', 10, 'bold'),
            fg_color=PRIMARY, hover_color='#6D5AE6',
            text_color=WHITE, height=28, width=240,
            command=self._exportar_pdf_ir, state='disabled',
        )
        self.btn_ir_pdf.pack(side='right', padx=12, pady=6)
        ctk.CTkLabel(
            barra,
            text='Planilha de Gado para IRPF — Atividade Rural (Lei 8.023/90)',
            font=ctk.CTkFont('Segoe UI', 9), text_color=TEXT_DIM,
        ).pack(side='left', padx=12)

        # ── Área de scroll com as tabelas ──────────────────────────────────
        self._ir_scroll = ctk.CTkScrollableFrame(tab, fg_color=BG, corner_radius=0)
        self._ir_scroll.pack(fill='both', expand=True, padx=4, pady=4)
        ctk.CTkLabel(self._ir_scroll,
                     text='Extraia os dados para visualizar a Tabela IR.',
                     font=ctk.CTkFont('Segoe UI', 11), text_color=TEXT_DIM
                     ).pack(pady=40)

    def _ir_secao(self, titulo: str, cor: str, linhas: list,
                  tot_notas: int, tot_cab: float, tot_val: float):
        # Colunas idênticas ao modelo .docx — sem coluna % TOTAL
        COLS    = ['MÊS', 'Q NOTAS', 'CABEÇAS', 'VALOR (R$)']
        WIDTHS  = [140, 85, 100, 185]
        ANCHORS = ['w', 'center', 'e', 'e']

        sec = ctk.CTkFrame(self._ir_scroll, fg_color=BG2, corner_radius=8,
                           border_color=cor, border_width=1)
        sec.pack(fill='x', padx=10, pady=(0, 10))

        # Título da seção
        ctk.CTkLabel(sec, text=f'  {titulo}',
                     font=ctk.CTkFont('Segoe UI', 11, 'bold'),
                     text_color=cor, fg_color=BG3,
                     corner_radius=6, height=30
                     ).pack(fill='x', padx=0, pady=(0, 4))

        # Cabeçalho
        hdr = ctk.CTkFrame(sec, fg_color=BG3, corner_radius=0)
        hdr.pack(fill='x', padx=8)
        for j, (col, w, a) in enumerate(zip(COLS, WIDTHS, ANCHORS)):
            ctk.CTkLabel(hdr, text=col, font=ctk.CTkFont('Segoe UI', 8, 'bold'),
                         text_color=cor, width=w, anchor=a
                         ).grid(row=0, column=j, padx=4, pady=5)

        # Linhas de dados — todos os 12 meses (igual ao modelo .docx)
        for row_idx, (mes, q, cab, val) in enumerate(linhas):
            tem_dado = q > 0 or cab > 0 or val > 0
            bg = BG4 if row_idx % 2 == 0 else BG2
            rf = ctk.CTkFrame(sec, fg_color=bg, corner_radius=0)
            rf.pack(fill='x', padx=8)
            dados = [
                mes,
                str(q) if tem_dado else '',
                f'{cab:.0f}' if tem_dado else '',
                f'R$ {val:,.2f}' if tem_dado else '',
            ]
            for j, (txt, w, a) in enumerate(zip(dados, WIDTHS, ANCHORS)):
                ctk.CTkLabel(rf, text=txt, font=ctk.CTkFont('Segoe UI', 8),
                             text_color=TEXT if tem_dado else TEXT_DIM,
                             width=w, anchor=a
                             ).grid(row=0, column=j, padx=4, pady=3)

        # Separador
        ctk.CTkFrame(sec, fg_color=cor, height=1, corner_radius=0
                     ).pack(fill='x', padx=8, pady=(2, 0))

        # Linha TOTAL
        tf = ctk.CTkFrame(sec, fg_color=BG3, corner_radius=0)
        tf.pack(fill='x', padx=8, pady=(0, 6))
        tot_dados = ['TOTAL', str(tot_notas), f'{tot_cab:.0f}', f'R$ {tot_val:,.2f}']
        for j, (txt, w, a) in enumerate(zip(tot_dados, WIDTHS, ANCHORS)):
            ctk.CTkLabel(tf, text=txt, font=ctk.CTkFont('Segoe UI', 8, 'bold'),
                         text_color=cor, width=w, anchor=a
                         ).grid(row=0, column=j, padx=4, pady=5)

    def _atualizar_tab_ir(self, res: dict):
        for w in self._ir_scroll.winfo_children():
            w.destroy()

        cat = res['por_categoria']
        pm  = res['por_mes']

        # Determina o ano de referência pelo mês mais frequente
        anos = [m.split('/')[1] for m in pm.keys() if '/' in m]
        ano  = max(set(anos), key=anos.count) if anos else '2025'

        # Meses fixos no formato MM/AAAA — 12 linhas sempre (fiel ao modelo .docx)
        MESES = [f'{mm:02d}/{ano}' for mm in range(1, 13)]
        NOMES = {
            f'01/{ano}': 'Janeiro',   f'02/{ano}': 'Fevereiro',
            f'03/{ano}': 'Março',     f'04/{ano}': 'Abril',
            f'05/{ano}': 'Maio',      f'06/{ano}': 'Junho',
            f'07/{ano}': 'Julho',     f'08/{ano}': 'Agosto',
            f'09/{ano}': 'Setembro',  f'10/{ano}': 'Outubro',
            f'11/{ano}': 'Novembro',  f'12/{ano}': 'Dezembro',
        }

        def _linhas(v_key: str, c_key: str, n_key: str):
            return [
                (NOMES[m],
                 pm.get(m, {}).get(n_key, 0),
                 pm.get(m, {}).get(c_key, 0.0),
                 pm.get(m, {}).get(v_key, 0.0))
                for m in MESES
            ]

        self._ir_secao('VENDAS', '#22C55E',
                       _linhas('vendas_valor', 'vendas_cabecas', 'vnd_notas'),
                       res['vendas_notas'], res['vendas_cabecas'], res['vendas_valor'])

        rem = cat.get('REMESSA', {})
        self._ir_secao('REMESSAS', '#EAB308',
                       _linhas('rem_valor', 'rem_cabecas', 'rem_notas'),
                       rem.get('notas', 0), rem.get('cabecas', 0.0), rem.get('valor', 0.0))

        trf = cat.get('TRANSFERENCIA', {})
        self._ir_secao('TRANSFERÊNCIAS', '#38BDF8',
                       _linhas('trf_valor', 'trf_cabecas', 'trf_notas'),
                       trf.get('notas', 0), trf.get('cabecas', 0.0), trf.get('valor', 0.0))

        out = cat.get('OUTRAS', {})
        self._ir_secao('OUTRAS', '#A78BFA',
                       _linhas('out_valor', 'out_cabecas', 'out_notas'),
                       out.get('notas', 0), out.get('cabecas', 0.0), out.get('valor', 0.0))

        self._ir_secao('TOTAL GERAL', '#9CA3AF',
                       _linhas('valor', 'cabecas', 'notas'),
                       res['total_notas'], res['total_cabecas'], res['total_valor'])

        # Habilita o botão PDF da Planilha IR
        if hasattr(self, 'btn_ir_pdf'):
            self.btn_ir_pdf.configure(state='normal')

    # Descrições de cada modo — exibidas na aba
    _MODO_DESCS = {
        'pipeline': 'Análise em 3 estágios sequenciais: Ollama extrai e cataloga → Gemini aplica critérios legais e calcula IR → Claude revisa e emite o parecer final assinado.',
        'ir':       'Gera tabelas IR mensais (VENDAS / REMESSAS / COMPRAS / TRANSFERÊNCIAS / OUTRAS) conforme Lei 8.023/90, prontas para a declaração de IRPF do Produtor Rural.',
        'ollama':   'Análise consultiva completa via Ollama local — 100% privado, sem enviar dados para a nuvem. Usa o modelo llama3.1:8b.',
        'gemini':   'Análise via Google Gemini 2.5 Pro — janela de contexto gigante, ideal para grandes volumes de notas e relatórios extensos.',
        'claude':   'Análise consultiva sênior via Claude Sonnet — maior profundidade, raciocínio jurídico-tributário e qualidade de redação.',
        'auto':     'Usa automaticamente o melhor provedor disponível na ordem: Claude → Gemini → Ollama → Estatísticas locais.',
    }

    def _build_tab_ia(self):
        tab = self.notebook.tab('Analise IA')

        # ── Painel de Configuração ────────────────────────────────────────
        cfg = ctk.CTkFrame(tab, fg_color=BG2, corner_radius=8,
                           border_color=BORDER, border_width=1)
        cfg.pack(fill='x', padx=10, pady=(8, 0))

        ctk.CTkLabel(cfg, text='  CONFIGURAÇÃO DA ANÁLISE POR IA',
                     font=ctk.CTkFont('Segoe UI', 10, 'bold'),
                     text_color=CYAN, height=28, fg_color=BG3, corner_radius=6,
                     anchor='w').pack(fill='x', padx=0, pady=(0, 8))

        # Linha 1 — Modo (SegmentedButton)
        l1 = ctk.CTkFrame(cfg, fg_color='transparent')
        l1.pack(fill='x', padx=14, pady=(0, 4))
        ctk.CTkLabel(l1, text='Modo:', font=ctk.CTkFont('Segoe UI', 11),
                     text_color=TEXT_DIM, width=52, anchor='w').pack(side='left')
        self.combo_provedor = ctk.CTkSegmentedButton(
            l1,
            values=['pipeline', 'ir', 'ollama', 'gemini', 'claude', 'auto'],
            font=ctk.CTkFont('Segoe UI', 11, 'bold'),
            fg_color=BG3,
            selected_color=PRIMARY, selected_hover_color=CYAN,
            unselected_color=BG3, unselected_hover_color=BG4,
            text_color=TEXT, text_color_disabled=TEXT_DIM,
            command=self._on_provedor_change,
        )
        self.combo_provedor.set('pipeline')
        self.combo_provedor.pack(side='left', padx=(6, 0))

        # Linha 2 — Descrição do modo
        self._lbl_modo_desc = ctk.CTkLabel(
            cfg,
            text=self._MODO_DESCS['pipeline'],
            font=ctk.CTkFont('Segoe UI', 10),
            text_color=TEXT_DIM, wraplength=860, justify='left',
        )
        self._lbl_modo_desc.pack(anchor='w', padx=66, pady=(0, 6))

        # Separador
        ctk.CTkFrame(cfg, fg_color=BORDER, height=1, corner_radius=0
                     ).pack(fill='x', padx=14, pady=(2, 6))

        # Linha 3 — Status das IAs
        l3 = ctk.CTkFrame(cfg, fg_color='transparent')
        l3.pack(fill='x', padx=14, pady=(0, 6))
        ctk.CTkLabel(l3, text='Status:', font=ctk.CTkFont('Segoe UI', 10, 'bold'),
                     text_color=TEXT_DIM, width=52, anchor='w').pack(side='left')
        self._lbl_st_ollama = ctk.CTkLabel(l3, text='● Ollama  —',
                                            font=ctk.CTkFont('Segoe UI', 10),
                                            text_color=TEXT_DIM)
        self._lbl_st_ollama.pack(side='left', padx=(6, 20))
        self._lbl_st_gemini = ctk.CTkLabel(l3, text='● Gemini  —',
                                            font=ctk.CTkFont('Segoe UI', 10),
                                            text_color=TEXT_DIM)
        self._lbl_st_gemini.pack(side='left', padx=(0, 20))
        self._lbl_st_claude = ctk.CTkLabel(l3, text='● Claude  —',
                                            font=ctk.CTkFont('Segoe UI', 10),
                                            text_color=TEXT_DIM)
        self._lbl_st_claude.pack(side='left')

        # Linha 4 — Nome do produtor (apenas modo IR, oculta por padrão)
        self._frame_produtor = ctk.CTkFrame(cfg, fg_color='transparent')
        ctk.CTkLabel(self._frame_produtor, text='Produtor Rural:',
                     font=ctk.CTkFont('Segoe UI', 11), text_color=TEXT_DIM,
                     width=110, anchor='w').pack(side='left')
        self.entry_produtor = ctk.CTkEntry(
            self._frame_produtor,
            placeholder_text='Nome completo do produtor (ex: Genis Carlos Luiz de Oliveira)',
            fg_color=BG, border_color=BORDER, text_color=TEXT,
            font=ctk.CTkFont('Segoe UI', 11), height=32, width=420,
        )
        self.entry_produtor.pack(side='left', padx=(4, 0))

        # ── Painel Visual do Pipeline (apenas modo pipeline) ─────────────
        self._pipeline_panel = ctk.CTkFrame(tab, fg_color=BG2, corner_radius=8,
                                             border_color=BORDER, border_width=1)

        # Cabeçalho do painel
        pl_hdr = ctk.CTkFrame(self._pipeline_panel, fg_color=BG3,
                               corner_radius=0, height=28)
        pl_hdr.pack(fill='x')
        pl_hdr.pack_propagate(False)
        ctk.CTkLabel(pl_hdr, text='  PIPELINE — TRÍPLICE ALIANÇA',
                     font=ctk.CTkFont('Segoe UI', 10, 'bold'),
                     text_color=ORANGE).pack(side='left', pady=5)
        ctk.CTkLabel(pl_hdr, text='Ollama  →  Gemini  →  Claude  ',
                     font=ctk.CTkFont('Segoe UI', 9),
                     text_color=TEXT_DIM).pack(side='right', pady=5)

        # Container dos 3 cards + setas
        pl_body = ctk.CTkFrame(self._pipeline_panel, fg_color='transparent')
        pl_body.pack(fill='x', padx=14, pady=10)

        _STAGES = [
            ('1', 'OLLAMA',  'Extração e Catalogação',  '#F59E0B'),
            ('2', 'GEMINI',  'Critérios Tributários',   '#38BDF8'),
            ('3', 'CLAUDE',  'Revisão e Aprovação',     '#22C55E'),
        ]
        self._pl_cards: list[dict] = []

        for idx, (num, nome, desc, cor) in enumerate(_STAGES):
            if idx > 0:
                # Seta conectora entre estágios
                ctk.CTkLabel(pl_body, text='  ►  ',
                             font=ctk.CTkFont('Segoe UI', 16, 'bold'),
                             text_color=BORDER).pack(side='left', pady=4)

            # Card do estágio
            card = ctk.CTkFrame(pl_body, fg_color=BG, corner_radius=8,
                                border_color=BORDER, border_width=2)
            card.pack(side='left', padx=0, pady=4, fill='y')

            # Badge numérico
            badge = ctk.CTkFrame(card, fg_color=BORDER, corner_radius=4,
                                 width=22, height=22)
            badge.pack_propagate(False)
            badge.pack(anchor='nw', padx=10, pady=(8, 0))
            ctk.CTkLabel(badge, text=num,
                         font=ctk.CTkFont('Segoe UI', 9, 'bold'),
                         text_color=TEXT_DIM).pack(expand=True)

            ctk.CTkLabel(card, text=nome,
                         font=ctk.CTkFont('Segoe UI', 12, 'bold'),
                         text_color=TEXT_DIM).pack(anchor='w', padx=10, pady=(4, 0))
            ctk.CTkLabel(card, text=desc,
                         font=ctk.CTkFont('Segoe UI', 9),
                         text_color=TEXT_DIM).pack(anchor='w', padx=10, pady=(1, 6))

            # Separador interno
            ctk.CTkFrame(card, fg_color=BORDER, height=1).pack(fill='x', padx=10)

            # Status label
            lbl_st = ctk.CTkLabel(card, text='○  Aguardando',
                                   font=ctk.CTkFont('Segoe UI', 10, 'bold'),
                                   text_color=TEXT_DIM)
            lbl_st.pack(anchor='w', padx=10, pady=(5, 10))

            self._pl_cards.append({
                'frame': card, 'lbl_status': lbl_st,
                'cor': cor, 'nome': nome,
            })

        # Painel começa visível (modo padrão é pipeline)
        self._pipeline_panel.pack(fill='x', padx=10, pady=(6, 0))

        # ── Área de Resultado ─────────────────────────────────────────────
        self._res_frame = ctk.CTkFrame(tab, fg_color=BG2, corner_radius=8,
                                       border_color=BORDER, border_width=1)
        self._res_frame.pack(fill='both', expand=True, padx=10, pady=(8, 10))
        res_frame = self._res_frame

        hdr = ctk.CTkFrame(res_frame, fg_color=BG3, corner_radius=0, height=30)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text='  RELATÓRIO GERAL POR IA',
                     font=ctk.CTkFont('Segoe UI', 10, 'bold'),
                     text_color=GREEN).pack(side='left', pady=6)
        self._lbl_modo_ativo = ctk.CTkLabel(hdr, text='',
                                             font=ctk.CTkFont('Segoe UI', 9),
                                             text_color=TEXT_DIM)
        self._lbl_modo_ativo.pack(side='right', padx=14, pady=6)

        self.txt_ia = ctk.CTkTextbox(res_frame, fg_color=BG, text_color=TEXT,
                                      font=ctk.CTkFont('Courier', 11),
                                      corner_radius=0, activate_scrollbars=True,
                                      wrap='word')
        self.txt_ia.pack(fill='both', expand=True)
        self.txt_ia.insert('end', 'Configure o modo acima e clique em "Analisar com IA" para iniciar.\n')
        self.txt_ia.configure(state='disabled')

        # Verifica disponibilidade das IAs em background
        threading.Thread(target=self._verificar_ias, daemon=True).start()

    # ── Ações ────────────────────────────────────────────────────────────────
    def _selecionar_pdf(self):
        path = filedialog.askopenfilename(
            title='Selecionar PDF SEFAZ',
            filetypes=[('PDF', '*.pdf'), ('Todos', '*.*')]
        )
        if path:
            self._pdf_path = path
            nome = Path(path).name
            self.lbl_arquivo.configure(text=nome, text_color=TEXT)
            self.btn_extrair.configure(state='normal')
            self._status(f'Arquivo: {nome}')

    def _extrair(self):
        if not self._pdf_path:
            return
        self.btn_extrair.configure(state='disabled', text='Extraindo...')
        self.btn_pdf.configure(state='disabled')
        self.btn_excel.configure(state='disabled')
        self.btn_ia.configure(state='disabled')
        self.progress.set(0)
        self._status('Extraindo dados do PDF...')

        def worker():
            from extractor import extrair_notas

            def prog(atual, total):
                self.after(0, lambda: self.progress.set(atual / total))
                self.after(0, lambda: self._status(f'Lendo pagina {atual}/{total}...'))

            try:
                notas = extrair_notas(self._pdf_path, callback=prog)
                self.after(0, lambda: self._pos_extracao(notas))
            except Exception as e:
                self.after(0, lambda: self._erro(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _pos_extracao(self, notas):
        self.notas = notas
        self.progress.set(1)
        self._build_cards()
        self._preencher_tabelas()
        self.btn_extrair.configure(state='normal', text='Extrair Dados')
        self.btn_pdf.configure(state='normal')
        self.btn_excel.configure(state='normal')
        self.btn_db.configure(state='normal')
        self.btn_ia.configure(state='normal')
        self.btn_limpar.configure(state='normal')
        self._atualizar_graficos()
        from extractor import resumo_geral
        res = resumo_geral(notas)
        self._atualizar_tab_ir(res)
        self._status(
            f'{len(notas)} notas | '
            f"{res['total_cabecas']:.0f} cabecas | "
            f"R$ {res['total_valor']:,.2f}"
        )

    def _preencher_tabelas(self):
        # Notas
        for item in self.tv_notas.get_children():
            self.tv_notas.delete(item)
        for i, n in enumerate(self.notas):
            tag = ('even' if i%2==0 else 'odd',)
            if 'REMESSA' in n.natureza.upper():
                tag = ('remessa',)
            elif 'VENDA' in n.natureza.upper():
                tag = ('venda',)
            self.tv_notas.insert('', 'end', tags=tag, values=(
                n.numero, n.emissao, n.natureza, n.local_emissao,
                n.destinatario.nome, n.destinatario.cpf_cnpj, n.destinatario.municipio,
                n.transportador.nome,
                f'{n.quantidade_total:.0f}',
                f'{n.valor_total:,.2f}',
                n.chave_acesso,
            ))

        # Itens
        for item in self.tv_itens.get_children():
            self.tv_itens.delete(item)
        row = 0
        for n in self.notas:
            for p in n.produtos:
                tag = ('even' if row%2==0 else 'odd',)
                self.tv_itens.insert('', 'end', tags=tag, values=(
                    n.numero, n.emissao, n.destinatario.nome,
                    p.codigo, p.descricao,
                    f'{p.quantidade:.0f}',
                    f'{p.vlr_unitario:,.4f}',
                    f'{p.vlr_icms:,.2f}',
                    f'{p.vlr_total:,.2f}',
                ))
                row += 1

        # Por Destinatário
        from collections import defaultdict
        from extractor import resumo_geral
        res = resumo_geral(self.notas)
        dest_info: dict = defaultdict(lambda: {'nome':'','cpf':'','mun':''})
        for n in self.notas:
            k = n.destinatario.cpf_cnpj or n.destinatario.nome
            dest_info[k]['nome'] = n.destinatario.nome
            dest_info[k]['cpf']  = n.destinatario.cpf_cnpj
            dest_info[k]['mun']  = n.destinatario.municipio

        for item in self.tv_dest.get_children():
            self.tv_dest.delete(item)
        sorted_dest = sorted(res['top_dest'], key=lambda x: x['valor'], reverse=True)
        for i, d in enumerate(sorted_dest):
            tag = ('even' if i%2==0 else 'odd',)
            info = dest_info.get(d.get('cpf_cnpj','') or d['nome'], {})
            medio = d['valor'] / d['notas'] if d['notas'] else 0
            self.tv_dest.insert('', 'end', tags=tag, values=(
                d['nome'],
                info.get('cpf',''),
                info.get('mun',''),
                d['notas'],
                f"{d['cabecas']:.0f}",
                f"{d['valor']:,.2f}",
                f'{medio:,.2f}',
            ))

    def _set_pipeline_stage(self, stage: int, status: str):
        """Atualiza visual do card do pipeline. stage=1-3, status=pending|running|done|skipped|error."""
        if not hasattr(self, '_pl_cards') or stage < 1 or stage > 3:
            return
        card_data = self._pl_cards[stage - 1]
        frame    = card_data['frame']
        lbl      = card_data['lbl_status']
        cor_card = card_data['cor']

        cfg = {
            'pending':  (BORDER,   TEXT_DIM, '○  Aguardando'),
            'running':  (cor_card, ORANGE,   '◎  Processando...'),
            'done':     (GREEN,    GREEN,    '✓  Concluído'),
            'skipped':  (BORDER,   TEXT_DIM, '—  Ignorado'),
            'error':    (RED,      RED,      '✗  Erro'),
        }.get(status, (BORDER, TEXT_DIM, '○  Aguardando'))

        border_cor, txt_cor, txt = cfg
        frame.configure(border_color=border_cor)
        lbl.configure(text=txt, text_color=txt_cor)

    def _reset_pipeline_cards(self):
        for i in range(1, 4):
            self._set_pipeline_stage(i, 'pending')

    def _verificar_ias(self):
        """Verifica disponibilidade das IAs em thread de background e atualiza labels."""
        from ai_client import _ollama_disponivel, _gemini_disponivel, _claude_disponivel

        checks = [
            (_ollama_disponivel,  self._lbl_st_ollama, 'Ollama',
             'disponível (llama3.1)', 'indisponível'),
            (_gemini_disponivel,  self._lbl_st_gemini, 'Gemini',
             'configurado', 'sem chave API'),
            (_claude_disponivel,  self._lbl_st_claude, 'Claude',
             'configurado', 'sem chave API'),
        ]
        for fn, lbl, nome, txt_ok, txt_fail in checks:
            ok = fn()
            cor  = GREEN  if ok else ORANGE
            icone = '●'   if ok else '○'
            txt  = f'{icone} {nome}  {txt_ok if ok else txt_fail}'
            self.after(0, lambda l=lbl, t=txt, c=cor: l.configure(text=t, text_color=c))

    def _on_provedor_change(self, valor: str):
        self._lbl_modo_desc.configure(text=self._MODO_DESCS.get(valor, ''))
        # Campo produtor — só no modo IR
        if valor == 'ir':
            self._frame_produtor.pack(fill='x', padx=14, pady=(0, 10))
        else:
            self._frame_produtor.pack_forget()
        # Painel pipeline — só no modo pipeline
        if valor == 'pipeline':
            self._pipeline_panel.pack(fill='x', padx=10, pady=(6, 0),
                                      before=self._res_frame)
            self._reset_pipeline_cards()
        else:
            self._pipeline_panel.pack_forget()

    def _analisar_ia(self):
        if not self.notas:
            return
        provedor = self.combo_provedor.get()
        nome_produtor = self.entry_produtor.get().strip() or 'Produtor Rural'
        labels = {
            'pipeline': 'Pipeline  Ollama → Gemini → Claude',
            'ir':       f'Tabelas IR  {nome_produtor}',
            'claude':   'Claude API',
            'gemini':   'Gemini API',
            'ollama':   'Ollama (local)',
            'auto':     'Auto — melhor disponível',
        }
        self.btn_ia.configure(state='disabled', text='Analisando...')
        self._lbl_modo_ativo.configure(
            text=f'Modo: {labels.get(provedor, provedor)}  |  Aguardando...')
        self.txt_ia.configure(state='normal')
        self.txt_ia.delete('1.0', 'end')
        self.txt_ia.insert('end', f'Conectando ao {labels.get(provedor, provedor)}...\n\n')
        self.notebook.set('Analise IA')

        # Reseta cards do pipeline
        if provedor == 'pipeline':
            self._reset_pipeline_cards()

        def worker():
            from ai_client import analisar

            # Detecta marcadores de estágio para atualizar os cards em tempo real
            _estagio_atual = [0]
            _MARCADORES = {
                'ESTÁGIO 1/3': (1, 2, 3),   # inicia 1, mantém 2 e 3 pendentes
                'ESTÁGIO 2/3': (2, 1, None), # conclui 1, inicia 2
                'ESTÁGIO 3/3': (3, 2, None), # conclui 2, inicia 3
            }

            buffer = []
            _acum = []  # acumula tokens para detectar marcadores multi-token

            def on_chunk(token):
                buffer.append(token)
                _acum.append(token)
                # Verifica marcadores de estágio (janela de 80 chars)
                janela = ''.join(_acum[-20:])
                if provedor == 'pipeline':
                    for marcador, (novo, conclui, _) in _MARCADORES.items():
                        if marcador in janela and _estagio_atual[0] != novo:
                            _estagio_atual[0] = novo
                            if conclui and conclui < novo:
                                self.after(0, lambda s=conclui: self._set_pipeline_stage(s, 'done'))
                            self.after(0, lambda s=novo: self._set_pipeline_stage(s, 'running'))
                if len(buffer) >= 5:
                    texto = ''.join(buffer)
                    buffer.clear()
                    self.after(0, lambda t=texto: self._append_ia(t))

            result = analisar(self.notas, callback=on_chunk,
                              provedor=provedor, nome_produtor=nome_produtor)
            if buffer:
                texto = ''.join(buffer)
                self.after(0, lambda t=texto: self._append_ia(t))
            self.analise_texto = result
            self.after(0, self._pos_ia)

        threading.Thread(target=worker, daemon=True).start()

    def _append_ia(self, texto):
        self.txt_ia.configure(state='normal')
        self.txt_ia.insert('end', texto)
        self.txt_ia.see('end')

    def _pos_ia(self):
        self.txt_ia.configure(state='disabled')
        self.btn_ia.configure(state='normal', text='Analisar com IA')
        provedor = self.combo_provedor.get()
        labels = {
            'pipeline': 'Pipeline  Ollama → Gemini → Claude',
            'ir':       'Tabelas IR',
            'claude':   'Claude API', 'gemini': 'Gemini API',
            'ollama':   'Ollama (local)', 'auto':  'Auto',
        }
        self._lbl_modo_ativo.configure(
            text=f'Modo: {labels.get(provedor, provedor)}  |  Concluído ✓')
        # Marca todos os cards do pipeline como concluídos
        if provedor == 'pipeline':
            for i in range(1, 4):
                self._set_pipeline_stage(i, 'done')
        self._status('Análise IA concluída.')

    def _gerar_pdf(self):
        if not self.notas:
            return
        sugestao = Path(self._pdf_path).stem + '_relatorio.pdf' if self._pdf_path else 'relatorio_nfa.pdf'
        saida = filedialog.asksaveasfilename(
            title='Salvar relatorio PDF',
            defaultextension='.pdf',
            filetypes=[('PDF', '*.pdf')],
            initialfile=sugestao,
        )
        if not saida:
            return
        self.btn_pdf.configure(state='disabled', text='Gerando...')
        self._status('Gerando PDF...')

        def worker():
            from pdf_report import gerar_pdf
            try:
                gerar_pdf(self.notas, saida, self.analise_texto)
                self.after(0, lambda: self._pdf_ok(saida))
            except Exception as e:
                self.after(0, lambda: self._erro(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _pdf_ok(self, saida):
        self.btn_pdf.configure(state='normal', text='Gerar PDF')
        self._status(f'PDF salvo: {Path(saida).name}')
        if messagebox.askyesno('PDF gerado', f'PDF salvo com sucesso!\n\n{saida}\n\nAbrir agora?'):
            os.startfile(saida)

    # ── Exportação PDF — Planilha IR ─────────────────────────────────────────
    def _exportar_pdf_ir(self):
        if not self.notas:
            return
        sugestao = Path(self._pdf_path).stem + '_planilha_ir.pdf' if self._pdf_path else 'planilha_gado_ir.pdf'
        saida = filedialog.asksaveasfilename(
            title='Salvar Planilha IR — PDF',
            defaultextension='.pdf',
            filetypes=[('PDF', '*.pdf')],
            initialfile=sugestao,
        )
        if not saida:
            return
        self.btn_ir_pdf.configure(state='disabled', text='Gerando...')
        self._status('Gerando Planilha IR em PDF...')

        def worker():
            from ir_report import gerar_pdf_ir
            try:
                gerar_pdf_ir(self.notas, saida)
                self.after(0, lambda: self._ir_pdf_ok(saida))
            except Exception as e:
                self.after(0, lambda: self._erro(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _ir_pdf_ok(self, saida):
        self.btn_ir_pdf.configure(state='normal', text='⬇  Exportar PDF — Planilha IR')
        self._status(f'Planilha IR salva: {Path(saida).name}')
        if messagebox.askyesno('Planilha IR gerada',
                               f'PDF da Planilha IR salvo!\n\n{saida}\n\nAbrir agora?'):
            os.startfile(saida)

    def _exportar_excel(self):
        if not self.notas:
            return
        sugestao = Path(self._pdf_path).stem + '_dados.xlsx' if self._pdf_path else 'dados_nfa.xlsx'
        saida = filedialog.asksaveasfilename(
            title='Salvar Excel',
            defaultextension='.xlsx',
            filetypes=[('Excel', '*.xlsx')],
            initialfile=sugestao,
        )
        if not saida:
            return
        self.btn_excel.configure(state='disabled', text='Exportando...')
        self._status('Gerando Excel...')

        def worker():
            from excel_export import exportar_excel
            try:
                exportar_excel(self.notas, saida)
                self.after(0, lambda: self._excel_ok(saida))
            except Exception as e:
                self.after(0, lambda: self._erro(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _excel_ok(self, saida):
        self.btn_excel.configure(state='normal', text='Exportar Excel')
        self._status(f'Excel salvo: {Path(saida).name}')
        if messagebox.askyesno('Excel gerado', f'Excel salvo!\n\n{saida}\n\nAbrir agora?'):
            os.startfile(saida)

    def _salvar_postgres(self):
        if not self.notas:
            return
            
        self.btn_db.configure(state='disabled', text='Salvando BD...')
        self._status('Conectando ao PostgreSQL...')

        def worker():
            try:
                from database import criar_tabelas, salvar_notas_bd
                criar_tabelas()
                salvas, ignoradas = salvar_notas_bd(self.notas)
                self.after(0, lambda s=salvas, i=ignoradas: self._bd_ok(s, i))
            except Exception as e:
                self.after(0, lambda err=str(e): self._bd_erro(err))

        threading.Thread(target=worker, daemon=True).start()

    def _bd_ok(self, salvas, ignoradas):
        self.btn_db.configure(state='normal', text='Salvar no BD')
        msg = f"Injeção no PostgreSQL concluída!\n\n✅ Novas Notas Salvas: {salvas}\n⏭️ Notas Ignoradas (Já existiam): {ignoradas}"
        self._status(f'Salvo no BD: {salvas} notas inseridas.')
        messagebox.showinfo('Banco de Dados', msg)
        
    def _bd_erro(self, err):
        self.btn_db.configure(state='normal', text='Salvar no BD')
        self._status(f'Erro no Banco de Dados: {err}')
        messagebox.showerror('Erro Conexão', err)

    def _limpar_dados(self):
        if not messagebox.askyesno('Limpar Dados', 'Deseja limpar todos os dados carregados?'):
            return
        self.notas = []
        self.analise_texto = ''
        self._pdf_path = ''

        # Reseta label do arquivo
        self.lbl_arquivo.configure(text='Nenhum arquivo selecionado', text_color=TEXT_DIM)

        # Limpa tabelas
        for tv in (self.tv_notas, self.tv_itens, self.tv_dest):
            tv.delete(*tv.get_children())

        # Limpa textbox IA e reseta indicadores
        self.txt_ia.configure(state='normal')
        self.txt_ia.delete('1.0', 'end')
        self.txt_ia.insert('end', 'Configure o modo acima e clique em "Analisar com IA" para iniciar.\n')
        self.txt_ia.configure(state='disabled')
        if hasattr(self, '_lbl_modo_ativo'):
            self._lbl_modo_ativo.configure(text='')

        # Reseta cards
        self._build_cards()

        # Reseta gráficos
        for w in self._graf_frame.winfo_children():
            w.destroy()
        self._graf_canvas_widgets.clear()
        ctk.CTkLabel(self._graf_frame,
                     text='Extraia os dados para visualizar os gráficos.',
                     font=ctk.CTkFont('Segoe UI', 11), text_color=TEXT_DIM
                     ).pack(pady=40)

        # Reseta aba IR
        for w in self._ir_scroll.winfo_children():
            w.destroy()
        ctk.CTkLabel(self._ir_scroll,
                     text='Extraia os dados para visualizar a Tabela IR.',
                     font=ctk.CTkFont('Segoe UI', 11), text_color=TEXT_DIM
                     ).pack(pady=40)

        # Reseta barra de progresso
        self.progress.set(0)

        # Desabilita botões de ação
        self.btn_extrair.configure(state='disabled')
        self.btn_ia.configure(state='disabled')
        self.btn_excel.configure(state='disabled')
        self.btn_db.configure(state='disabled')
        self.btn_pdf.configure(state='disabled')
        if hasattr(self, 'btn_ir_pdf'):
            self.btn_ir_pdf.configure(state='disabled', text='⬇  Exportar PDF — Planilha IR')
        self.btn_limpar.configure(state='disabled')

        self._status('Dados limpos. Selecione um novo arquivo PDF.')

    def _status(self, msg: str):
        self.lbl_status.configure(text=msg)

    def _erro(self, msg: str):
        self.btn_extrair.configure(state='normal', text='Extrair Dados')
        self.btn_pdf.configure(state='normal')
        self.btn_excel.configure(state='normal')
        self.btn_db.configure(state='normal')
        self.btn_ia.configure(state='normal', text='Analisar com IA')
        self._status(f'Erro: {msg}')
        messagebox.showerror('Erro', msg)


# ── Entry point ──────────────────────────────────────────────────────────────
if __name__ == '__main__':
    app = App()
    app.mainloop()
