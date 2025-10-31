# ui_components.py
import streamlit as st
import pandas as pd
from datetime import datetime
from dados_constantes import BANCOS_MAPEAMENTO, COLUNAS_CONDICAO
import math
import streamlit_nested_layout # Importa a correção do expander

def exibir_sidebar(df: pd.DataFrame):
    """
    Função principal que organiza e exibe toda a barra lateral.
    Ela chama funções menores para cada seção.
    Retorna um dicionário com todas as configurações.
    """
    st.sidebar.title("Configurações da Campanha")
    
    
    convenio = df['Convenio'].iloc[0] if not df.empty and 'Convenio' in df.columns else "N/A"
    st.sidebar.markdown(
        f"<span style='color:#d9534f; font-weight:bold;'>Convênio Detectado: {convenio}</span>", 
        unsafe_allow_html=True
    )

    # --- 1. Seleção da Campanha ---
    tipo_campanha = st.sidebar.selectbox(
        "1. Tipo da Campanha:",
        ['Novo', 'Benefício', 'Cartão', 'Benefício & Cartão'],
        key="tipo_campanha_selectbox"
    )
    

    # --- 2. Configurações Gerais ---
    with st.sidebar.expander("2. Filtros Gerais", expanded=True):
        comissao_minima = st.number_input("Comissão Mínima (R$)", min_value=0.0, step=1.0)
        comissao_maxima = st.number_input("Comissão Máxima (R$)", min_value=0.0, step=1.0, value=100000.00)
        
        key_margem = f"margem_limite_{tipo_campanha.lower().replace(' & ', '_')}"
        margem_limite = st.number_input(
            f"Corte da margem de empréstimo",
            help="Se o tipo de campanha for Crédito Novo, serão considerados apenas leads com margem de empréstimo maiores que o valor informado. Caso contrário, serão considerados apenas leads com margem de empréstimo menores que o valor informado.",
            value=20.0,
            step=5.0,
            key=key_margem
        )
        idade_padrao = 72 if tipo_campanha == 'Novo' else 74
        idade_max = st.number_input("Idade Máxima", 0, 120, idade_padrao)
        data_limite_idade = (datetime.today() - pd.DateOffset(years=idade_max)).date()

    # --- 3. Filtros de Exclusão ---
    with st.sidebar.expander("3. Excluir Grupos Específicos", expanded=False):
        
        # --- (INÍCIO DA MODIFICAÇÃO) ---
        
        # Filtro de Lotação (Seleção Exata)
        if 'Lotacao' in df.columns:
            lotacoes_disponiveis = sorted(list(df['Lotacao'].dropna().unique()))
            selecao_lotacao = st.multiselect(
                "Excluir Lotações (Seleção Exata):",
                options=lotacoes_disponiveis,
            )
        else:
            selecao_lotacao = []
        
        # Filtro de Lotação (Palavras-Chave)
        selecao_lotacao_palavras = st.text_input(
            "Excluir Lotações por palavra-chave (separar com ;)",
            placeholder="Ex: POLICIA; PM; EDUCACAO",
            key="lotacao_palavras"
        )
        # Converte a string em uma lista de palavras
        lista_lotacao_palavras = [p.strip().lower() for p in selecao_lotacao_palavras.split(';') if p.strip()]

        st.divider()

        # Filtro de Vínculo (Seleção Exata)
        if 'Vinculo_Servidor' in df.columns:
            vinculos_disponiveis = sorted(list(df['Vinculo_Servidor'].dropna().unique()))
            selecao_vinculos = st.multiselect(
                "Excluir Vínculos (Seleção Exata):",
                options=vinculos_disponiveis,
            )
        else:
            selecao_vinculos = []

        # Filtro de Vínculo (Palavras-Chave)
        selecao_vinculos_palavras = st.text_input(
            "Excluir Vínculos por palavra-chave (separar com ;)",
            placeholder="Ex: TEMPORARIO; COMISSIONADO",
            key="vinculos_palavras"
        )
        # Converte a string em uma lista de palavras
        lista_vinculos_palavras = [p.strip().lower() for p in selecao_vinculos_palavras.split(';') if p.strip()]
        
        # --- (FIM DA MODIFICAÇÃO) ---

    # --- 4. Configuração de Equipes ---
    with st.sidebar.expander("4. Atribuição de Equipes", expanded=True):
        equipes = st.selectbox(
            "Equipe Principal:",
            ['outbound', 'csapp', 'csativacao', 'cscdx', 'csport', 'outbound_virada'],
            key="equipe_campanha_selectbox"
        )
        
        # Adiciona o slider de Convai
        convai_percent = st.slider(
            "% para Convai (IA)",
            min_value=0,
            max_value=100,
            value=0,
            step=5
        )

    
    return {
        "tipo_campanha": tipo_campanha,
        "comissao_minima": comissao_minima,
        "comissao_maxima": comissao_maxima,
        "margem_limite": margem_limite,
        "data_limite_idade": data_limite_idade,
        
        # --- (INÍCIO DA MODIFICAÇÃO) ---
        "selecao_lotacao": selecao_lotacao,
        "selecao_lotacao_palavras": lista_lotacao_palavras, # Envia a lista de palavras-chave
        "selecao_vinculos": selecao_vinculos,
        "selecao_vinculos_palavras": lista_vinculos_palavras, # Envia a lista de palavras-chave
        # --- (FIM DA MODIFICAÇÃO) ---
        
        "equipe": equipes,
        "convenio": convenio,
        "convai_percent": convai_percent # Envia o percentual do convai
    }


