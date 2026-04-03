import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import io
import os

st.set_page_config(page_title="Controle Inteligente D&G Tech", layout="wide")

# ==========================================
# 🔴 COLE O LINK DA SUA PLANILHA AQUI ABAIXO:
# ==========================================
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1PkR-fMgs3EA6Cxa_eTgRmD-tbXzrhazR6PXn3C-SOEk/edit?gid=0#gid=0"

# --- CONEXÃO GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def carregar_base():
    try:
        # Agora o sistema sabe exatamente qual arquivo abrir
        return conn.read(spreadsheet=URL_PLANILHA, worksheet="Base_Custos_DGTech", ttl="1m")
    except:
        return pd.DataFrame(columns=['SKU', 'Produto', 'Custo Unitário'])

def salvar_base(df):
    # Agora o sistema sabe exatamente onde salvar
    conn.update(spreadsheet=URL_PLANILHA, worksheet="Base_Custos_DGTech", data=df)
    st.cache_data.clear()

if os.path.exists("Logo alta qualidade fundo azul.jpg"):
    st.image("Logo alta qualidade fundo azul.jpg", width=220)

tab1, tab2 = st.tabs(["📊 Planejador de Compras", "📦 Base de Produtos & Custos"])

# --- ABA 2: BASE DE CUSTOS ---
with tab2:
    st.subheader("Custos de Compra Armazenados")
    base_atual = carregar_base()
    
    base_editada = st.data_editor(
        base_atual, 
        num_rows="dynamic", 
        use_container_width=True,
        key="editor_central"
    )
    
    if st.button("💾 Salvar Alterações na Nuvem"):
        salvar_base(base_editada)
        st.success("Dados salvos com sucesso no Google Sheets!")

# --- ABA 1: PLANEJADOR ---
with tab1:
    st.sidebar.header("⚙️ Parâmetros")
    dias_analise = st.sidebar.number_input("Dias do relatório da Olist:", min_value=1, value=30)
    
    st.sidebar.subheader("📈 Acelerador de Tendência")
    st.sidebar.markdown("*Compensa o crescimento da empresa inflando a média de vendas diárias.*")
    fator_crescimento = st.sidebar.slider("Aceleração de Vendas (%)", 0, 50, 10)
    
    prazo_total = st.sidebar.number_input("Prazo Logístico Total (dias):", value=10)
    dias_cobertura = st.sidebar.number_input("Estoque para quantos dias?", value=30)

    uploaded_file = st.file_uploader("Suba o relatório da Olist", type=["xls", "xlsx", "csv"])

    if uploaded_file:
        try:
            df_olist = pd.read_excel(uploaded_file, engine='calamine')
            
            # Limpeza de colunas
            df_olist.columns = [str(c).strip() for c in df_olist.columns]
            
            # Busca dinâmica pelas colunas corretas
            col_sku = 'Código (SKU)'
            col_saidas = 'Saídas'
            col_saldo_final = [c for c in df_olist.columns if 'Saldo' in str(c)]
            col_saldo_final = col_saldo_final[-1] if col_saldo_final else df_olist.columns[-1]

            df_olist[col_saidas] = pd.to_numeric(df_olist[col_saidas], errors='coerce').fillna(0)
            df_olist[col_saldo_final] = pd.to_numeric(df_olist[col_saldo_final], errors='coerce').fillna(0)
            df_olist = df_olist.dropna(subset=[col_sku])

            # Sincronização Sheets
            base_custos = carregar_base()
            skus_olist = df_olist[[col_sku, 'Produto']].drop_duplicates()
            novos = skus_olist[~skus_olist[col_sku].isin(base_custos['SKU'].tolist())]
            
            if not novos.empty:
                st.warning(f"Adicionando {len(novos)} novos SKUs à base de dados...")
                novos['Custo Unitário'] = 0.0
                base_nova = pd.concat([base_custos, novos], ignore_index=True)
                salvar_base(base_nova) # Agora isso vai funcionar sem erros!
                base_custos = base_nova

            df = df_olist.merge(base_custos[['SKU', 'Custo Unitário']], left_on=col_sku, right_on='SKU', how='left')
            
            # CÁLCULOS COM FATOR DE CRESCIMENTO
            df['VMD_Pura'] = df[col_saidas] / dias_analise
            df['Venda Média Diária'] = df['VMD_Pura'] * (1 + (fator_crescimento / 100))
            
            df['Dias_Restantes'] = (df[col_saldo_final] / df['Venda Média Diária']).replace([float('inf')], 999).fillna(999).astype(int)
            df['Qtd_Sugerida'] = ((df['Venda Média Diária'] * dias_cobertura) - df[col_saldo_final]).clip(lower=0).astype(int)
            df['Total Pedido'] = df['Qtd_Sugerida'] * df['Custo Unitário']
            
            st.subheader("📋 Diagnóstico de Reposição")
            
            # Exibição
            colunas_exibir = [col_sku, 'Produto', 'Custo Unitário', col_saldo_final, 'Venda Média Diária', 'Dias_Restantes', 'Qtd_Sugerida', 'Total Pedido']
            st.dataframe(df[colunas_exibir])
            
            custo_total = df['Total Pedido'].sum()
            st.metric("Investimento Total Necessário", f"R$ {custo_total:,.2f}")

        except Exception as e:
            st.error(f"Erro ao processar: {e}")
