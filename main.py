import streamlit as st
import pandas as pd

st.set_page_config(
    layout="wide",
    page_title='Filtrador de Campanhas v4',
    initial_sidebar_state='expanded'
)

# Assumindo que estes arquivos .py estão no mesmo diretório
from juntar_arquivos import *
from frontend_componentes import *
from filtradores import * # --- 1. IMPORTAÇÃO ADICIONADA ---
from supabase_utils import salvar_configuracao_no_supabase 

# --- Título ---
st.title("🚀 Filtrador de Campanhas v4")

@st.cache_data
def converter_df_para_csv(df):
    """Converte o DataFrame para CSV com encoding correto para download."""
    return df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')


# --- 2. Upload de Arquivos ---
st.sidebar.header("1. Carregue os arquivos de higienização")
arquivos_carregados = st.sidebar.file_uploader(
    'Arraste um ou mais arquivos CSV aqui',
    accept_multiple_files=True,
    type=['csv'],
    key='file_uploader'
)
st.sidebar.write("---")

if arquivos_carregados:
    st.session_state.df_bruto = carregar_arquivos_csv(arquivos_carregados)
    
if 'df_bruto' in st.session_state and not st.session_state.df_bruto.empty:
    df_bruto = st.session_state.df_bruto
    st.success(f"Arquivos carregados com sucesso! Total de {len(df_bruto)} registros.")
    st.dataframe(df_bruto.head(3))
    st.write("---")
    
    tipo_campanha_selecionada = st.session_state.get('tipo_campanha_selectbox', 'Novo')
    convenio_detectado = df_bruto['Convenio'].iloc[0] if 'Convenio' in df_bruto.columns else None
    
    
    params_gerais = exibir_sidebar(df_bruto)
    
    configs_banco = exibir_configuracoes_banco(
        params_gerais['tipo_campanha'],
        params_gerais['convenio'],
        df_bruto
    )
    
    with st.expander("Parâmetros de Entrada (Debug)", expanded=False):
        st.write("Parâmetros Gerais:", params_gerais)
        st.write("Configurações por Banco:", configs_banco)
    
    # --- Ação Principal: Aplicar Filtros ---
    st.header("3. Gere a Campanha")
    if st.button("✨ Aplicar Filtros e Gerar Arquivo", type="primary", use_container_width=True):
        with st.spinner("Processando e aplicando filtros..."):
            try:
                # A função agora retorna a base e as estatísticas
                base_filtrada, stats = aplicar_filtros(df_bruto, params_gerais, configs_banco)
                
                # Salva ambos nos resultados da sessão
                st.session_state.base_filtrada = base_filtrada
                st.session_state.stats_filtragem = stats
                
                # Salva os parâmetros que FORAM USADOS para este filtro
                st.session_state.params_para_salvar = params_gerais
                st.session_state.configs_para_salvar = configs_banco

            except Exception as e:
                st.error(f"Ocorreu um erro inesperado durante a filtragem:")
                st.exception(e)
                if 'base_filtrada' in st.session_state:
                    del st.session_state.base_filtrada
                if 'stats_filtragem' in st.session_state:
                    del st.session_state.stats_filtragem

    # --- 4. Resultados e Ações Pós-Filtragem ---
    if 'base_filtrada' in st.session_state:
        base_filtrada = st.session_state.base_filtrada
        stats = st.session_state.get('stats_filtragem', [])
        
        # (NOVA VERIFICAÇÃO) Checa se o DataFrame resultante não está vazio
        if not base_filtrada.empty:
            st.success(f"Filtragem concluída! {len(base_filtrada)} registros encontrados.")
            
            # Exibe as estatísticas
            st.subheader("Estatísticas da Filtragem")
            stats_df = pd.DataFrame(stats)
            st.dataframe(stats_df)
            
            # Exibe a prévia
            st.subheader("Prévia dos Dados Filtrados")
            st.dataframe(base_filtrada.head())
            
            # Gera o CSV para download
            csv_data = converter_df_para_csv(base_filtrada)
            
            # Gera o nome do arquivo
            nome_arquivo = "campanha_filtrada.csv"
            # Tenta pegar o nome da campanha gerado pelo filtradores.py
            if 'Campanha' in base_filtrada.columns:
                nome_arquivo = f"{base_filtrada['Campanha'].iloc[0]}.csv"
                
            st.download_button(
                label="📥 Baixar Planilha Pronta",
                data=csv_data,
                file_name=nome_arquivo,
                mime='text/csv',
                use_container_width=True
            )
            
            # --- 2. BOTÃO DE SALVAR MANUAL ADICIONADO ---
            st.divider() # Adiciona um separador visual
            
            if st.button("🚀 Salvar esta Configuração no Supabase", use_container_width=True):
                # Verifica se os parâmetros existem no session_state
                if 'params_para_salvar' in st.session_state and 'configs_para_salvar' in st.session_state:
                    with st.spinner("Salvando configuração..."):
                        params = st.session_state.params_para_salvar
                        configs = st.session_state.configs_para_salvar
                        
                        sucesso = salvar_configuracao_no_supabase(params, configs)
                        
                        if sucesso:
                            st.success("Configuração salva com sucesso no Supabase!")
                        else:
                            st.error("Falha ao salvar a configuração.")
                else:
                    st.error("Erro: Não foi possível encontrar os parâmetros da última filtragem. Tente filtrar novamente.")
            
        else:
            # (AVISO MOVIDO) Agora, se a base estiver em session_state mas VAZIA,
            # ele exibirá o aviso corretamente.
            st.warning("Nenhum registro correspondeu aos filtros aplicados. Tente ajustar os parâmetros (ex: comissão mínima).")
    
    elif 'stats_filtragem' in st.session_state:
        # Isso só será acionado se um erro tiver ocorrido E a base_filtrada foi deletada
        st.warning("A filtragem rodou, mas nenhum resultado foi gerado. Verifique os parâmetros.")
    
else:
    st.info("Aguardando o carregamento dos arquivos CSV para iniciar a configuração da campanha.")