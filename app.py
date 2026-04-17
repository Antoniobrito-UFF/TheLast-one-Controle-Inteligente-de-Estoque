import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta
import urllib.parse
import os

st.set_page_config(page_title="Controle Inteligente D&G Tech", layout="wide")

# ==========================================
# 🔴 LINK DA SUA PLANILHA:
# ==========================================
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1PkR-fMgs3EA6Cxa_eTgRmD-tbXzrhazR6PXn3C-SOEk/edit?gid=1319897969#gid=1319897969"

# --- CONEXÃO GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def carregar_base():
    try:
        return conn.read(spreadsheet=URL_PLANILHA, worksheet="Base_Custos", ttl="1m")
    except:
        return pd.DataFrame(columns=['Código (SKU)', 'Produto', 'Custo Unitário'])

def salvar_base(df):
    conn.update(spreadsheet=URL_PLANILHA, worksheet="Base_Custos", data=df)
    st.cache_data.clear()

def carregar_radar():
    try:
        return conn.read(spreadsheet=URL_PLANILHA, worksheet="Status_Estoque", ttl="1m")
    except:
        return pd.DataFrame()

def salvar_radar(df):
    conn.update(spreadsheet=URL_PLANILHA, worksheet="Status_Estoque", data=df)
    st.cache_data.clear()

