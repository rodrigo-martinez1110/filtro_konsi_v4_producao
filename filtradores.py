"""
Módulo de filtragem e processamento de bases de dados para campanhas.
Organizado por convenio + produto para maior modularidade.
"""

import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime
from dados_constantes import * # Certifique-se que este arquivo exista no seu projeto
import re

# ============================================
# FUNÇÕES AUXILIARES
# ============================================

def _aplicar_margem_seguranca(margem_disponivel_series: pd.Series, config: dict) -> pd.Series:
    """Aplica margem de segurança à série de margens."""
    # Garante que a série seja numérica, tratando erros e NaNs
    margem_numerica = pd.to_numeric(margem_disponivel_series, errors='coerce').fillna(0)

    if not config.get("usa_margem_seguranca"):
        return margem_numerica

    modo = config.get("modo_margem_seguranca")
    valor = config.get("valor_margem_seguranca", 0)

    # Garante que valor seja numérico
    try:
        valor = float(valor)
    except (ValueError, TypeError):
        valor = 0.0

    if modo == "Percentual (%)":
        return margem_numerica * (1 - valor / 100)
    elif modo == "Valor Fixo (R$)":
        return (margem_numerica - valor).clip(lower=0)

    return margem_numerica


def _criar_mascara_condicional(base: pd.DataFrame, config: dict, tratado_col: str) -> pd.Series:
    """
    Cria uma máscara booleana com base nas condições dinâmicas da UI.
    Lê as regras da 'config' e o operador lógico ('E' ou 'OU').
    """
    # Garante que a coluna 'tratado' exista
    if tratado_col not in base.columns:
        st.error(f"Erro interno: Coluna de controle '{tratado_col}' não encontrada.")
        return pd.Series([False] * len(base), index=base.index)
    # Garante que a coluna 'tratado' seja booleana
    try:
        base[tratado_col] = base[tratado_col].astype(bool)
    except Exception:
        st.warning(f"Não foi possível converter a coluna '{tratado_col}' para booleano. Assumindo 'False'.")
        base[tratado_col] = False
        
    mascara_base = (base[tratado_col] == False)
    
    condicoes = config.get("condicoes", [])
    if not condicoes:
        return mascara_base

    lista_de_mascaras = []
    for c_idx, c in enumerate(condicoes):
        try:
            tipo = c.get("tipo")
            mascara_condicao = pd.Series([False] * len(base), index=base.index) # Default False

            if tipo == "coluna_coluna":
                col1 = c.get('coluna1')
                col2 = c.get('coluna2')
                if col1 and col2 and col1 in base.columns and col2 in base.columns:
                    num1 = pd.to_numeric(base[col1], errors='coerce')
                    num2 = pd.to_numeric(base[col2], errors='coerce')
                    m_num = (num1 == num2)
                    m_str = (base[col1].fillna('').astype(str) == base[col2].fillna('').astype(str))
                    mascara_condicao = m_num.fillna(False) | (~m_num.fillna(True) & m_str)
                else:
                    st.warning(f"Condição {c_idx+1} 'coluna_coluna' ignorada: Colunas '{col1}' ou '{col2}' inválidas ou não encontradas.")

            elif tipo == "coluna_valor":
                coluna_nome = c.get('coluna')
                valor_str = c.get('valor')
                operador = c.get('operador')

                if not all([coluna_nome, valor_str is not None, operador]):
                        st.warning(f"Condição {c_idx+1} 'coluna_valor' incompleta: {c}")
                        continue

                if coluna_nome not in base.columns:
                    st.warning(f"Condição {c_idx+1} 'coluna_valor' ignorada: Coluna '{coluna_nome}' não encontrada.")
                    continue

                coluna = base[coluna_nome]
                valor_str_cleaned = str(valor_str).strip()
                valor_num = pd.to_numeric(valor_str_cleaned, errors='coerce')
                col_num = pd.to_numeric(coluna, errors='coerce')

                if not pd.isna(valor_num):
                    if operador == '<': mascara_condicao = (col_num < valor_num)
                    else: mascara_condicao = (col_num > valor_num)
                else:
                    try:
                        valor_data = pd.to_datetime(valor_str_cleaned, errors='raise')
                        col_data = pd.to_datetime(coluna, errors='coerce')
                        if not col_data.isna().all():
                            if operador == '<': mascara_condicao = (col_data < valor_data)
                            else: mascara_condicao = (col_data > valor_data)
                        else:
                            col_str = coluna.astype(str)
                            if operador == '<': mascara_condicao = (col_str < valor_str_cleaned)
                            else: mascara_condicao = (col_str > valor_str_cleaned)
                    except (ValueError, TypeError):
                        col_str = coluna.astype(str)
                        if operador == '<': mascara_condicao = (col_str < valor_str_cleaned)
                        else: mascara_condicao = (col_str > valor_str_cleaned)

                mascara_condicao = mascara_condicao.fillna(False)

            elif tipo == "coluna_palavras":
                coluna_nome = c.get('coluna')
                palavras = c.get('palavras', [])

                if not coluna_nome or not palavras:
                    st.warning(f"Condição {c_idx+1} 'coluna_palavras' incompleta: {c}")
                    continue

                if coluna_nome not in base.columns:
                    st.warning(f"Condição {c_idx+1} 'coluna_palavras' ignorada: Coluna '{coluna_nome}' não encontrada.")
                    continue

                palavras_escaped = [re.escape(str(p).strip()) for p in palavras if str(p).strip()]
                if palavras_escaped:
                    palavras_regex = '|'.join(palavras_escaped)
                    mascara_condicao = base[coluna_nome].astype(str).str.contains(palavras_regex, case=False, na=False, regex=True)

            lista_de_mascaras.append(mascara_condicao)

        except Exception as e:
            st.error(f"Erro inesperado ao processar condição #{c_idx+1} ({c.get('tipo')} '{c.get('coluna')}'): {e}")
            lista_de_mascaras.append(pd.Series([False] * len(base), index=base.index))

    if not lista_de_mascaras:
        return mascara_base if not config.get("condicoes") else pd.Series([False] * len(base), index=base.index)

    operador_logico = config.get("operador_logico", "E (AND)")
    try:
        if operador_logico == "E (AND)":
            mascara_combinada = pd.Series([True] * len(base), index=base.index)
            for m in lista_de_mascaras:
                mascara_combinada &= m
        else: # "Ou (OR)"
            mascara_combinada = pd.Series([False] * len(base), index=base.index)
            for m in lista_de_mascaras:
                mascara_combinada |= m
    except Exception as e:
        st.error(f"Erro ao combinar máscaras com '{operador_logico}': {e}")
        return pd.Series([False] * len(base), index=base.index)

    return mascara_base & mascara_combinada


