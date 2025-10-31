# pages/2_Reportar_Erro.py

import streamlit as st
from supabase import create_client, Client
from datetime import datetime

# --- Configuração da Página ---
st.set_page_config(
    layout="wide", # Mudei para "wide" para dar mais espaço para a lista
    page_title='Reportar Erro'
)

st.title("🐞 Reportar um Erro ou Problema")

# --- Constantes de Opções ---
LISTA_PRODUTOS = ['Novo', 'Benefício', 'Cartão', 'Benefício & Cartão', 'Outro']
LISTA_CONVENIOS = ['govsp', 'govmt', 'Outro / Não Aplicável']
STATUS_OPTIONS = ['Aberto', 'Em Análise', 'Resolvido']

# --- Conexão com o Supabase ---
@st.cache_resource
def init_supabase_connection():
    try:
        # --- AJUSTE AQUI ---
        # Buscando dentro da seção [supabase] dos seus segredos
        url = st.secrets["supabase"]["supabase_url"]
        key = st.secrets["supabase"]["supabase_key"]
        # --- FIM DO AJUSTE ---
        
        return create_client(url, key)
    except Exception as e:
        st.error(f"Erro ao conectar com o Supabase: {e}")
        st.info("Certifique-se de que 'supabase_url' e 'supabase_key' estão configurados nos seus Streamlit Secrets DENTRO de uma seção [supabase].")
        return None

supabase = init_supabase_connection()

# --- Funções de Callback e Fetch ---

@st.cache_data(ttl=300) # Cache de 5 minutos
def fetch_reports():
    """Busca todos os relatórios, dos mais novos para os mais antigos."""
    try:
        response = supabase.table("bug_reports").select("*").order("created_at", desc=True).execute()
        
        # Retorna apenas a lista de dados, e não o objeto de resposta
        return response.data 
    
    except Exception as e:
        st.error(f"Erro ao buscar relatórios: {e}")
        return None

def update_status_callback(report_id: int):
    """
    Função chamada quando um selectbox de status é alterado.
    Ela atualiza o status no Supabase.
    """
    try:
        # Pega o novo valor do selectbox pelo seu 'key'
        new_status = st.session_state[f"status_select_{report_id}"]
        
        # Atualiza no Supabase
        supabase.table("bug_reports").update({"status": new_status}).eq("id", report_id).execute()
        
        st.toast(f"Status do Relatório #{report_id} atualizado para '{new_status}'!", icon="✅")
        
        # Limpa o cache da função fetch_reports para recarregar a lista
        fetch_reports.clear()
        
    except Exception as e:
        st.toast(f"Erro ao atualizar status: {e}", icon="❌")


# --- Interface Principal ---

if supabase:
    # 1. Formulário de Submissão (em um expander)
    with st.expander("Clique aqui para enviar um novo relatório de erro", expanded=False):
        with st.form("bug_report_form"):
            st.subheader("Detalhes do Problema")
            col1, col2 = st.columns(2)
            with col1:
                convenio_selecionado = st.selectbox(
                    "Convênio (Onde o erro ocorreu)",
                    options=LISTA_CONVENIOS,
                    index=len(LISTA_CONVENIOS)-1
                )
            with col2:
                produto_selecionado = st.selectbox(
                    "Produto (Onde o erro ocorreu)",
                    options=LISTA_PRODUTOS,
                    index=len(LISTA_PRODUTOS)-1
                )
            descricao_erro = st.text_area(
                "Descreva o erro (Obrigatório)",
                height=200,
                placeholder="Ex: Ao usar o convênio 'govsp' com o produto 'Novo', o cálculo da comissão saiu zerado..."
            )
            submitted = st.form_submit_button("Enviar Relatório", type="primary", use_container_width=True)

        if submitted:
            if not descricao_erro:
                st.error("Por favor, preencha a descrição do erro.")
            else:
                with st.spinner("Enviando relatório..."):
                    data_para_inserir = {
                        "convenio": convenio_selecionado,
                        "produto": produto_selecionado,
                        "descricao": descricao_erro,
                        "pagina": "Filtrador v4"
                        # O status será 'Aberto' por padrão (definido no Supabase)
                    }
                    response = supabase.table("bug_reports").insert(data_para_inserir).execute()
                    if response.data:
                        st.success("🎉 Relatório enviado com sucesso! Obrigado pelo feedback.")
                        fetch_reports.clear() # Limpa o cache para mostrar o novo item na lista
                    else:
                        st.error("Houve um problema ao enviar o relatório.")
    
    st.divider()

    # 2. Lista de Relatórios Existentes
    st.header("Relatórios de Erros Atuais")
    st.button("Recarregar Lista", on_click=fetch_reports.clear)

    # A variável agora contém a lista de dados diretamente
    reports_data = fetch_reports() 

    # Verifica se a lista não é None e não está vazia
    if reports_data: 
        # Layout dos Títulos
        col_data, col_conv, col_prod, col_desc, col_status = st.columns([1, 1, 1, 3, 1])
        with col_data:
            st.subheader("Data")
        with col_conv:
            st.subheader("Convênio")
        with col_prod:
            st.subheader("Produto")
        with col_desc:
            st.subheader("Descrição")
        with col_status:
            st.subheader("Status")

        # Itera diretamente sobre a lista
        for report in reports_data:
            report_id = report['id']
            # Tenta converter a data, tratando possíveis erros
            try:
                created_at_dt = datetime.fromisoformat(report['created_at'])
                data_formatada = created_at_dt.strftime("%d/%m/%Y %H:%M")
            except Exception:
                data_formatada = "Data inválida"
            
            # Pega o status atual e define o índice do selectbox
            current_status = report.get('status', 'Aberto')
            status_index = STATUS_OPTIONS.index(current_status) if current_status in STATUS_OPTIONS else 0
            
            with st.container(border=True):
                c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 3, 1])
                
                with c1:
                    st.write(data_formatada)
                with c2:
                    st.write(report['convenio'])
                with c3:
                    st.write(report['produto'])
                with c4:
                    st.caption(report['descricao'])
                with c5:
                    # Este é o Selectbox que atualiza o status
                    st.selectbox(
                        "Alterar Status",
                        options=STATUS_OPTIONS,
                        index=status_index,
                        key=f"status_select_{report_id}", # Chave única para o widget
                        label_visibility="collapsed",
                        on_change=update_status_callback, # Função chamada na mudança
                        args=(report_id,) # Argumento para a função
                    )
    else:
        st.info("Nenhum relatório de erro encontrado.")

else:
    st.error("A conexão com o banco de dados de relatórios falhou. Não é possível enviar ou carregar relatórios.")