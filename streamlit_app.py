#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ACHE SUCATAS - Dashboard de Editais de Leilao
Visualizacao e filtragem de editais coletados do PNCP
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os

# Carregar secrets do Streamlit Cloud ou .env local
if hasattr(st, "secrets") and "SUPABASE_URL" in st.secrets:
    os.environ["SUPABASE_URL"] = st.secrets["SUPABASE_URL"]
    os.environ["SUPABASE_SERVICE_KEY"] = st.secrets.get(
        "SUPABASE_ANON_KEY", st.secrets.get("SUPABASE_SERVICE_KEY", "")
    )

from supabase_repository import SupabaseRepository

# =============================================================================
# CONFIGURACAO DA PAGINA
# =============================================================================
st.set_page_config(
    page_title="ACHE SUCATAS - Dashboard",
    page_icon="hammer",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =============================================================================
# CACHE
# =============================================================================


@st.cache_resource
def get_repository():
    """Instancia cached do repositorio Supabase."""
    return SupabaseRepository()


@st.cache_data(ttl=300)
def get_ufs_disponiveis(_repo):
    """Lista cached de UFs disponiveis."""
    return _repo.listar_ufs_disponiveis()


@st.cache_data(ttl=300)
def get_modalidades_disponiveis(_repo):
    """Lista cached de modalidades disponiveis."""
    return _repo.listar_modalidades_disponiveis()


# =============================================================================
# FUNCOES AUXILIARES
# =============================================================================


def format_currency(value):
    """Formata valor como moeda brasileira."""
    if value is None:
        return "N/D"
    try:
        formatted = f"R$ {value:,.2f}"
        return formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "N/D"


def format_date_br(date_str):
    """Formata data ISO para formato brasileiro."""
    if not date_str:
        return "N/D"
    try:
        if "T" in str(date_str):
            date_str = str(date_str).split("T")[0]
        parts = str(date_str).split("-")
        if len(parts) == 3:
            return f"{parts[2]}/{parts[1]}/{parts[0]}"
        return date_str
    except (ValueError, IndexError):
        return str(date_str)


# =============================================================================
# APLICACAO PRINCIPAL
# =============================================================================


def main():
    # Header
    st.title("ACHE SUCATAS - Dashboard")
    st.caption("Editais de Leilao Publico do Brasil - Fonte: PNCP")

    # Inicializar repositorio
    repo = get_repository()

    if not repo.enable_supabase:
        st.error("Erro: Nao foi possivel conectar ao Supabase")
        st.info("Configure SUPABASE_URL e SUPABASE_ANON_KEY nos secrets")
        st.code(
            """
# .streamlit/secrets.toml
SUPABASE_URL = "https://seu-projeto.supabase.co"
SUPABASE_ANON_KEY = "sua-chave-anon"
            """,
            language="toml",
        )
        return

    # =========================================================================
    # SIDEBAR - FILTROS
    # =========================================================================
    with st.sidebar:
        st.header("Filtros")

        # Filtro de UF
        ufs = get_ufs_disponiveis(repo)
        uf_options = ["Todos"] + ufs
        uf_selected = st.selectbox("Estado (UF)", options=uf_options, index=0)

        # Filtro de Data
        st.subheader("Periodo de Publicacao")
        col1, col2 = st.columns(2)

        default_end = datetime.now().date()
        default_start = default_end - timedelta(days=30)

        with col1:
            data_inicio = st.date_input("De", value=default_start, format="DD/MM/YYYY")
        with col2:
            data_fim = st.date_input("Ate", value=default_end, format="DD/MM/YYYY")

        # Filtro de Modalidade
        modalidades = get_modalidades_disponiveis(repo)
        modalidade_options = ["Todas"] + modalidades
        modalidade_selected = st.selectbox(
            "Modalidade", options=modalidade_options, index=0
        )

        # Limite de resultados
        limit = st.slider(
            "Max. resultados", min_value=10, max_value=500, value=50, step=10
        )

        # Botao de atualizar
        if st.button("Atualizar Dados"):
            st.cache_data.clear()
            st.rerun()

    # =========================================================================
    # BUSCAR DADOS
    # =========================================================================
    editais = repo.listar_editais_filtrados(
        uf=uf_selected if uf_selected != "Todos" else None,
        data_inicio=data_inicio.isoformat() if data_inicio else None,
        data_fim=data_fim.isoformat() if data_fim else None,
        modalidade=modalidade_selected if modalidade_selected != "Todas" else None,
        limit=limit,
    )

    # =========================================================================
    # METRICAS
    # =========================================================================
    total_editais = repo.contar_editais()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Total no Banco", value=total_editais if total_editais >= 0 else "N/D"
        )

    with col2:
        st.metric(label="Resultado Filtro", value=len(editais))

    with col3:
        st.metric(label="UFs Disponiveis", value=len(ufs))

    with col4:
        total_valor = sum(e.get("valor_estimado", 0) or 0 for e in editais)
        st.metric(label="Valor Total (filtro)", value=format_currency(total_valor))

    st.divider()

    # =========================================================================
    # TABELA DE EDITAIS
    # =========================================================================
    st.subheader("Editais de Leilao")

    if not editais:
        st.warning("Nenhum edital encontrado com os filtros selecionados.")
        return

    # Converter para DataFrame
    df = pd.DataFrame(editais)

    # Formatar colunas para exibicao
    df_display = df.copy()
    df_display["data_publicacao"] = df_display["data_publicacao"].apply(format_date_br)
    df_display["data_leilao"] = df_display["data_leilao"].apply(format_date_br)
    df_display["valor_estimado"] = df_display["valor_estimado"].apply(format_currency)

    # Selecionar colunas para exibir
    columns_display = [
        "titulo",
        "orgao",
        "uf",
        "cidade",
        "data_publicacao",
        "data_leilao",
        "valor_estimado",
        "quantidade_itens",
        "modalidade_leilao",
        "nome_leiloeiro",
    ]

    # Filtrar colunas existentes
    columns_display = [c for c in columns_display if c in df_display.columns]

    # Renomear colunas para exibicao
    column_names = {
        "titulo": "Titulo",
        "orgao": "Orgao",
        "uf": "UF",
        "cidade": "Cidade",
        "data_publicacao": "Publicacao",
        "data_leilao": "Data Leilao",
        "valor_estimado": "Valor Estimado",
        "quantidade_itens": "Itens",
        "modalidade_leilao": "Modalidade",
        "nome_leiloeiro": "Leiloeiro",
    }

    df_show = df_display[columns_display].rename(columns=column_names)

    # Exibir tabela
    st.dataframe(df_show, use_container_width=True, hide_index=True, height=400)

    # =========================================================================
    # DETALHES DO EDITAL
    # =========================================================================
    st.divider()
    st.subheader("Detalhes do Edital")

    if len(editais) > 0:
        edital_titles = [
            f"{e.get('uf', 'XX')} - {e.get('titulo', 'Sem titulo')[:50]}"
            for e in editais
        ]
        selected_idx = st.selectbox(
            "Selecione um edital para ver detalhes:",
            range(len(edital_titles)),
            format_func=lambda x: edital_titles[x],
        )

        if selected_idx is not None:
            edital = editais[selected_idx]

            with st.expander("Informacoes Completas", expanded=True):
                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("**Identificacao**")
                    st.write(f"**Titulo:** {edital.get('titulo', 'N/D')}")
                    st.write(f"**Orgao:** {edital.get('orgao', 'N/D')}")
                    st.write(
                        f"**Cidade/UF:** {edital.get('cidade', 'N/D')}/{edital.get('uf', 'N/D')}"
                    )
                    st.write(f"**PNCP ID:** {edital.get('pncp_id', 'N/D')}")

                    st.markdown("**Datas**")
                    st.write(
                        f"**Publicacao:** {format_date_br(edital.get('data_publicacao'))}"
                    )
                    st.write(
                        f"**Data do Leilao:** {format_date_br(edital.get('data_leilao'))}"
                    )

                with col2:
                    st.markdown("**Comercial**")
                    st.write(
                        f"**Valor Estimado:** {format_currency(edital.get('valor_estimado'))}"
                    )
                    st.write(
                        f"**Quantidade de Itens:** {edital.get('quantidade_itens', 'N/D')}"
                    )
                    st.write(
                        f"**Modalidade:** {edital.get('modalidade_leilao', 'N/D')}"
                    )
                    st.write(f"**Leiloeiro:** {edital.get('nome_leiloeiro', 'N/D')}")
                    st.write(f"**Score:** {edital.get('score', 'N/D')}")

                # Links
                st.markdown("**Links**")
                link_col1, link_col2 = st.columns(2)

                link_pncp = edital.get("link_pncp")
                if link_pncp:
                    with link_col1:
                        st.link_button("Ver no PNCP", link_pncp)

                pdf_url = edital.get("pdf_storage_url")
                if pdf_url:
                    with link_col2:
                        st.link_button("Download PDF", pdf_url)


# =============================================================================
# EXECUTAR
# =============================================================================
if __name__ == "__main__":
    main()
