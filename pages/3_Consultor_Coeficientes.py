import streamlit as st
import pandas as pd
from supabase_utils import consultar_coeficientes # Importa a função de consulta atualizada

st.set_page_config(
    layout="wide",
    page_title='Consulta de Coeficientes'
)

st.title("📈 Consultar Histórico de Coeficientes")
st.markdown("Consulte os coeficientes e parâmetros de campanhas salvas anteriormente.")

# --- Opções de filtro ---
convenios_filtro = ["Todos", "govsp", "govmt"] 
produtos_filtro = ["Todos", "Novo", "Benefício", "Cartão"] # Filtra pelo 'produto_configurado'

col1, col2 = st.columns(2)
convenio_selecionado = col1.selectbox("Filtrar por Convênio:", convenios_filtro, key="filtro_convenio")
produto_selecionado = col2.selectbox("Filtrar por Produto:", produtos_filtro, key="filtro_produto")

if st.button("Consultar Histórico", use_container_width=True, type="primary"):
    
    with st.spinner("Buscando dados no Supabase..."):
        # Usa a nova função de consulta
        resultados = consultar_coeficientes(convenio_selecionado, produto_selecionado)
        
        if resultados:
            st.success(f"Encontrados {len(resultados)} registros.")
            
            # Converte a lista de dicts para um DataFrame
            df_resultados = pd.DataFrame(resultados)
            
            # Formata a data para melhor leitura
            if 'created_at' in df_resultados.columns:
                 try:
                    df_resultados['Data'] = pd.to_datetime(df_resultados['created_at']).dt.strftime('%d/%m/%Y %H:%M')
                 except Exception:
                    pass 
            
            # --- COLUNAS ATUALIZADAS (EXATAMENTE O QUE VOCÊ PEDIU) ---
            # Define as colunas que queremos mostrar e sua ordem
            colunas_para_mostrar = [
                'Data',
                'convenio',
                'produto_configurado',
                'banco',
                'coeficiente',
                'comissao',
                'parcelas',
                'coeficiente_parcela',
                'margem_minima_cartao',
                'usa_margem_seguranca',
                'modo_margem_seguranca',
                'valor_margem_seguranca',
                'operador_logico',
                'equipe',
                'tipo_campanha_geral', # Campanha "mãe"
                'condicoes' # Mostra as condições JSON
            ]
            
            # Filtra o DataFrame para ter apenas as colunas que existem
            colunas_finais = [col for col in colunas_para_mostrar if col in df_resultados.columns]
            
            # Renomeia colunas para visualização (opcional, mas limpo)
            df_display = df_resultados[colunas_finais].rename(columns={
                'produto_configurado': 'Produto',
                'tipo_campanha_geral': 'Campanha (Mãe)',
                'coeficiente_parcela': 'Coef. Parcela',
                'margem_minima_cartao': 'Margem Mín.',
                'usa_margem_seguranca': 'Usa Seg?',
                'modo_margem_seguranca': 'Modo Seg.',
                'valor_margem_seguranca': 'Valor Seg.'
            })
            
            st.dataframe(df_display, use_container_width=True)
            
            with st.expander("Ver dados JSON completos (para copiar)"):
                st.json(resultados)
        else:
            st.warning("Nenhum registro encontrado para estes filtros.")