# ============================================
# PRÉ-PROCESSAMENTO
# ============================================

def _preprocessar_base(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Normaliza colunas, aplica filtros gerais e inicializa colunas."""
    if df is None or not isinstance(df, pd.DataFrame):
        st.error("Erro Crítico: Dados de entrada inválidos para _preprocessar_base.")
        return pd.DataFrame()
    base = df.copy()

    colunas_essenciais = ['Nome_Cliente', 'CPF', 'Lotacao', 'Vinculo_Servidor', 'Data_Nascimento',
                         'MG_Emprestimo_Disponivel', 'MG_Beneficio_Saque_Total', 'MG_Beneficio_Saque_Disponivel',
                         'MG_Cartao_Total', 'MG_Cartao_Disponivel', 'Matricula']
    for col in colunas_essenciais:
        if col not in base.columns:
            st.warning(f"Coluna essencial '{col}' não encontrada. Criando vazia.")
            base[col] = pd.NA

    try:
        if 'Nome_Cliente' in base.columns:
            base['Nome_Cliente'] = base['Nome_Cliente'].apply(lambda x: x.title() if pd.notna(x) and isinstance(x, str) else x)
        if 'CPF' in base.columns:
            base['CPF'] = base['CPF'].astype(str).str.replace(r"[.\-]", "", regex=True).str.strip().replace(['', 'nan', 'None'], pd.NA)
    except Exception as e:
        st.error(f"Erro na limpeza de Nome/CPF: {e}")
        return pd.DataFrame()

    try:
        if 'Lotacao' in base.columns:
            selecao_lotacao_exata = params.get('selecao_lotacao', [])
            if selecao_lotacao_exata:
                base = base[~base['Lotacao'].astype(str).isin(selecao_lotacao_exata)]
            selecao_lotacao_palavras = params.get('selecao_lotacao_palavras', [])
            if selecao_lotacao_palavras:
                lotacao_regex = '|'.join([re.escape(str(p)) for p in selecao_lotacao_palavras if str(p)])
                if lotacao_regex:
                    mascara_lotacao = base['Lotacao'].astype(str).str.contains(lotacao_regex, case=False, na=False, regex=True)
                    base = base[~mascara_lotacao]

        if 'Vinculo_Servidor' in base.columns:
            selecao_vinculos_exatos = params.get('selecao_vinculos', [])
            if selecao_vinculos_exatos:
                base = base[~base['Vinculo_Servidor'].astype(str).isin(selecao_vinculos_exatos)]
            selecao_vinculos_palavras = params.get('selecao_vinculos_palavras', [])
            if selecao_vinculos_palavras:
                vinculo_regex = '|'.join([re.escape(str(p)) for p in selecao_vinculos_palavras if str(p)])
                if vinculo_regex:
                    mascara_vinculo = base['Vinculo_Servidor'].astype(str).str.contains(vinculo_regex, case=False, na=False, regex=True)
                    base = base[~mascara_vinculo]
    except Exception as e:
        st.error(f"Erro nos filtros de exclusão: {e}")
        return pd.DataFrame()

    if 'Data_Nascimento' in base.columns and not base['Data_Nascimento'].isna().all():
        data_limite_idade_obj = params.get('data_limite_idade')
        if data_limite_idade_obj:
            try:
                datas_nascimento = pd.to_datetime(base["Data_Nascimento"], dayfirst=True, errors='coerce')
                mask_falha1 = datas_nascimento.isna()
                if mask_falha1.any():
                        datas_nascimento.loc[mask_falha1] = pd.to_datetime(base.loc[mask_falha1, "Data_Nascimento"], dayfirst=True, errors='coerce', format='%d/%m/%Y')
                
                data_limite_dt64 = pd.Timestamp(data_limite_idade_obj)
                base = base[(~datas_nascimento.isna()) & (datas_nascimento >= data_limite_dt64)]
            except Exception as e:
                st.error(f"Erro ao aplicar filtro de idade: {e}. Verifique formatos em 'Data_Nascimento'.")

    base['tratado'] = False
    base['tratado_beneficio'] = False
    base['tratado_cartao'] = False
    for prod in ['emprestimo', 'beneficio', 'cartao']:
        col_vl = f'valor_liberado_{prod}'
        col_vp = f'valor_parcela_{prod}'
        col_co = f'comissao_{prod}'
        col_ba = f'banco_{prod}'
        col_pr = f'prazo_{prod}'
        if col_vl not in base.columns: base[col_vl] = 0.0
        if col_vp not in base.columns: base[col_vp] = 0.0
        if col_co not in base.columns: base[col_co] = 0.0
        if col_ba not in base.columns: base[col_ba] = ''
        if col_pr not in base.columns: base[col_pr] = 0
        
    # Garante colunas GOVSP
    for col in ['MG_Beneficio_Saque_Total', 'MG_Beneficio_Saque_Disponivel', 'MG_Cartao_Total', 'MG_Cartao_Disponivel', 'Matricula']:
        if col not in base.columns:
            st.warning(f"Coluna GOVSP '{col}' não encontrada. Criando vazia.")
            base[col] = pd.NA

    return base


# ============================================
# FUNÇÕES ESPECÍFICAS POR CONVENIO + PRODUTO
# ============================================

# --- GOVSP ---
def govsp_novo(base: pd.DataFrame, params: dict, config: dict) -> pd.DataFrame:
    try:
        base_calc = base.copy()
        if 'MG_Emprestimo_Disponivel' in base_calc.columns:
            base_calc['MG_Emprestimo_Disponivel'] = pd.to_numeric(base_calc['MG_Emprestimo_Disponivel'], errors='coerce')
            base_filtrada = base_calc.loc[(base_calc['MG_Emprestimo_Disponivel'] >= 0).fillna(False)]
        else:
            st.warning("GOVSP Novo: Coluna 'MG_Emprestimo_Disponivel' não encontrada.")
            base_filtrada = base_calc
        return _aplicar_regras_emprestimo(base_filtrada, config)
    except Exception as e:
        st.error(f"Erro em govsp_novo: {e}")
        return base

def govsp_beneficio(base: pd.DataFrame, params: dict, config: dict) -> pd.DataFrame:
    """ Lógica GOVSP específica para Benefício """
    try:
        base_calc = base.copy()
        base_calc['MG_Beneficio_Saque_Total'] = pd.to_numeric(base_calc['MG_Beneficio_Saque_Total'], errors='coerce')
        base_calc['MG_Beneficio_Saque_Disponivel'] = pd.to_numeric(base_calc['MG_Beneficio_Saque_Disponivel'], errors='coerce')

        # Chama a função genérica (que usa a UI)
        base_calc = _aplicar_regras_beneficio(base_calc, config)

        # Aplica regra GOVSP: Zera valor se já usou margem
        mascara_usou_beneficio = (base_calc['MG_Beneficio_Saque_Total'] > base_calc['MG_Beneficio_Saque_Disponivel']).fillna(False)
        # Zera apenas para quem foi TRATADO pela função acima E já usou a margem
        indices_para_zerar = base_calc[mascara_usou_beneficio & (base_calc['tratado_beneficio'] == True)].index

        if not indices_para_zerar.empty:
            base_calc.loc[indices_para_zerar, 'valor_liberado_beneficio'] = 0.0
            base_calc.loc[indices_para_zerar, 'comissao_beneficio'] = 0.0
            base_calc.loc[indices_para_zerar, 'valor_parcela_beneficio'] = 0.0

        return base_calc
    except Exception as e:
        st.error(f"Erro em govsp_beneficio: {e}")
        return base

def govsp_cartao(base: pd.DataFrame, params: dict, config: dict) -> pd.DataFrame:
    """ Lógica GOVSP específica para Cartão """
    try:
        base_calc = base.copy()
        base_calc['MG_Cartao_Total'] = pd.to_numeric(base_calc['MG_Cartao_Total'], errors='coerce')
        base_calc['MG_Cartao_Disponivel'] = pd.to_numeric(base_calc['MG_Cartao_Disponivel'], errors='coerce')
        
        # Chama a função genérica (que usa a UI)
        base_calc = _aplicar_regras_cartao(base_calc, config)

        # Aplica regra GOVSP: Zera valor se já usou margem
        mascara_usou_cartao = (base_calc['MG_Cartao_Total'] > base_calc['MG_Cartao_Disponivel']).fillna(False)
        # Zera apenas para quem foi TRATADO pela função acima E já usou a margem
        indices_para_zerar = base_calc[mascara_usou_cartao & (base_calc['tratado_cartao'] == True)].index

        if not indices_para_zerar.empty:
            base_calc.loc[indices_para_zerar, 'valor_liberado_cartao'] = 0.0
            base_calc.loc[indices_para_zerar, 'comissao_cartao'] = 0.0
            base_calc.loc[indices_para_zerar, 'valor_parcela_cartao'] = 0.0

        return base_calc
    except Exception as e:
        st.error(f"Erro em govsp_cartao: {e}")
        return base

# --- GOVMT ---
def govmt_novo(base: pd.DataFrame, params: dict, config: dict) -> pd.DataFrame:
    try:
        base_calc = base.copy()
        if 'MG_Compulsoria_Disponivel' in base_calc.columns:
            base_calc['MG_Compulsoria_Disponivel'] = pd.to_numeric(base_calc['MG_Compulsoria_Disponivel'], errors='coerce')
            base_filtrada = base_calc.loc[(base_calc['MG_Compulsoria_Disponivel'] >= 0).fillna(False)]
        else:
            st.warning("GOVMT Novo: Coluna 'MG_Compulsoria_Disponivel' não encontrada.")
            base_filtrada = base_calc
        return _aplicar_regras_emprestimo(base_filtrada, config)
    except Exception as e:
        st.error(f"Erro em govmt_novo: {e}")
        return base

# ============================================
# FUNÇÕES GENÉRICAS DE PROCESSAMENTO
# ============================================

def generico_novo(base: pd.DataFrame, params: dict, config: dict) -> pd.DataFrame:
    try:
        return _aplicar_regras_emprestimo(base, config)
    except Exception as e:
        st.error(f"Erro em generico_novo: {e}")
        return base.copy()

def generico_beneficio(base: pd.DataFrame, params: dict, config: dict) -> pd.DataFrame:
    try:
        return _aplicar_regras_beneficio(base, config)
    except Exception as e:
        st.error(f"Erro em generico_beneficio: {e}")
        return base.copy()

def generico_cartao(base: pd.DataFrame, params: dict, config: dict) -> pd.DataFrame:
    try:
        return _aplicar_regras_cartao(base, config)
    except Exception as e:
        st.error(f"Erro em generico_cartao: {e}")
        return base.copy()


# ============================================
# FUNÇÕES GENÉRICAS DE CÁLCULO POR PRODUTO
# ============================================

def _aplicar_regras_emprestimo(base: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Aplica cálculo de empréstimo com base na máscara condicional da UI."""
    try:
        base_calc = base.copy()
        mask = _criar_mascara_condicional(base_calc, config, 'tratado')
        indices_para_calcular = base_calc[mask].index

        if not indices_para_calcular.empty:
            if 'MG_Emprestimo_Disponivel' not in base_calc.columns:
                st.error("Erro: Coluna 'MG_Emprestimo_Disponivel' não encontrada.")
                return base
            margem_ajustada = _aplicar_margem_seguranca(base_calc.loc[indices_para_calcular, 'MG_Emprestimo_Disponivel'], config)
            
            # --- CORREÇÃO CÁLCULO VALOR LIBERADO: MARGEM * COEF ---
            valor_liberado = (margem_ajustada * config.get('coeficiente', 1)).round(2)
            # ------------------------------------
            valor_parcela = margem_ajustada.round(2)
            comissao = (valor_liberado * (config.get('comissao',0)/100)).round(2)

            base_calc.loc[indices_para_calcular, 'valor_liberado_emprestimo'] = valor_liberado.fillna(0)
            base_calc.loc[indices_para_calcular, 'valor_parcela_emprestimo'] = valor_parcela.fillna(0)
            base_calc.loc[indices_para_calcular, 'comissao_emprestimo'] = comissao.fillna(0)
            base_calc.loc[indices_para_calcular, 'banco_emprestimo'] = config.get('banco')
            base_calc.loc[indices_para_calcular, 'prazo_emprestimo'] = config.get('parcelas')
            base_calc.loc[indices_para_calcular, 'tratado'] = True
        return base_calc
    except Exception as e:
        st.error(f"Erro em _aplicar_regras_emprestimo: {e}")
        return base

def _aplicar_regras_beneficio(base: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Aplica cálculo de benefício com base na máscara condicional da UI."""
    try:
        base_calc = base.copy()
        
        # --- INÍCIO DA MODIFICAÇÃO ---
        if 'MG_Beneficio_Saque_Disponivel' not in base_calc.columns:
                st.error("Erro: Coluna 'MG_Beneficio_Saque_Disponivel' não encontrada.")
                return base
        
        # Garante que a coluna de margem seja numérica
        base_calc['MG_Beneficio_Saque_Disponivel'] = pd.to_numeric(base_calc['MG_Beneficio_Saque_Disponivel'], errors='coerce')

        mask_condicional = _criar_mascara_condicional(base_calc, config, 'tratado_beneficio')
        
        # Pega a margem mínima da config (a UI salva como 'margem_minima_cartao' para ambos)
        margem_min_beneficio = config.get('margem_minima_cartao', 0)
        
        # Cria a máscara de margem mínima
        mask_margem_minima = (base_calc['MG_Beneficio_Saque_Disponivel'] >= margem_min_beneficio).fillna(False)
        
        # Combina as máscaras
        mask = mask_condicional & mask_margem_minima
        indices_para_calcular = base_calc[mask].index
        # --- FIM DA MODIFICAÇÃO ---

        if not indices_para_calcular.empty:
            # Coluna já verificada e convertida acima
            margem_ajustada = _aplicar_margem_seguranca(base_calc.loc[indices_para_calcular, 'MG_Beneficio_Saque_Disponivel'], config)

            # --- CORREÇÃO CÁLCULO VALOR LIBERADO: MARGEM * COEF ---
            valor_liberado = (margem_ajustada * config.get('coeficiente', 1)).round(2)
            # ------------------------------------
            coef_parcela = config.get('coeficiente_parcela', 1)
            if pd.isna(coef_parcela) or coef_parcela == 0: coef_parcela = 1
            valor_parcela = (valor_liberado / coef_parcela).round(2) if coef_parcela != 0 else 0.0
            comissao = (valor_liberado * (config.get('comissao',0)/100)).round(2)

            base_calc.loc[indices_para_calcular, 'valor_liberado_beneficio'] = valor_liberado.fillna(0)
            base_calc.loc[indices_para_calcular, 'valor_parcela_beneficio'] = valor_parcela.fillna(0)
            base_calc.loc[indices_para_calcular, 'comissao_beneficio'] = comissao.fillna(0)
            base_calc.loc[indices_para_calcular, 'banco_beneficio'] = config.get('banco')
            base_calc.loc[indices_para_calcular, 'prazo_beneficio'] = config.get('parcelas')
            base_calc.loc[indices_para_calcular, 'tratado_beneficio'] = True
        return base_calc
    except Exception as e:
        st.error(f"Erro em _aplicar_regras_beneficio: {e}")
        return base

def _aplicar_regras_cartao(base: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Aplica cálculo de cartão com base na máscara condicional da UI."""
    try:
        base_calc = base.copy()
        if 'MG_Cartao_Disponivel' not in base.columns:
            st.error("Erro: Coluna 'MG_Cartao_Disponivel' não encontrada.")
            return base

        base_calc['MG_Cartao_Disponivel'] = pd.to_numeric(base_calc['MG_Cartao_Disponivel'], errors='coerce')

        mask_condicional = _criar_mascara_condicional(base_calc, config, 'tratado_cartao')
        margem_min_cartao = config.get('margem_minima_cartao', 0)
        mask_margem_minima = (base_calc['MG_Cartao_Disponivel'] >= margem_min_cartao).fillna(False)
        mask = mask_condicional & mask_margem_minima
        indices_para_calcular = base_calc[mask].index

        if not indices_para_calcular.empty:
            margem_ajustada = _aplicar_margem_seguranca(base_calc.loc[indices_para_calcular, 'MG_Cartao_Disponivel'], config)

            # --- CÁLCULO VALOR LIBERADO (JÁ ESTAVA CORRETO COMO *) ---
            valor_liberado = (margem_ajustada * config.get('coeficiente', 1)).round(2)
            # -----------------------------------------------------
            coef_parcela = config.get('coeficiente_parcela', 1)
            if pd.isna(coef_parcela) or coef_parcela == 0: coef_parcela = 1
            valor_parcela = (valor_liberado / coef_parcela).round(2) if coef_parcela != 0 else 0.0
            comissao = (valor_liberado * (config.get('comissao',0)/100)).round(2)

            base_calc.loc[indices_para_calcular, 'valor_liberado_cartao'] = valor_liberado.fillna(0)
            base_calc.loc[indices_para_calcular, 'valor_parcela_cartao'] = valor_parcela.fillna(0)
            base_calc.loc[indices_para_calcular, 'comissao_cartao'] = comissao.fillna(0)
            base_calc.loc[indices_para_calcular, 'banco_cartao'] = config.get('banco')
            base_calc.loc[indices_para_calcular, 'prazo_cartao'] = config.get('parcelas')
            base_calc.loc[indices_para_calcular, 'tratado_cartao'] = True
        
        return base_calc
    except Exception as e:
        st.error(f"Erro em _aplicar_regras_cartao: {e}")
        return base

# ============================================
# MAPEAMENTO DE PROCESSADORES
# ============================================

PROCESSADORES = {
    ('govsp', 'Novo'): govsp_novo,
    ('govsp', 'Benefício'): govsp_beneficio, # <-- Adicionado de volta
    ('govsp', 'Cartão'): govsp_cartao, # <-- Adicionado de volta
    ('govmt', 'Novo'): govmt_novo
}

PROCESSADORES_GENERICOS = {
    'Novo': generico_novo,
    'Benefício': generico_beneficio,
    'Cartão': generico_cartao
}


# ============================================
# FINALIZAÇÃO DA BASE
# ============================================

def _finalizar_base(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    if df is None or not isinstance(df, pd.DataFrame):
        st.error("Erro interno: _finalizar_base recebeu dados inválidos.")
        return pd.DataFrame()
    if df.empty:
        st.info("Base vazia antes da finalização.")
        return pd.DataFrame()
        
    base = df.copy()
    
    # Garante colunas de valor/comissão
    for prod in ['emprestimo', 'beneficio', 'cartao']:
        for tipo in ['valor_liberado', 'comissao']:
            col = f'{tipo}_{prod}'
            if col not in base.columns: base[col] = 0.0
            base[col] = pd.to_numeric(base[col], errors='coerce').fillna(0)
            
    # Remove linhas onde TODOS os valores liberados são <= 0
    try:
        mascara_todos_zero_ou_neg = (base['valor_liberado_beneficio'] <= 0.0) & \
                                    (base['valor_liberado_cartao'] <= 0.0) & \
                                    (base['valor_liberado_emprestimo'] <= 0.0)
        base = base.loc[~mascara_todos_zero_ou_neg]

        if base.empty:
            st.warning("Nenhum cliente com valor liberado > 0 após aplicar regras.")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao remover linhas com valores zerados/negativos: {e}")
        return pd.DataFrame()

    try:
        colunas_comissao = [f'comissao_{prod}' for prod in ['emprestimo', 'beneficio', 'cartao']]
        base['comissao_total'] = base[colunas_comissao].sum(axis=1)
    except Exception as e:
        st.error(f"Erro ao calcular comissão total: {e}")
        base['comissao_total'] = 0.0

    # Cria um único expander para os logs desta função
    log_expander = st.expander("Logs de Finalização (Cortes de Comissão e Margem)", expanded=False)

    # --- INÍCIO DO LOG 5 ---
    try:
        comissao_min = params.get('comissao_minima', 0)
        comissao_max = params.get('comissao_maxima', float('inf')) 
        
        qtd_antes_comissao = len(base)
        with log_expander:
            st.write("--- LOG: Corte de Comissão ---")
            st.write(f"Linhas antes do corte de comissão: {qtd_antes_comissao}")
        
        base = base.loc[(base['comissao_total'] >= comissao_min) & (base['comissao_total'] <= comissao_max)]
        
        qtd_depois_comissao = len(base)
        with log_expander:
            st.write(f"Linhas após o corte de comissão: {qtd_depois_comissao}")
            st.write(f"Total removido (Comissão): {qtd_antes_comissao - qtd_depois_comissao}")
            st.write("--- Fim Log (Comissão) ---")
        
        if base.empty:
            st.warning("Nenhum cliente atendeu aos filtros de comissão.")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao aplicar filtro de comissão: {e}")
        return pd.DataFrame()
    # --- FIM DO LOG 5 ---

    # --- INÍCIO DO LOG 6 ---
    try:
        if 'MG_Emprestimo_Disponivel' in base.columns:
            base['MG_Emprestimo_Disponivel'] = pd.to_numeric(base['MG_Emprestimo_Disponivel'], errors='coerce')
            margem_limite = params.get('margem_limite', 20.0)
            tipo_campanha = params.get('tipo_campanha', '')

            qtd_antes_margem = len(base)
            with log_expander:
                st.write(f"--- LOG: Corte de Margem Empréstimo ---")
                st.write(f"Linhas antes do corte de margem de empréstimo: {qtd_antes_margem}")

            if tipo_campanha == 'Novo':
                with log_expander:
                    st.write(f"Filtrando para: MG_Emprestimo_Disponivel > {margem_limite}")
                base = base.loc[(base['MG_Emprestimo_Disponivel'] > margem_limite).fillna(False)]
            else:
                with log_expander:
                    st.write(f"Filtrando para: MG_Emprestimo_Disponivel <= {margem_limite}")
                base = base.loc[(base['MG_Emprestimo_Disponivel'] <= margem_limite).fillna(False)] # <= (Corrigido)
            
            qtd_depois_margem = len(base)
            with log_expander:
                st.write(f"Linhas após o corte de margem de empréstimo: {qtd_depois_margem}")
                st.write(f"Total removido (Margem): {qtd_antes_margem - qtd_depois_margem}")
                st.write(f"--- Fim Log (Margem) ---")

            if base.empty:
                st.warning("Nenhum cliente atendeu ao filtro de margem de empréstimo.")
                return pd.DataFrame()
        else:
            st.warning("Coluna 'MG_Emprestimo_Disponivel' não encontrada para filtro de margem.")
    except Exception as e:
        st.error(f"Erro ao aplicar filtro de margem de empréstimo: {e}")
        return pd.DataFrame()
    # --- FIM DO LOG 6 ---
        
    for col in ORDEM_COLUNAS_FINAL:
        if col not in base.columns:
            base[col] = pd.NA
    colunas_presentes = [col for col in ORDEM_COLUNAS_FINAL if col in base.columns]
    try:
        base = base[colunas_presentes]
        if MAPEAMENTO_COLUNAS_FINAL:
                base.rename(columns=MAPEAMENTO_COLUNAS_FINAL, inplace=True, errors='ignore')
    except Exception as e:
        st.error(f"Erro ao reordenar/renomear colunas finais: {e}")

    if 'CPF' in base.columns and not base.empty:
        base.dropna(subset=['CPF'], inplace=True)

        if not base.empty:
            try:
                if 'comissao_total' in base.columns:
                    base = base.sort_values(by='comissao_total', ascending=False, na_position='last')
                base = base.drop_duplicates(subset=['CPF'], keep='first')
            except Exception as e:
                st.error(f"Erro na deduplicação: {e}")
                if not base.empty:
                    base = base.drop_duplicates(subset=['CPF'], keep='first')

    if not base.empty:
        try:
            data_hoje = datetime.today().strftime('%d%m%Y')
            campanha_map = {'Novo': 'novo', 'Benefício': 'benef', 'Cartão': 'cartao', 'Benefício & Cartão': 'benef&cartao'}
            tipo_campanha_str = campanha_map.get(params.get('tipo_campanha'), 'campanha')
            convenio = params.get('convenio', 'geral')
            equipe = params.get('equipe', 'outbound')
            base['Campanha'] = f"{convenio}_{data_hoje}_{tipo_campanha_str}_{equipe}"

            convai_percent = params.get('convai_percent', 0)
            if convai_percent > 0:
                n_convai = int((convai_percent / 100) * len(base))
                if n_convai > 0:
                    n_convai = min(n_convai, len(base))
                    indices_convai = base.sample(n=n_convai, random_state=42).index
                    base.loc[indices_convai, 'Campanha'] = f"{convenio}_{data_hoje}_{tipo_campanha_str}_convai"
        except Exception as e:
            st.error(f"Erro ao gerar campanha/convai: {e}")

    colunas_para_remover = [
        'tratado', 'tratado_beneficio', 'tratado_cartao', 'comissao_total'
    ]
    base.drop(columns=[col for col in colunas_para_remover if col in base.columns], inplace=True, errors='ignore')

    for prod in ['emprestimo', 'beneficio', 'cartao']:
        for tipo in ['valor_liberado', 'valor_parcela', 'comissao']:
            col = f'{tipo}_{prod}'
            if col in base.columns:
                base[col] = pd.to_numeric(base[col], errors='coerce').fillna(0)
    return base


# ============================================
# FUNÇÃO PRINCIPAL
# ============================================
def aplicar_filtros(df: pd.DataFrame, params: dict, configs_banco: list):
    """Função principal que orquestra todo o processo de filtragem."""
    
    try:
        base_pre_processada = _preprocessar_base(df, params)
        if base_pre_processada.empty and not df.empty:
                st.error("Falha durante o pré-processamento.")
                return pd.DataFrame(), []
        elif base_pre_processada.empty and df.empty:
                st.warning("Base inicial vazia.")
                return pd.DataFrame(), []
                
        tipo_campanha_global = params.get('tipo_campanha')
        convenio = params.get('convenio')

        # Cria um único expander para os logs desta função
        log_expander_govsp = st.expander("Logs de Processamento (Lógica Específica GOVSP)", expanded=False)

        # --- INÍCIO DO LOG 1 & 2 ---
        with log_expander_govsp:
            st.write("--- LOG: Lógica GOVSP (Identificação) ---")
        matriculas_para_zerar_beneficio = set()
        matriculas_para_zerar_cartao = set()
        if convenio == 'govsp':
            # Garante que colunas são numéricas antes de comparar
            mg_benef_total = pd.to_numeric(base_pre_processada['MG_Beneficio_Saque_Total'], errors='coerce')
            mg_benef_disp = pd.to_numeric(base_pre_processada['MG_Beneficio_Saque_Disponivel'], errors='coerce')
            mascara_beneficio = (mg_benef_total > mg_benef_disp).fillna(False)
            matriculas_para_zerar_beneficio = set(base_pre_processada.loc[mascara_beneficio, 'Matricula'].dropna().unique())
            with log_expander_govsp:
                st.write(f"LOG: Matrículas que usaram Benefício (salvas para zerar): {len(matriculas_para_zerar_beneficio)}")

            mg_cartao_total = pd.to_numeric(base_pre_processada['MG_Cartao_Total'], errors='coerce')
            mg_cartao_disp = pd.to_numeric(base_pre_processada['MG_Cartao_Disponivel'], errors='coerce')
            mascara_cartao = (mg_cartao_total > mg_cartao_disp).fillna(False)
            matriculas_para_zerar_cartao = set(base_pre_processada.loc[mascara_cartao, 'Matricula'].dropna().unique())
            with log_expander_govsp:
                st.write(f"LOG: Matrículas que usaram Cartão (salvas para zerar): {len(matriculas_para_zerar_cartao)}")
        with log_expander_govsp:
            st.write("--- Fim Log (Identificação) ---")
        # --- FIM DO LOG 1 & 2 ---


        stats = []

        for config_idx, config in enumerate(configs_banco):
            try:
                if tipo_campanha_global == 'Benefício & Cartão':
                    produto_configurado = config.get('cartao_escolhido', 'Benefício')
                    produto_da_config = 'Cartão' if produto_configurado == 'Consignado' else 'Benefício'
                else:
                    produto_da_config = tipo_campanha_global 
                
                chave = (convenio, produto_da_config)
                func = PROCESSADORES.get(chave)
                
                if not func:
                    func = PROCESSADORES_GENERICOS.get(produto_da_config)
                    
                if func:
                    if produto_da_config == 'Benefício': produto_key = 'beneficio'
                    elif produto_da_config == 'Cartão': produto_key = 'cartao'
                    elif produto_da_config == 'Novo': produto_key = ''
                    else: produto_key = produto_da_config.lower().replace(" ", "_")

                    coluna_tratado = 'tratado' if produto_da_config == 'Novo' else f'tratado_{produto_key}'

                    if coluna_tratado not in base_pre_processada.columns:
                        st.error(f"Config {config_idx+1}: Coluna '{coluna_tratado}' ausente.")
                        continue

                    if 'CPF' in base_pre_processada.columns:
                        if pd.api.types.is_bool_dtype(base_pre_processada[coluna_tratado]):
                            cpfs_tratados_antes = set(
                                base_pre_processada.loc[base_pre_processada[coluna_tratado] == True, 'CPF'].dropna()
                            )
                        else:
                            st.warning(f"Coluna {coluna_tratado} não é booleana para stats prévias.")
                            cpfs_tratados_antes = set()
                    else:
                        cpfs_tratados_antes = set()

                    base_antes_func = base_pre_processada.copy()
                    base_pre_processada = func(base_antes_func, params, config)

                    if base_pre_processada is None or not isinstance(base_pre_processada, pd.DataFrame):
                        st.error(f"Erro Crítico: Função para {chave} retornou dados inválidos (Config {config_idx+1}). Restaurando base.")
                        base_pre_processada = base_antes_func
                        continue

                    registros_afetados_unicos = 0
                    if 'CPF' in base_pre_processada.columns:
                        if pd.api.types.is_bool_dtype(base_pre_processada[coluna_tratado]):
                            cpfs_tratados_depois = set(
                                base_pre_processada.loc[base_pre_processada[coluna_tratado] == True, 'CPF'].dropna()
                            )
                            cpfs_novos_unicos = cpfs_tratados_depois - cpfs_tratados_antes
                            registros_afetados_unicos = len(cpfs_novos_unicos)
                        else:
                            st.warning(f"Coluna {coluna_tratado} não é booleana para stats pós.")
                    else:
                        try:
                            linhas_depois = base_pre_processada[coluna_tratado].sum()
                            linhas_antes_estimado = len(cpfs_tratados_antes)
                            registros_afetados_unicos = max(0, linhas_depois - linhas_antes_estimado)
                        except Exception:
                            registros_afetados_unicos = -1

                    stats.append({
                        'banco': config.get('banco'),
                        'produto': produto_da_config,
                        'registros_afetados': registros_afetados_unicos
                    })
                else:
                    st.error(f"Config {config_idx+1}: Nenhum processador para '{produto_da_config}'.")

            except Exception as e_config:
                st.error(f"Erro processando config #{config_idx+1} ({config.get('banco')}/{produto_da_config}): {e_config}")
                import traceback
                st.code(traceback.format_exc())

        # --- INÍCIO DO LOG 3 & 4 ---
        with log_expander_govsp:
            st.write("--- LOG: Lógica GOVSP (Aplicação do Override) ---")
        if convenio == 'govsp':
            if matriculas_para_zerar_beneficio:
                mascara_zerar_b = base_pre_processada['Matricula'].isin(matriculas_para_zerar_beneficio)
                # Conta apenas os que TINHAM valor > 0 e agora serão zerados
                mascara_tinham_valor_b = (base_pre_processada['valor_liberado_beneficio'] > 0)
                qtd_zerados_b = (mascara_zerar_b & mascara_tinham_valor_b).sum()
                with log_expander_govsp:
                    st.write(f"LOG: Matrículas que tiveram valor de Benefício ZERADO: {qtd_zerados_b}")
                
                cols_b = ['valor_liberado_beneficio', 'comissao_beneficio', 'valor_parcela_beneficio']
                base_pre_processada.loc[mascara_zerar_b, cols_b] = 0.0
            else:
                with log_expander_govsp:
                    st.write("LOG: Nenhuma matrícula marcada para zerar Benefício.")
            
            if matriculas_para_zerar_cartao:
                mascara_zerar_c = base_pre_processada['Matricula'].isin(matriculas_para_zerar_cartao)
                # Conta apenas os que TINHAM valor > 0 e agora serão zerados
                mascara_tinham_valor_c = (base_pre_processada['valor_liberado_cartao'] > 0)
                qtd_zerados_c = (mascara_zerar_c & mascara_tinham_valor_c).sum()
                with log_expander_govsp:
                    st.write(f"LOG: Matrículas que tiveram valor de Cartão ZERADO: {qtd_zerados_c}")
                
                cols_c = ['valor_liberado_cartao', 'comissao_cartao', 'valor_parcela_cartao']
                base_pre_processada.loc[mascara_zerar_c, cols_c] = 0.0
            else:
                with log_expander_govsp:
                    st.write("LOG: Nenhuma matrícula marcada para zerar Cartão.")
        with log_expander_govsp:
            st.write("--- Fim Log (Aplicação) ---")
        # --- FIM DO LOG 3 & 4 ---


        if base_pre_processada.empty or (
            base_pre_processada['valor_liberado_beneficio'].fillna(0).le(0) &
            base_pre_processada['valor_liberado_cartao'].fillna(0).le(0) &
            base_pre_processada['valor_liberado_emprestimo'].fillna(0).le(0)
        ).all():
            st.warning("Nenhum valor liberado > 0 calculado.")
            return pd.DataFrame(), stats

        base_final = _finalizar_base(base_pre_processada, params)

        if base_final.empty and not base_pre_processada.empty :
                st.warning("Clientes removidos pelos filtros finais (comissão, margem, etc.).")

        return base_final, stats

    except Exception as e:
        st.error(f"Erro GERAL em aplicar_filtros: {e}")
        import traceback
        st.code(traceback.format_exc())
        return pd.DataFrame(), []