# --- FUNÇÃO DE ARREDONDAMENTO (CORREÇÃO DE PALABRA -> PALAVRA) ---
def ajustar_lote_compra(row):
    nome = str(row['Produto']).upper()
    qtd_exata = row['Qtd_Sugerida_Matematica']
    
    if qtd_exata <= 0:
        return 0
        
    if any(p in nome for p in ['UNIPOLAR', 'MONOPOLAR', '1P', '1 P']):
        multiplo = 12
    elif any(p in nome for p in ['BIPOLAR', '2P', '2 P', '2 POLOS']):
        multiplo = 6
    elif any(p in nome for p in ['TRIPOLAR', '3P', '3 P', '3 POLOS']):
        multiplo = 3
    else:
        return int(qtd_exata)
        
    if qtd_exata < multiplo:
        return 0 
    else:
        return int(((qtd_exata + multiplo - 1) // multiplo) * multiplo)

if os.path.exists("Logo alta qualidade fundo azul.jpg"):
    st.image("Logo alta qualidade fundo azul.jpg", width=220)

# -----------------------------------------------------
# 🚨 RADAR DE RUPTURA (CORREÇÃO DE SINTAXE)
# -----------------------------------------------------
st.subheader("🚨 Radar de Ruptura Próxima")
status_atual = carregar_radar()

if not status_atual.empty and 'Data_Ruptura' in status_atual.columns:
    status_atual['Data_Ruptura'] = pd.to_datetime(status_atual['Data_Ruptura'], errors='coerce')
    hoje_dt = pd.Timestamp(datetime.now().date())
    
    if 'Data_Limite_Compra' in status_atual.columns:
        status_atual['Data_Limite_Compra'] = pd.to_datetime(status_atual['Data_Limite_Compra'], errors='coerce')
        # Filtro corrigido para evitar erro de sintaxe
        risco = status_atual[hoje_dt >= status_atual['Data_Limite_Compra']].dropna()
    else:
        risco = status_atual[status_atual['Data_Ruptura'] <= hoje_dt + timedelta(days=10)].dropna()
    
    if not risco.empty:
        cols = st.columns(len(risco) if len(risco) < 4 else 4)
        for i, (_, r) in enumerate(risco.iterrows()):
            dias_restantes = (r['Data_Ruptura'] - hoje_dt).days
            with cols[i % 4]:
                if dias_restantes <= 0:
                    st.error(f"**{r['Produto']}**\n\nESTOQUE ESGOTADO!")
                else:
                    st.warning(f"**{r['Produto']}**\n\n⚠️ Ação Necessária!\nAcaba em: {dias_restantes} dias")
    else:
        st.success("Tudo sob controle. Nenhum item atingiu o ponto de pedido hoje.")
else:
    st.info("Nenhum histórico encontrado. Suba um relatório para iniciar.")

st.divider()

tab1, tab2 = st.tabs(["📊 Planejador de Compras", "📦 Base de Produtos & Custos"])

with tab2:
    st.subheader("Custos de Compra Armazenados")
    base_atual = carregar_base()
    base_editada = st.data_editor(base_atual, num_rows="dynamic", use_container_width=True, key="editor_central")
    if st.button("💾 Salvar Alterações na Nuvem"):
        salvar_base(base_editada)
        st.success("Dados salvos!")

with tab1:
    st.sidebar.header("⚙️ Parâmetros")
    hoje = datetime.today()
    data_inicio = st.sidebar.date_input("Início da Análise", value=hoje - timedelta(days=30))
    data_fim = st.sidebar.date_input("Fim da Análise", value=hoje)
    dias_analise = (data_fim - data_inicio).days + 1
    
    fator_crescimento = st.sidebar.slider("Crescimento (%)", 0, 50, 10)
    prazo_total = st.sidebar.number_input("Prazo de Entrega (dias):", value=10)
    dias_cobertura = st.sidebar.number_input("Cobertura desejada (dias):", value=30)

    uploaded_file = st.file_uploader("Suba o relatório da Olist", type=["xlsx", "xls", "csv"])

    if uploaded_file:
        try:
            df_olist = pd.read_excel(uploaded_file, engine='calamine')
            df_olist.columns = [str(c).strip() for c in df_olist.columns]
            
            col_sku = 'Código (SKU)'
            col_saidas = 'Saídas'
            col_saldo_final = [c for c in df_olist.columns if 'Saldo' in str(c)][-1]

            # --- TRATAMENTO: CONVERTE NEGATIVOS EM ZERO ---
            df_olist[col_sku] = df_olist[col_sku].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
            df_olist[col_saidas] = pd.to_numeric(df_olist[col_saidas], errors='coerce').fillna(0)
            
            # Aqui está o segredo: .clip(lower=0) transforma qualquer valor menor que zero em zero
            df_olist[col_saldo_final] = pd.to_numeric(df_olist[col_saldo_final], errors='coerce').fillna(0).clip(lower=0)

            base_custos = carregar_base()
            base_custos['Código (SKU)'] = base_custos['Código (SKU)'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
            
            df = df_olist.merge(base_custos[['Código (SKU)', 'Custo Unitário']], on=col_sku, how='left')
            
            df['VMD_Pura'] = df[col_saidas] / dias_analise
            df['Venda Média Diária'] = df['VMD_Pura'] * (1 + (fator_crescimento / 100))
            
            # Cálculo de dias restantes (mínimo 0)
            df['Dias_Restantes'] = (df[col_saldo_final] / df['Venda Média Diária']).replace([float('inf')], 999).fillna(0)
            df['Dias_Restantes'] = df['Dias_Restantes'].clip(lower=0).astype(int)
            
            df['Data_Ruptura'] = [datetime.now().date() + timedelta(days=min(d, 365)) for d in df['Dias_Restantes']]
            df['Data_Limite_Compra'] = [d - timedelta(days=int(prazo_total)) for d in df['Data_Ruptura']]
            
            # Cálculo da quantidade sugerida (mínimo 0)
            df['Qtd_Sugerida_Matematica'] = ((df['Venda Média Diária'] * dias_cobertura) - df[col_saldo_final]).clip(lower=0).astype(int)
            df['Qtd_Sugerida'] = df.apply(ajustar_lote_compra, axis=1)
            df['Total Pedido'] = df['Qtd_Sugerida'] * df['Custo Unitário']
            
            st.subheader("📋 Sugestão de Compras")
            st.dataframe(df[[col_sku, 'Produto', 'Custo Unitário', col_saldo_final, 'Dias_Restantes', 'Data_Limite_Compra', 'Data_Ruptura', 'Qtd_Sugerida', 'Total Pedido']])
            
            st.metric("Total do Pedido", f"R$ {df['Total Pedido'].sum():,.2f}")

            if st.button("📌 Salvar Previsão no Radar"):
                previsao = df[['Produto', 'Data_Ruptura', 'Data_Limite_Compra']].copy()
                previsao['Data_Ruptura'] = previsao['Data_Ruptura'].astype(str)
                previsao['Data_Limite_Compra'] = previsao['Data_Limite_Compra'].astype(str)
                salvar_radar(previsao)
                st.success("Radar atualizado! Negativos ignorados.")

        except Exception as e:
            st.error(f"Erro ao processar: {e}")
