import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta
import io
import urllib.parse
import os

st.set_page_config(page_title="Controle Inteligente D&G Tech", layout="wide")

# --- CONEXÃO GOOGLE SHEETS (BANCO DE DADOS ETERNO) ---
conn = st.connection("gsheets", type=GSheetsConnection)

def carregar_base():
    try:
        # Tenta ler a planilha; se não existir, cria estrutura básica
        return conn.read(worksheet="Base_Custos_DGTech", ttl="1m")
    except:
        return pd.DataFrame(columns=['SKU', 'Produto', 'Custo Unitário'])

def salvar_base(df):
    conn.update(worksheet="Base_Custos", data=df)
    st.cache_data.clear()

# --- LOGO E ESTILO ---
if os.path.exists("Logo alta qualidade fundo azul.jpg"):
    st.image("Logo alta qualidade fundo azul.jpg", width=220)

tab1, tab2 = st.tabs(["📊 Planejador de Compras", "📦 Base de Produtos & Custos"])

# --- ABA 2: BASE DE PRODUTOS (ONDE TUDO FICA SALVO) ---
with tab2:
    st.subheader("Custos de Compra Armazenados")
    base_atual = carregar_base()
    
    # Editor interativo que salva no Google Sheets
    base_editada = st.data_editor(
        base_atual, 
        num_rows="dynamic", 
        use_container_width=True,
        key="editor_central"
    )
    
    if st.button("💾 Salvar Alterações na Nuvem"):
        salvar_base(base_editada)
        st.success("Dados salvos com sucesso no Google Sheets!")

# --- ABA 1: PLANEJADOR COM TENDÊNCIA DE CRESCIMENTO ---
with tab1:
    st.sidebar.header("⚙️ Parâmetros de Estoque")
    dias_analise = st.sidebar.number_input("Dias do relatório (ex: 7 ou 30):", min_value=1, value=7)
    
    # NOVO: Fator de Tendência para substituir a média simples
    st.sidebar.subheader("📈 Projeção de Crescimento")
    fator_crescimento = st.sidebar.slider("Tendência de Crescimento (%)", 0, 50, 10)
    st.sidebar.caption("Aumenta a VMD com base na expansão da empresa.")
    
    prazo_total = st.sidebar.number_input("Prazo Total Fornecedor + Logística (dias):", value=10)
    dias_cobertura = st.sidebar.number_input("Estoque para quantos dias?", value=30)

    uploaded_file = st.file_uploader("Suba o relatório da Olist", type=["xlsx", "csv"])

    if uploaded_file:
        df_olist = pd.read_excel(uploaded_file, engine='calamine')
        # ... (Limpeza de colunas como fizemos antes) ...
        
        # 1. Sincronização Automática com a Base do Sheets
        base_custos = carregar_base()
        skus_olist = df_olist[['Código (SKU)', 'Produto']].drop_duplicates()
        novos = skus_olist[~skus_olist['Código (SKU)'].isin(base_custos['SKU'].tolist())]
        
        if not novos.empty:
            st.warning(f"Identificamos {len(novos)} novos SKUs. Adicionando à base...")
            novos['Custo Unitário'] = 0.0
            base_nova = pd.concat([base_custos, novos], ignore_index=True)
            salvar_base(base_nova)
            base_custos = base_nova

        # 2. Cruzamento de Dados
        df = df_olist.merge(base_custos[['SKU', 'Custo Unitário']], left_on='Código (SKU)', right_on='SKU', how='left')
        
        # 3. CÁLCULOS COM TENDÊNCIA (Média Exponencial Adaptada)
        # VMD Simples
        df['VMD_Base'] = df['Saídas'] / dias_analise
        # VMD com Tendência de Crescimento
        df['Venda Média Diária'] = df['VMD_Base'] * (1 + (fator_crescimento / 100))
        
        df['Dias_Restantes'] = (df['Saldo'] / df['Venda Média Diária']).fillna(999).astype(int)
        df['Qtd_Sugerida'] = ((df['Venda Média Diária'] * dias_cobertura) - df['Saldo']).clip(lower=0).astype(int)
        
        # 4. EXIBIÇÃO E FINANCEIRO
        st.subheader("Diagnóstico de Reposição")
        df['Total Pedido'] = df['Qtd_Sugerida'] * df['Custo Unitário']
        
        st.dataframe(df[['SKU', 'Produto', 'Custo Unitário', 'Venda Média Diária', 'Dias_Restantes', 'Qtd_Sugerida', 'Total Pedido']])
        
        custo_total = df['Total Pedido'].sum()
        st.metric("Investimento Total Necessário", f"R$ {custo_total:,.2f}")

        # ... (Botões de WhatsApp e Excel permanecem iguais) ...
