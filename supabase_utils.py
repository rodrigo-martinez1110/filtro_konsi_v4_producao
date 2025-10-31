import streamlit as st
from supabase import create_client, Client
import copy
import json
from postgrest.exceptions import APIError
import pandas as pd
from datetime import date # Importado para safe_json_serialize

@st.cache_resource
def init_supabase() -> Client:
    """Inicializa e retorna o cliente Supabase usando os secrets do Streamlit."""
    try:
        # --- MODIFICAÇÃO AQUI ---
        supabase_url = st.secrets["supabase"]["supabase_url"]
        supabase_key = st.secrets["supabase"]["supabase_key"]
        # --- FIM DA MODIFICAÇÃO ---
        
        return create_client(supabase_url, supabase_key)
    except Exception as e:
        st.error(f"Erro ao conectar com o Supabase: {e}")
        return None

def safe_json_serialize(obj):
    """Converte um objeto para um formato JSON serializável, tratando datas."""
    def default(o):
        if isinstance(o, date): # Trata datas
            return o.isoformat()
        if hasattr(o, 'isoformat'): # Trata datetimes
            return o.isoformat()
        return str(o) # Fallback para string

    # Garante que o objeto não é nulo antes de copiar
    if obj is None:
        return None
    obj_copy = copy.deepcopy(obj)
    
    # Serializa e desserializa para garantir que é um objeto JSON válido
    return json.loads(json.dumps(obj_copy, default=default))

# --- FUNÇÃO DE SALVAR REESCRITA (para tabela larga) ---
def salvar_configuracao_no_supabase(params_gerais: dict, configs_banco: list):
    """
    Salva CADA configuração de banco como uma NOVA LINHA na tabela 'logs_auditoria_configs'.
    """
    client = init_supabase()
    if client is None:
        st.warning("Conexão com o Supabase falhou. Não foi possível salvar o log.")
        return False

    try:
        params_serializados = safe_json_serialize(params_gerais)
        linhas_para_inserir = []

        # Loop através de cada configuração de banco
        for config in configs_banco:
            
            # Lógica para determinar o 'produto' final
            produto_final = "N/A"
            tipo_campanha_global = params_gerais.get('tipo_campanha')
            
            if tipo_campanha_global == 'Novo':
                produto_final = "Novo"
            elif tipo_campanha_global == 'Benefício':
                produto_final = "Benefício"
            elif tipo_campanha_global == 'Cartão':
                produto_final = "Cartão"
            elif tipo_campanha_global == 'Benefício & Cartão':
                if config.get('cartao_escolhido') == 'Consignado':
                    produto_final = "Cartão"
                else:
                    produto_final = "Benefício"

            # Prepara o payload (uma linha para a tabela)
            payload = {
                # --- Colunas de Parâmetros Gerais ---
                "convenio": params_gerais.get('convenio'),
                "tipo_campanha_geral": params_gerais.get('tipo_campanha'),
                "equipe": params_gerais.get('equipe'),

                # --- Colunas da Configuração do Banco ---
                "produto_configurado": produto_final,
                "cartao_escolhido": config.get('cartao_escolhido'),
                "operador_logico": config.get('operador_logico'),
                "condicoes": safe_json_serialize(config.get('condicoes')),
                "banco": config.get('banco'),
                "coeficiente": config.get('coeficiente'),
                "comissao": config.get('comissao'),
                "parcelas": config.get('parcelas'),
                "coeficiente_parcela": config.get('coeficiente_parcela'),
                "margem_minima_cartao": config.get('margem_minima_cartao'),
                "usa_margem_seguranca": config.get('usa_margem_seguranca'),
                "modo_margem_seguranca": config.get('modo_margem_seguranca'),
                "valor_margem_seguranca": config.get('valor_margem_seguranca'),

                # --- JSON de Auditoria ---
                "params_gerais_json": params_serializados
            }
            linhas_para_inserir.append(payload)

        # Insere todas as linhas de uma vez
        client.table("logs_auditoria_configs").insert(linhas_para_inserir).execute()
        return True

    except APIError as e:
        st.warning(f"Erro ao salvar log no Supabase (APIError): {e}")
        return False
    except Exception as e:
        st.warning(f"Erro inesperado ao serializar ou salvar log no Supabase: {e}")
        return False

# --- FUNÇÃO DE CONSULTA ATUALIZADA (para tabela larga) ---
@st.cache_data(ttl=300) # Cache de 5 minutos
def consultar_coeficientes(convenio: str = None, produto: str = None) -> list:
    """
    Consulta os logs de auditoria no Supabase, com filtros.
    """
    client = init_supabase()
    if client is None:
        st.error("Conexão com o Supabase falhou. Não foi possível consultar os dados.")
        return []

    try:
        # Seleciona todas as colunas da nova tabela
        query = client.table("logs_auditoria_configs").select("*").order("created_at", desc=True)

        if convenio and convenio != "Todos":
            query = query.eq("convenio", convenio)
        
        # Filtra pela coluna 'produto_configurado'
        if produto and produto != "Todos":
            query = query.eq("produto_configurado", produto)
        
        query = query.limit(200) # Aumenta o limite
        
        response = query.execute()
        return response.data

    except APIError as e:
        st.error(f"Erro ao consultar dados no Supabase (APIError): {e}")
        return []
    except Exception as e:
        st.error(f"Erro inesperado ao consultar dados: {e}")
        return []