# ===== CSS para colorir todos os expanders =====
st.markdown(
    """
    <style>
    /* Cor de fundo do conteúdo do expander */
    div[data-testid="stExpander"] > div[role="region"] {
        background-color: #e6f0ff;
        border-radius: 0 0 8px 8px;
        padding: 10px;
    }

    /* Cabeçalho do expander */
    div[data-testid="stExpander"] > div[role="button"] {
        background-color: #c0d4ff;
        border-radius: 8px 8px 0 0;
        padding: 5px 10px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

def exibir_configuracoes_banco(tipo_campanha: str, convenio: str, df: pd.DataFrame):
    """Configurações de banco com filtros avançados dinâmicos em expander colorido (AND/OR)."""
    st.header("2. Configure os Bancos e Produtos")

    # === Quantidade de Bancos ===
    if tipo_campanha == 'Benefício & Cartão':
        quant_bancos = st.number_input(
            "Quantidade de Configurações de Banco/Produto:",
            min_value=1, max_value=10, value=2, key="quant_bancos_misto"
        )
    else:
        quant_bancos = st.number_input(
            "Quantidade de Bancos:",
            min_value=1, max_value=10, value=1, key="quant_bancos_unico"
        )

    configuracoes_banco = []
    colunas_por_linha = 2
    linhas = math.ceil(quant_bancos / colunas_por_linha)

    for linha in range(linhas):
        cols = st.columns(colunas_por_linha)
        for j, col in enumerate(cols):

            i = linha * colunas_por_linha + j
            if i >= quant_bancos:
                break

            with col:
                with st.expander(f"Configuração #{i + 1}", expanded=True):
                    config = {}

                    # ===== Tipo de produto =====
                    # Ajuste para exibir o rádio apenas se a campanha for misturada
                    if tipo_campanha == 'Benefício & Cartão':
                        tipo_produto = st.radio(
                            "Tipo de Produto:", ['Benefício', 'Consignado'], key=f"produto_{i}", horizontal=True)
                    elif tipo_campanha == 'Benefício':
                         tipo_produto = "Benefício"
                    elif tipo_campanha == 'Cartão':
                        tipo_produto = "Consignado" # Mapeia para Consignado/Cartão
                    else: # 'Novo'
                        tipo_produto = "Novo" # Mapeia para Novo/Emprestimo
                    
                    config["cartao_escolhido"] = tipo_produto

                    # ===== Condições dentro de expander =====
                    # A biblioteca importada agora permite este aninhamento
                    with st.expander("Definir Condições de Aplicação (E/OU)"):
                        operador_logico = st.radio(
                            "Combinar condições com:",
                            ["E (AND)", "Ou (OR)"],
                            index=0, key=f"operador_logico_{i}",
                            horizontal=True
                        )
                        config["operador_logico"] = operador_logico

                        condicoes = []
                        num_condicoes = st.number_input(
                            "Número de condições para aplicar esta configuração:",
                            min_value=0, max_value=10, value=0, key=f"num_condicoes_{i}"
                        )

                        colunas_disponiveis = df.columns.tolist()

                        for c in range(num_condicoes):
                            st.markdown(f"**Condição #{c + 1}**")
                            tipo_condicao = st.selectbox(
                                "Tipo de condição:",
                                ["Coluna = Coluna", "Coluna < Valor", "Coluna > Valor", "Coluna contém palavras"],
                                key=f"tipo_cond_{i}_{c}"
                            )

                            if tipo_condicao == "Coluna = Coluna":
                                coluna1 = st.selectbox("Coluna 1:", options=colunas_disponiveis, key=f"col1_{i}_{c}")
                                coluna2 = st.selectbox("Coluna 2:", options=colunas_disponiveis, key=f"col2_{i}_{c}")
                                st.info(f"Exemplo: Aplicar quando os valores de '{coluna1}' forem iguais aos valores de '{coluna2}'")
                                condicoes.append({"tipo":"coluna_coluna", "coluna1":coluna1, "coluna2":coluna2})

                            elif tipo_condicao in ["Coluna < Valor", "Coluna > Valor"]:
                                coluna = st.selectbox("Coluna:", options=colunas_disponiveis, key=f"col_{i}_{c}")
                                valor = st.text_input(
                                    "Valor para comparar:",
                                    placeholder="Ex: 1980-10-11 (para datas) ou 1000 (para números)",
                                    key=f"valor_{i}_{c}"
                                )
                                st.info(f"Exemplo: Aplicar quando '{coluna}' {('<' if tipo_condicao=='Coluna < Valor' else '>')} {valor}")
                                condicoes.append({
                                    "tipo":"coluna_valor", 
                                    "operador": "<" if tipo_condicao=="Coluna < Valor" else ">", 
                                    "coluna":coluna, 
                                    "valor":valor
                                })

                            elif tipo_condicao == "Coluna contém palavras":
                                coluna = st.selectbox("Coluna:", options=colunas_disponiveis, key=f"col_{i}_{c}")
                                palavras = st.text_input(
                                    "Palavras (separadas por ; )",
                                    placeholder="Ex: CELETISTA; TEMPORARIO",
                                    key=f"palavras_{i}_{c}"
                                )
                                lista_palavras = [p.strip().lower() for p in palavras.split(";") if p.strip()]
                                st.info(f"Exemplo: Aplicar quando '{coluna}' contém qualquer uma das palavras: {', '.join(lista_palavras)}")
                                condicoes.append({"tipo":"coluna_palavras", "coluna":coluna, "palavras":lista_palavras})

                        config["condicoes"] = condicoes

                    # ===== Banco e parâmetros =====
                    banco_nome = st.selectbox("Banco:", list(BANCOS_MAPEAMENTO.keys()), key=f"banco_{i}")
                    config["banco"] = BANCOS_MAPEAMENTO[banco_nome]

                    config["coeficiente"] = st.number_input("Coeficiente Principal:", min_value=0.0, step=0.0001, format="%.4f", key=f"coef_{i}")
                    config["comissao"] = st.number_input("Comissão (%):", min_value=0.0, max_value=100.0, step=0.01, key=f"comissao_{i}")
                    config["parcelas"] = st.number_input("Parcelas:", min_value=1, max_value=200, step=1, key=f"parcelas_{i}")

                    coef_str = st.text_input("Coeficiente da Parcela:", "1.0", key=f"coef_parcela_{i}").replace(",", ".")
                    config["coeficiente_parcela"] = float(coef_str) if coef_str else 1.0

                    # Margem mínima
                    config["margem_minima_cartao"] = 30.0
                    if tipo_campanha in ['Benefício', 'Cartão', 'Benefício & Cartão']:
                        config["margem_minima_cartao"] = st.number_input("Margem Mínima Produto:", value=30.0, key=f"mg_minima_{i}")

                    # Margem de segurança
                    config["usa_margem_seguranca"] = st.checkbox("Usar Margem de Segurança?", key=f"usa_margem_seg_{i}")
                    if config["usa_margem_seguranca"]:
                        col1, col2 = st.columns(2)
                        with col1:
                            tipo_margem = st.radio("Tipo de cálculo:", ["Percentual (%)", "Valor Fixo (R$)"], key=f"tipo_margem_{i}", horizontal=True)
                        with col2:
                            if tipo_margem == "Percentual (%)":
                                valor_margem = st.number_input("Valor (%)", min_value=0.0, max_value=100.0, value=5.0, step=0.1, key=f"valor_margem_perc_{i}")
                            else:
                                valor_margem = st.number_input("Valor (R$)", min_value=0.0, value=50.0, step=1.0, key=f"valor_margem_fixo_{i}")
                        config["modo_margem_seguranca"] = tipo_margem
                        config["valor_margem_seguranca"] = valor_margem
                    else:
                        config["modo_margem_seguranca"] = None
                        config["valor_margem_seguranca"] = None

                    configuracoes_banco.append(config)

    return configuracoes_banco




# ======================================================================
# Filtro Master
def exibir_sidebar_simulacoes():
    """Cria a barra lateral com os parâmetros para o filtro de simulações."""
    st.sidebar.header("⚙️ Parâmetros de Saída")
    
    with st.sidebar.expander("Definir Parâmetros", expanded=True):
        equipes_konsi = ['outbound', 'csapp', 'csport', 'cscdx', 'csativacao', 'cscp']
        equipe = st.selectbox("Selecione a Equipe", equipes_konsi, key="equipe_simulacao")
        comissao_banco = st.number_input("Comissão do banco (%)", value=10.0, step=0.5, min_value=0.0) / 100
        comissao_minima = st.number_input("Comissão mínima (R$)", value=50.0, step=10.0, min_value=0.0)
        comissao_maxima = st.number_input("Comissão máxima (R$)", value=50.0, step=10.0, min_value=0.0)

    filtrar_saldo_devedor = st.sidebar.checkbox("Apenas com saldo devedor > 0", value=False)

    return {
        "equipe": equipe,
        "comissao_banco": comissao_banco,
        "comissao_minima": comissao_minima,
        "comissao_maxima": comissao_maxima,
        "filtrar_saldo_devedor": filtrar_saldo_devedor
    }

