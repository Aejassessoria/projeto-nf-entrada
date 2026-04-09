import streamlit as st
import pandas as pd
import re
import os, sys
import unicodedata
import io, contextlib

sys.path.insert(0, os.path.dirname(__file__))

from src.database_pg import (inicializar_banco, salvar_regra_ncm,
                           listar_regras_ncm, deletar_regra_ncm, get_connection,
                           buscar_todas_regras_ncm, buscar_historico_cliente,
                           salvar_classificacoes_batch, deletar_historico_item,
                           listar_historico_itens, deletar_cache_cliente)
from src.reader import ler_planilha_sat, listar_clientes
from src.receita_federal import consultar_cnpj, consultar_cnpjs_batch, formatar_cnpj, consultar_ncm
from src.classifier import (classificar_planilha, resumo_classificacao,
                             RESULTADO_IMOBILIZADO, RESULTADO_USO_CONSUMO,
                             RESULTADO_REVENDA, RESULTADO_INCERTO)

def _ascii(txt):
    """Remove acentos para compatibilidade com fontes built-in do fpdf2."""
    return unicodedata.normalize('NFKD', str(txt)).encode('latin-1', 'replace').decode('latin-1')


def gerar_pdf_relatorio(df: pd.DataFrame, nome_empresa: str) -> bytes:
    from fpdf import FPDF, XPos, YPos

    COLS = [c for c in ['_hist', 'numero_nf', 'data_emissao', 'ncm', 'cfop',
                         'descricao_produto', 'quantidade', 'unidade',
                         'valor_unitario', 'valor_total',
                         'icms_tributacao', 'origem', 'icms_bc', 'icms_aliq', 'icms_valor',
                         'classificacao'] if c in df.columns]
    LABELS = {
        '_hist': 'Historico', 'numero_nf': 'NF', 'data_emissao': 'Data',
        'ncm': 'NCM', 'cfop': 'CFOP', 'descricao_produto': 'Descricao',
        'quantidade': 'Qtd', 'unidade': 'Un',
        'valor_unitario': 'Vl Unit', 'valor_total': 'Vl Total',
        'icms_tributacao': 'Trib.ICMS', 'origem': 'Origem',
        'icms_bc': 'BC ICMS', 'icms_aliq': 'Aliq%', 'icms_valor': 'Vl ICMS',
        'classificacao': 'Classificacao',
    }
    WIDTHS = {
        '_hist': 13, 'numero_nf': 18, 'data_emissao': 16,
        'ncm': 20, 'cfop': 12, 'descricao_produto': 55,
        'quantidade': 12, 'unidade': 9,
        'valor_unitario': 20, 'valor_total': 20,
        'icms_tributacao': 16, 'origem': 12,
        'icms_bc': 18, 'icms_aliq': 12, 'icms_valor': 18,
        'classificacao': 24,
    }

    df_pdf = df[COLS].copy()
    if 'classificacao' in df_pdf.columns:
        df_pdf = df_pdf.sort_values('classificacao', kind='stable')
    if '_hist' in df_pdf.columns:
        df_pdf['_hist'] = df_pdf['_hist'].apply(
            lambda x: 'SIM' if 'Com' in str(x) else 'NAO')

    widths = [WIDTHS[c] for c in COLS]

    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=False)
    pdf.set_margins(8, 8, 8)

    def draw_title():
        pdf.set_font('Helvetica', 'B', 13)
        pdf.cell(0, 7, _ascii(f'Classificacao de NF Entrada - {nome_empresa}'),
                 align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font('Helvetica', '', 8)
        pdf.cell(0, 5, f'Gerado em: {pd.Timestamp.now().strftime("%d/%m/%Y %H:%M")}',
                 align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(2)

    def draw_col_header():
        pdf.set_fill_color(50, 80, 120)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font('Helvetica', 'B', 6.5)
        for c, w in zip(COLS, widths):
            pdf.cell(w, 5.5, LABELS[c], border=1, align='C', fill=True)
        pdf.ln()
        pdf.set_text_color(0, 0, 0)

    def draw_cfop_header(classificacao):
        pdf.set_fill_color(210, 225, 245)
        pdf.set_font('Helvetica', 'B', 8)
        pdf.cell(0, 6, f'  Classificacao: {_ascii(classificacao)}', border=1, fill=True,
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.add_page()
    draw_title()

    current_group = None
    fill = False

    for _, row in df_pdf.iterrows():
        group = str(row.get('classificacao', '') or '')

        if group != current_group:
            if pdf.get_y() > pdf.h - pdf.b_margin - 22:
                pdf.add_page()
                draw_title()
            if current_group is not None:
                pdf.ln(2)
            current_group = group
            draw_cfop_header(group)
            draw_col_header()
            fill = False

        if pdf.get_y() > pdf.h - pdf.b_margin - 7:
            pdf.add_page()
            draw_title()
            draw_cfop_header(group)
            draw_col_header()
            fill = False

        if fill:
            pdf.set_fill_color(240, 245, 255)
        else:
            pdf.set_fill_color(255, 255, 255)
        fill = not fill
        pdf.set_font('Helvetica', '', 6.5)

        for c, w in zip(COLS, widths):
            val = row.get(c, '') or ''
            if c in ('valor_unitario', 'valor_total', 'icms_bc', 'icms_valor'):
                try:
                    txt = f"R$ {float(val):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                except (ValueError, TypeError):
                    txt = str(val)
            elif c == 'icms_aliq':
                try:
                    txt = f"{float(val):,.2f}%".replace(',', 'X').replace('.', ',').replace('X', '.')
                except (ValueError, TypeError):
                    txt = str(val)
            elif c == 'quantidade':
                try:
                    v = float(val)
                    txt = str(int(v)) if v == int(v) else f"{v:,.2f}"
                except (ValueError, TypeError):
                    txt = str(val)
            elif c == 'descricao_produto':
                txt = str(val)[:55]
            else:
                txt = str(val)
            pdf.cell(w, 5, _ascii(txt), border=1, fill=True)
        pdf.ln()

    return bytes(pdf.output())


inicializar_banco()

st.set_page_config(page_title="Classificador NF Entrada", layout="wide", page_icon="📋")

COR = {
    RESULTADO_IMOBILIZADO: '🔵',
    RESULTADO_USO_CONSUMO: '🟢',
    RESULTADO_REVENDA:     '🟡',
    RESULTADO_INCERTO:     '🔴',
}

with st.sidebar:
    st.title("📋 NF Entrada")
    pagina = st.radio("Menu", ["Classificar Notas", "Regras por NCM", "Histórico"],
                      label_visibility="collapsed")
    st.divider()
    usuario_logado = st.text_input("👤 Seu nome", key="usuario_logado",
                                   placeholder="Informe seu nome...",
                                   help="Será registrado junto ao histórico de classificações")

# ══════════════════════════════════════════════════════════════════════════════
# PÁGINA 1 — Classificar Notas
# ══════════════════════════════════════════════════════════════════════════════
if pagina == "Classificar Notas":
    st.title("Classificação de Notas de Entrada")
    st.caption("Carregue a planilha de itens exportada do SAT")

    if not usuario_logado:
        st.warning("⚠️ Informe seu nome na barra lateral antes de carregar a planilha.")
        st.stop()

    arquivo = st.file_uploader("Planilha SAT (Itens)", type=['xlsx', 'xls'])

    if arquivo is None and 'df_raw' in st.session_state:
        st.info(f"📋 Planilha em uso: **{st.session_state.get('arquivo_carregado', '')}** — carregue outra para substituir.")

    if arquivo or 'df_raw' in st.session_state:
        try:
            arquivo_nome = arquivo.name if arquivo is not None else None
            # Usa cache da sessão para não reler o arquivo ao mudar de cliente
            if arquivo_nome and st.session_state.get('arquivo_carregado') != arquivo_nome:
                with st.spinner("Lendo planilha..."):
                    df_raw = ler_planilha_sat(arquivo)
                    clientes = listar_clientes(df_raw)

                # Consulta CNAE de todos os clientes de uma vez (só na carga)
                with st.spinner(f"Consultando {len(clientes)} clientes na Receita Federal..."):
                    cnpjs_lista = [c.get('cnpj_destinatario', '') for c in clientes if c.get('cnpj_destinatario', '')]
                    cache_info = consultar_cnpjs_batch(cnpjs_lista)

                st.session_state['df_raw'] = df_raw
                st.session_state['clientes'] = clientes
                st.session_state['cache_info'] = cache_info
                st.session_state['arquivo_carregado'] = arquivo_nome
                st.session_state.pop('df_classificado', None)
                st.session_state.pop('relatorio_liberado', None)
                st.session_state.pop('cliente_ativo', None)

            df_raw = st.session_state['df_raw']
            clientes = st.session_state['clientes']
            cache_info = st.session_state['cache_info']

            st.success(f"Planilha carregada: **{len(df_raw)} itens** | **{len(clientes)} empresa(s) compradora(s)**")

            # Lista empresas encontradas na planilha
            opcoes = {}
            for c in clientes:
                cnpj = c.get('cnpj_destinatario', '')
                nome_planilha = c.get('nome_destinatario', '')
                info = cache_info.get(cnpj, {})
                nome_receita = info.get('razao_social', '') if info else ''
                nome = nome_receita or nome_planilha or cnpj
                itens_empresa = len(df_raw[df_raw['cnpj_destinatario'] == cnpj]) if 'cnpj_destinatario' in df_raw.columns else 0
                opcoes[f"{nome} ({formatar_cnpj(cnpj)})"] = cnpj
                st.markdown(f"🏢 **{nome}** — CNPJ: `{formatar_cnpj(cnpj)}` — {itens_empresa} itens")

            st.divider()
            cliente_sel = st.selectbox("Selecione a empresa para classificar", list(opcoes.keys()))
            cnpj_cliente = opcoes[cliente_sel]
            info_cliente = cache_info.get(cnpj_cliente)

            if info_cliente:
                cnaes_sec = info_cliente.get('cnaes_secundarios') or []
                cnaes_sec_det = info_cliente.get('cnaes_secundarios_detalhados') or []
                cnaes_sec_str = f" | +{len(cnaes_sec)} CNAE(s) secundário(s)" if cnaes_sec else ""
                ci1, ci2 = st.columns([5, 1])
                ci1.info(f"**{info_cliente['razao_social']}** | CNAE principal: `{info_cliente['cnae']}` — {info_cliente['descricao_cnae']}{cnaes_sec_str}")
                if ci2.button("🔄 Atualizar dados", key="btn_atualizar_cliente",
                               help="Busca novamente os CNAEs na Receita Federal"):
                    deletar_cache_cliente(cnpj_cliente)
                    with st.spinner("Consultando Receita Federal..."):
                        novo_info = consultar_cnpj(cnpj_cliente)
                    if novo_info:
                        st.session_state['cache_info'][cnpj_cliente] = novo_info
                        # Força reclassificação com novos CNAEs
                        st.session_state.pop('df_classificado', None)
                        st.session_state.pop('cliente_ativo', None)
                    st.rerun()

                with st.expander("🏭 Ver todos os CNAEs desta empresa"):
                    st.markdown(f"**Principal:** `{info_cliente['cnae']}` — {info_cliente['descricao_cnae']}")
                    if cnaes_sec_det:
                        st.markdown("**Secundários:**")
                        for c in cnaes_sec_det:
                            st.markdown(f"- `{c['codigo']}` — {c['descricao']}")
                    elif cnaes_sec:
                        st.markdown("**Secundários:**")
                        for cod in cnaes_sec:
                            st.markdown(f"- `{cod}`")
                    else:
                        st.caption("Nenhum CNAE secundário encontrado para esta empresa.")

                cnae_cliente = info_cliente['cnae']
                desc_cnae_cliente = info_cliente.get('descricao_cnae', '')
                cnaes_secundarios_cliente = cnaes_sec
            else:
                st.warning("Não foi possível consultar o CNAE deste cliente.")
                cnae_cliente = ''
                desc_cnae_cliente = ''
                cnaes_secundarios_cliente = []

            # Filtra itens do cliente selecionado
            if 'cnpj_destinatario' in df_raw.columns:
                df_cliente = df_raw[df_raw['cnpj_destinatario'] == cnpj_cliente].copy()
            else:
                df_cliente = df_raw.copy()

            st.caption(f"{len(df_cliente)} itens encontrados para este cliente")
            st.divider()

            # Classifica apenas quando muda de cliente (não a cada interação)
            if 'df_classificado' not in st.session_state or st.session_state.get('cliente_ativo') != cnpj_cliente:
                with st.spinner("Classificando itens..."):
                    regras_ncm = buscar_todas_regras_ncm()
                    historico_ncm = buscar_historico_cliente(cnpj_cliente)
                    df = classificar_planilha(df_cliente, cnpj_cliente, cnae_cliente, desc_cnae_cliente,
                                              cnaes_secundarios=cnaes_secundarios_cliente,
                                              regras_ncm=regras_ncm, historico_ncm=historico_ncm)
                st.session_state['df_classificado'] = df.copy()
                st.session_state['historico_ncm_ativo'] = set(historico_ncm.keys())
                st.session_state['historico_ncm_dict'] = historico_ncm
                st.session_state['cliente_ativo'] = cnpj_cliente
                st.session_state.pop('relatorio_liberado', None)
                st.session_state.pop(f"opcoes_pesquisa_{cnpj_cliente}", None)
            else:
                df = st.session_state['df_classificado']
                # Remove _sel legado se existir
                if '_sel' in df.columns:
                    df = df.drop(columns=['_sel'])
                    st.session_state['df_classificado'] = df.copy()

            resumo = resumo_classificacao(df)

            OPCOES_CLASS = [RESULTADO_IMOBILIZADO, RESULTADO_USO_CONSUMO, RESULTADO_REVENDA, RESULTADO_INCERTO]

            # Indicador de histórico — NCMs já classificados anteriormente para este cliente
            hist_ncms = st.session_state.get('historico_ncm_ativo', set())
            df['_hist'] = df['ncm'].apply(lambda x: '✅ Com histórico' if x in hist_ncms else '🆕 Sem histórico')

            st.subheader("Resultado da classificação")

            # Resumo histórico x novos
            n_com_hist = int((df['_hist'] == '✅ Com histórico').sum())
            n_sem_hist = int((df['_hist'] == '🆕 Sem histórico').sum())
            mh1, mh2 = st.columns(2)
            mh1.success(f"✅ **{n_com_hist}** item(ns) com histórico — classificação aplicada automaticamente")
            mh2.warning(f"🆕 **{n_sem_hist}** item(ns) sem histórico — revisar e confirmar")

            # ── Alteração em lote + painel de detalhe ─────────────────────
            with st.expander("✏️ Alterar classificação em lote"):
                st.caption("Clique nas linhas para selecionar (Ctrl ou Shift para múltiplas). Depois escolha a classificação e aplique.")

                bulk_col1, bulk_col2 = st.columns([3, 1])

                with bulk_col1:
                    cols_bulk = [c for c in ['numero_nf', 'cnpj_emitente', 'nome_emitente', 'ncm', 'cfop', 'descricao_produto', 'quantidade', 'valor_unitario', 'valor_total', 'classificacao'] if c in df.columns]
                    df_bulk_view = df[cols_bulk + ['_hist']].copy() if '_hist' in df.columns else df[cols_bulk].copy()

                    bulk_ver = st.session_state.get('bulk_sel_version', 0)
                    evento_bulk = st.dataframe(
                        df_bulk_view,
                        use_container_width=True,
                        height=520,
                        on_select="rerun",
                        selection_mode="multi-row",
                        key=f"bulk_df_sel_{bulk_ver}",
                        column_config={
                            "numero_nf": st.column_config.TextColumn("NF", width="small"),
                            "cnpj_emitente": st.column_config.TextColumn("CNPJ Fornecedor", width="medium"),
                            "nome_emitente": st.column_config.TextColumn("Fornecedor", width="large"),
                            "ncm": st.column_config.TextColumn("NCM", width="small"),
                            "cfop": st.column_config.TextColumn("CFOP", width="small"),
                            "descricao_produto": st.column_config.TextColumn("Descrição", width="large"),
                            "quantidade": st.column_config.NumberColumn("Qtd", width="small"),
                            "valor_unitario": st.column_config.NumberColumn("Vl Unit", format="R$ %.2f", width="small"),
                            "valor_total": st.column_config.NumberColumn("Vl Total", format="R$ %.2f", width="small"),
                            "classificacao": st.column_config.TextColumn("Classificação Atual", width="medium"),
                            "_hist": st.column_config.TextColumn("Histórico", width="medium"),
                        },
                    )

                    linhas_sel = evento_bulk.selection.rows
                    n_bulk = len(linhas_sel)

                    # Armazena índices pendentes para o callback (executa antes do rerun)
                    linhas_sel_validas = [i for i in linhas_sel if i is not None and isinstance(i, int)]
                    st.session_state['_bulk_indices_pending'] = df_bulk_view.index[linhas_sel_validas].tolist()

                    def _aplicar_bulk():
                        _df = st.session_state.get('df_classificado')
                        _indices = st.session_state.get('_bulk_indices_pending', [])
                        _nova_class = st.session_state.get('bulk_nova_class', '')
                        if _df is not None and _indices:
                            _df.loc[_indices, 'classificacao'] = _nova_class
                            st.session_state['df_classificado'] = _df.copy()

                    def _limpar_bulk():
                        st.session_state['bulk_sel_version'] = st.session_state.get('bulk_sel_version', 0) + 1

                    bg1, bg2, bg3 = st.columns([3, 1, 1])
                    with bg1:
                        nova_class_bulk = st.selectbox(
                            f"Classificar {n_bulk} item(ns) selecionado(s) como:",
                            OPCOES_CLASS, key="bulk_nova_class",
                            disabled=(n_bulk == 0),
                        )
                    with bg2:
                        st.write("")
                        st.button(f"✅ Aplicar ({n_bulk})", type="primary", key="btn_bulk",
                                  disabled=(n_bulk == 0), on_click=_aplicar_bulk)
                    with bg3:
                        st.write("")
                        st.button("🗑 Limpar seleção", key="btn_bulk_clear",
                                  disabled=(n_bulk == 0), on_click=_limpar_bulk)

                with bulk_col2:
                    st.markdown("**🔍 O que é este item?**")

                    cache_key = f"opcoes_pesquisa_{cnpj_cliente}"
                    if cache_key not in st.session_state:
                        opcoes_pesquisa = {}
                        for idx, row in df.iterrows():
                            desc_op = str(row.get('descricao_produto', '') or '')[:50]
                            ncm_op = str(row.get('ncm', '') or '')
                            chave = desc_op if desc_op else f"NCM {ncm_op}"
                            opcoes_pesquisa[chave] = (idx, ncm_op)
                        st.session_state[cache_key] = opcoes_pesquisa
                    else:
                        opcoes_pesquisa = st.session_state[cache_key]

                    if opcoes_pesquisa:
                        busca = st.text_input("Buscar item", key="pesquisa_texto", placeholder="Digite parte do nome...", label_visibility="collapsed")
                        todas_opcoes = list(opcoes_pesquisa.keys())
                        opcoes_filtradas = [o for o in todas_opcoes if busca.upper() in o.upper()] if busca else todas_opcoes

                        if opcoes_filtradas:
                            item_sel = st.selectbox("Item", opcoes_filtradas, key="pesquisa_item_sel", label_visibility="collapsed")
                            item_idx, ncm_pesquisa = opcoes_pesquisa[item_sel]
                            item_row = df.loc[item_idx]

                            desc_pesquisa = str(item_row.get('descricao_produto', '') or '')
                            valor_item = float(item_row.get('valor_total', 0) or 0)
                            fornecedor = str(item_row.get('nome_emitente', '') or '')
                            classif_atual = str(item_row.get('classificacao', '') or '')
                            cor_class = {'IMOBILIZADO': '🔵', 'USO E CONSUMO': '🟢', 'REVENDA': '🟡', 'INCERTO': '🔴'}.get(classif_atual, '⚪')

                            cache_ncm = st.session_state.setdefault('cache_desc_ncm', {})
                            if ncm_pesquisa and ncm_pesquisa not in cache_ncm:
                                with st.spinner("Consultando..."):
                                    info_ncm = consultar_ncm(ncm_pesquisa)
                                    cache_ncm[ncm_pesquisa] = info_ncm.get('descricao', '') if info_ncm else ''

                            desc_oficial = cache_ncm.get(ncm_pesquisa, '')

                            st.markdown(f"**{cor_class} {desc_pesquisa}**")
                            st.caption(f"NCM: {ncm_pesquisa} | R$ {valor_item:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
                            st.caption(f"Fornecedor: {fornecedor[:40]}")
                            if desc_oficial:
                                st.info(desc_oficial)
                            else:
                                st.caption("Descrição oficial não encontrada.")
                            st.markdown(f"{cor_class} `{classif_atual}`")
                        else:
                            st.caption("Nenhum item encontrado.")

            # Atualiza métricas
            c1, c2, c3, c4, c5, c6 = st.columns(6)
            c1.metric("Total", resumo['total'])
            c2.metric("🔵 Imobilizado", resumo['imobilizado'])
            c3.metric("🟢 Uso e Consumo", resumo['uso_consumo'])
            c4.metric("🟡 Revenda", resumo['revenda'])
            c5.metric("🔴 Incertos", resumo['incerto'])
            c6.metric("✅ Classificados", f"{resumo['automatizado_pct']}%")

            # Confirmar e salvar
            st.divider()
            if not usuario_logado:
                st.warning("⚠️ Informe seu nome na barra lateral antes de salvar.")
            if st.button("✅ Confirmar e salvar histórico", type="primary", disabled=not usuario_logado):
                nome_dest = info_cliente['razao_social'] if info_cliente else ''
                historico_dict = st.session_state.get('historico_ncm_dict', {})
                tuplas = [
                    (
                        cnpj_cliente,
                        nome_dest,
                        str(row.get('cnpj_emitente', '')),
                        str(row.get('nome_emitente', '')),
                        str(row.get('numero_nf', '')),
                        str(row.get('ncm', '')),
                        str(row.get('cfop', '')),
                        str(row.get('descricao_produto', '')),
                        float(row.get('valor_total', 0) or 0),
                        row['classificacao'],
                        int(row['classificacao'] != RESULTADO_INCERTO),
                        usuario_logado,
                    )
                    for _, row in df.iterrows()
                ]
                salvar_classificacoes_batch(tuplas)
                # Atualiza o indicador de histórico com os NCMs recém-salvos
                ncms_salvos = {str(row.get('ncm', '')) for _, row in df.iterrows()}
                st.session_state['historico_ncm_ativo'] = st.session_state.get('historico_ncm_ativo', set()) | ncms_salvos
                st.session_state['relatorio_liberado'] = True
                st.success(f"Histórico atualizado por **{usuario_logado}**! Itens novos foram inseridos; reclassificados foram atualizados; sem alteração foram mantidos com data original.")

            # Exportar — só aparece após confirmar e salvar
            if st.session_state.get('relatorio_liberado'):
                st.divider()
                st.markdown("**⬇️ Baixar relatório**")
                nome_dest_arquivo = info_cliente['razao_social'].replace(' ', '_') if info_cliente else cnpj_cliente

                cols_exp = [c for c in [
                    '_hist', 'numero_nf', 'data_emissao',
                    'cnpj_emitente', 'nome_emitente',
                    'ncm', 'cfop',
                    'descricao_produto', 'quantidade', 'unidade',
                    'valor_unitario', 'valor_total',
                    'icms_tributacao', 'origem', 'icms_bc', 'icms_aliq', 'icms_valor',
                    'classificacao'
                ] if c in df.columns]
                df_exp = df[cols_exp].copy()
                if '_hist' in df_exp.columns:
                    df_exp = df_exp.rename(columns={'_hist': 'historico'})
                df_exp = df_exp.sort_values('classificacao', kind='stable') if 'classificacao' in df_exp.columns else df_exp

                # Formata CNPJs com máscara para evitar notação científica no Excel
                def _fmt_cnpj(v):
                    c = re.sub(r'\D', '', str(v)) if pd.notna(v) else ''
                    if len(c) == 14:
                        return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"
                    return v
                for col_cnpj in ['cnpj_emitente', 'cnpj_destinatario']:
                    if col_cnpj in df_exp.columns:
                        df_exp[col_cnpj] = df_exp[col_cnpj].apply(_fmt_cnpj)

                csv = df_exp.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')

                nome_empresa_pdf = info_cliente['razao_social'] if info_cliente else cnpj_cliente
                _class_hash = hash(tuple(df['classificacao'].tolist())) if 'classificacao' in df.columns else 0
                pdf_cache_key = f"pdf_{cnpj_cliente}_{len(df)}_{_class_hash}"
                if pdf_cache_key not in st.session_state:
                    _buf = io.StringIO()
                    with contextlib.redirect_stdout(_buf), contextlib.redirect_stderr(_buf):
                        st.session_state[pdf_cache_key] = gerar_pdf_relatorio(df, nome_empresa_pdf)
                pdf_bytes = st.session_state[pdf_cache_key]

                dl1, dl2 = st.columns(2)
                dl1.download_button("⬇️ Baixar relatório (.csv)", csv,
                                    f"classificacao_{nome_dest_arquivo}.csv", "text/csv")
                dl2.download_button("⬇️ Baixar relatório (.pdf)", pdf_bytes,
                                    f"classificacao_{nome_dest_arquivo}.pdf", "application/pdf")

        except ValueError as e:
            st.error(f"Erro ao processar planilha: {e}")
        except Exception as e:
            st.error(f"Erro inesperado: {e}")
            raise

# ══════════════════════════════════════════════════════════════════════════════
# PÁGINA 2 — Regras por NCM
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "Regras por NCM":
    st.title("Regras por NCM")
    st.caption("Defina como um NCM deve ser classificado — globalmente ou para uma empresa específica.")

    # Carrega empresas com histórico + empresas já consultadas (cache clientes)
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT cnpj, razao_social FROM (
                SELECT DISTINCT c.cnpj_destinatario AS cnpj,
                       COALESCE(cl.razao_social, c.nome_destinatario, c.cnpj_destinatario) AS razao_social
                FROM classificacoes c
                LEFT JOIN clientes cl ON cl.cnpj = c.cnpj_destinatario
                WHERE c.cnpj_destinatario IS NOT NULL AND c.cnpj_destinatario != ''
                UNION
                SELECT cnpj, razao_social FROM clientes
                WHERE cnpj IS NOT NULL AND cnpj != ''
            ) t
            ORDER BY razao_social
        """)
        clientes_regra_rows = cur.fetchall()
    finally:
        conn.close()
    opcoes_empresa = {'Todas as empresas (global)': ''}
    for r in clientes_regra_rows:
        nome = r['razao_social'] or r['cnpj']
        opcoes_empresa[f"{nome} ({formatar_cnpj(r['cnpj'])})"] = r['cnpj']
    opcoes_empresa['✏️ Digitar CNPJ manualmente...'] = '__manual__'

    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("Adicionar regra")
        ncm_novo = st.text_input("NCM (código completo ou 2 primeiros dígitos)", placeholder="Ex: 90022010 ou 90")
        empresa_sel = st.selectbox("Aplicar a", list(opcoes_empresa.keys()), key="regra_empresa")
        cnpj_regra = opcoes_empresa[empresa_sel]

        if cnpj_regra == '__manual__':
            cnpj_digitado = st.text_input("CNPJ da empresa", placeholder="00.000.000/0000-00", max_chars=18, key="cnpj_manual_regra")
            cnpj_limpo = re.sub(r'\D', '', cnpj_digitado)
            if len(cnpj_limpo) == 14:
                with st.spinner("Consultando empresa..."):
                    from src.database_pg import buscar_cliente as _buscar_cliente
                    info = _buscar_cliente(cnpj_limpo) or consultar_cnpj(cnpj_limpo)
                nome_exibir = info.get('razao_social', cnpj_limpo) if info else cnpj_limpo
                st.caption(f"Empresa: **{nome_exibir}**")
                cnpj_regra = cnpj_limpo
            else:
                if cnpj_digitado:
                    st.caption("Digite os 14 dígitos do CNPJ.")
                cnpj_regra = None

        class_nova = st.selectbox("Classificação", [RESULTADO_IMOBILIZADO, RESULTADO_USO_CONSUMO, RESULTADO_REVENDA])
        desc_nova = st.text_input("Descrição", placeholder="Ex: Câmeras e lentes ópticas")
        if st.button("Salvar regra", type="primary", disabled=(cnpj_regra is None)):
            if ncm_novo.strip():
                salvar_regra_ncm(ncm_novo.strip(), class_nova, desc_nova.strip(), cnpj_regra or '')
                alvo = empresa_sel if cnpj_regra else "todas as empresas"
                st.success(f"Regra salva para NCM {ncm_novo} — {alvo}!")
                st.rerun()
            else:
                st.error("Informe o NCM.")

    with col2:
        st.subheader("Regras cadastradas")
        fb1, fb2 = st.columns(2)
        filtro_ncm_regra = fb1.text_input("Buscar por NCM", placeholder="Ex: 84212300", label_visibility="collapsed", key="filtro_ncm_regra")
        filtro_emp_regra = fb2.text_input("Buscar por empresa", placeholder="Nome ou CNPJ...", label_visibility="collapsed", key="filtro_emp_regra")
        regras = listar_regras_ncm()
        if filtro_ncm_regra:
            regras = [r for r in regras if filtro_ncm_regra.strip() in r['ncm']]
        if filtro_emp_regra:
            termo = filtro_emp_regra.upper()
            regras = [r for r in regras if
                      termo in (r.get('razao_social') or '').upper() or
                      termo in (r.get('cnpj_destinatario') or '').upper()]
        if regras:
            for r in regras:
                c1, c2 = st.columns([4, 1])
                with c1:
                    cor = {'IMOBILIZADO': '🔵', 'USO E CONSUMO': '🟢', 'REVENDA': '🟡'}.get(r['classificacao'], '⚪')
                    empresa_tag = f" | 🏢 {r.get('razao_social') or formatar_cnpj(r['cnpj_destinatario'])}" if r.get('cnpj_destinatario') else " | 🌐 Global"
                    st.write(f"{cor} **NCM {r['ncm']}** — {r['classificacao']}{empresa_tag} | {r.get('descricao','')}")
                with c2:
                    if st.button("🗑️", key=f"del_{r['ncm']}_{r.get('cnpj_destinatario','')}"):
                        deletar_regra_ncm(r['ncm'], r.get('cnpj_destinatario', ''))
                        st.rerun()
        else:
            st.info("Nenhuma regra cadastrada ainda.")

# ══════════════════════════════════════════════════════════════════════════════
# PÁGINA 3 — Histórico
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "Histórico":
    st.title("Histórico de Classificações")
    st.caption("Cada item é registrado individualmente. Use 🗑️ para excluir um item específico do histórico.")

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT cnpj_destinatario, nome_destinatario FROM classificacoes "
            "WHERE confirmado_fiscal=1 AND nome_destinatario IS NOT NULL ORDER BY nome_destinatario"
        )
        clientes_hist_rows = cur.fetchall()
    finally:
        conn.close()

    opcoes_clientes = {'Todos': None}
    for r in clientes_hist_rows:
        if r['nome_destinatario']:
            opcoes_clientes[r['nome_destinatario']] = r['cnpj_destinatario']

    hf1, hf2, hf3, hf4 = st.columns([2, 1.5, 1.5, 1])
    with hf1:
        filtro_nome = st.selectbox("Cliente", list(opcoes_clientes.keys()), label_visibility="visible")
    with hf2:
        busca_hist = st.text_input("Buscar descrição / NCM", placeholder="Digite descrição ou NCM...", label_visibility="visible")
    with hf3:
        opcoes_class = ["Todas", "USO E CONSUMO", "IMOBILIZADO", "REVENDA", "INCERTO"]
        filtro_class = st.selectbox("Classificação", opcoes_class, label_visibility="visible")
    cnpj_filtro = opcoes_clientes[filtro_nome]

    registros = listar_historico_itens(cnpj_filtro)

    # Filtra por busca de texto
    if busca_hist:
        termo = busca_hist.upper()
        registros = [r for r in registros
                     if termo in (r.get('descricao_produto') or '').upper()
                     or termo in (r.get('ncm') or '').upper()]

    # Filtra por classificação
    if filtro_class != "Todas":
        registros = [r for r in registros if r.get('classificacao') == filtro_class]

    if not registros:
        st.info("Nenhum item encontrado." if busca_hist else "Nenhuma classificação salva ainda.")
    else:
        with hf4:
            df_exp = pd.DataFrame(registros).drop(columns=['id'], errors='ignore')
            csv = df_exp.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
            st.download_button("⬇️ Exportar", csv, "historico.csv", "text/csv")

        st.caption(f"{len(registros)} item(ns) encontrado(s)")
        st.divider()

        # Paginação para não renderizar centenas de botões de uma vez
        PAGE_SIZE = 50
        total_pags = max(1, (len(registros) + PAGE_SIZE - 1) // PAGE_SIZE)
        pag = st.number_input("Página", min_value=1, max_value=total_pags, value=1, step=1,
                               label_visibility="collapsed") if total_pags > 1 else 1
        inicio = (pag - 1) * PAGE_SIZE
        pagina_regs = registros[inicio: inicio + PAGE_SIZE]

        if total_pags > 1:
            st.caption(f"Página {pag} de {total_pags} — mostrando {len(pagina_regs)} de {len(registros)} itens")

        # Cabeçalho
        h1, h2, h3, h4, h5, h6, h7 = st.columns([2, 1, 3, 2, 1, 1, 0.4])
        for col, txt in zip([h1, h2, h3, h4, h5, h6, h7],
                             ["**Cliente**", "**NCM**", "**Descrição**", "**Classificação**", "**Cadastrado por**", "**Data**", ""]):
            col.markdown(txt)

        for reg in pagina_regs:
            c1, c2, c3, c4, c5, c6, c7 = st.columns([2, 1, 3, 2, 1, 1, 0.4])
            cor = {'IMOBILIZADO': '🔵', 'USO E CONSUMO': '🟢', 'REVENDA': '🟡', 'INCERTO': '🔴'}.get(reg.get('classificacao',''), '⚪')
            c1.write(reg.get('nome_destinatario') or reg.get('cnpj_destinatario', ''))
            c2.write(reg.get('ncm', ''))
            c3.write((reg.get('descricao_produto') or '')[:60])
            c4.write(f"{cor} {reg.get('classificacao', '')}")
            c5.write(reg.get('usuario') or '—')
            c6.write(reg.get('data_classificacao', ''))
            if c7.button("🗑️", key=f"del_item_{reg['id']}", help="Excluir este item do histórico"):
                deletar_historico_item(reg['cnpj_destinatario'], reg['ncm'], reg.get('descricao_produto', ''))
                st.rerun()
