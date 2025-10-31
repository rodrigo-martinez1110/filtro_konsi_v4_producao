import streamlit as st
import pandas as pd
from supabase import create_client, Client
from typing import List, Dict

@st.cache_data
def carregar_arquivos_csv(files: List[st.runtime.uploaded_file_manager.UploadedFile]) -> pd.DataFrame:
    """Junta múltiplos arquivos CSV carregados em um único DataFrame."""
    if not files:
        st.warning("Nenhum arquivo CSV foi carregado.")
        return pd.DataFrame()

    dataframes = []
    for arquivo in files:
        try:
            # Garante que o ponteiro do arquivo esteja no início
            arquivo.seek(0)
            df = pd.read_csv(arquivo, low_memory=False)
            if not df.empty:
                dataframes.append(df)
            else:
                st.warning(f"O arquivo {arquivo.name} está vazio e será ignorado.")
        except Exception as e:
            st.error(f"Erro ao ler o arquivo {arquivo.name}: {e}")
            
    if not dataframes:
        st.error("Nenhum arquivo CSV válido pôde ser processado.")
        return pd.DataFrame()
        
    return pd.concat(dataframes, ignore_index=True)