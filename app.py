import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta
import urllib.parse
import os

st.set_page_config(page_title="D&G Tech - Inteligência de Estoque", layout="wide")

URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1PkR-fMgs3EA6Cxa_eTgRmD-tbXzrhazR6PXn3C-SOEk/edit?gid=0#gid=0"

conn = st.connection("gsheets", type=GSheetsConnection)

# --- FUNÇÕES DE BANCO DE DADOS ---
def carregar_base(aba="Base_Custos"):
    try:
        return conn.read(spreadsheet=URL_PLANILHA, worksheet=aba, ttl="1m")
    except:
        return pd.DataFrame()

def salvar_dados(df, aba):
    conn.update(spreadsheet=URL_PLANILHA, worksheet=aba, data=df)
    st.cache_data.clear()

def ajustar_lote_compra(row):
    nome = str(row['Produto']).upper()
    qtd_exata = row['Qtd_Sugerida_Matematica']
    if qtd_exata <= 0: return 0
    
    if any(p in nome for p in ['UNIPOLAR', 'MONOPOLAR', '1P']): multiplo = 12
    elif any(p in nome for p in ['BIPOLAR', '2P']): multiplo = 6
    elif any(p in nome for p in ['TRIPOLAR', '3P']): multiplo = 3
    else: return int(qtd_exata)
    
    return 0 if qtd_exata < multiplo else int(((qtd_exata + multiplo - 1) // multiplo) * multiplo)

# --- INTERFACE ---
if os.path.exists("Logo alta qualidade fundo azul.jpg"):
    st.image("Logo alta qualidade fundo azul.jpg", width=180)

# -----------------------------------------------------
# 🚨 NOVO: PAINEL DE ALERTAS ATIVOS (Lê do Banco de Dados)
# -----------------------------------------------------
st.subheader("🚨 Radar de Ruptura Próxima")
status_atual = carregar_base("Status_Estoque")

if not status_atual.empty:
    # Filtra apenas quem acaba nos próximos 10 dias (ou já acabou)
    status_atual['Data_Ruptura'] = pd.to_datetime(status_atual['Data_Ruptura'], errors='coerce')
    hoje_dt = pd.Timestamp(datetime.now().date())
    risco = status_atual[status_atual['Data_Ruptura'] <= hoje_dt + timedelta(days=10)]
    
    if not risco.empty:
        for _, r in risco.iterrows():
            dias_que_faltam = (r['Data_Ruptura'] - hoje_dt).days
            msg = f"Acaba em {dias_que_faltam} dias" if dias_que_faltam > 0 else "ESTOQUE ESGOTADO!"
            st.warning(f"**{r['Produto']}**: {msg} (Previsão: {r['Data_Ruptura'].strftime('%d/%m')})")
    else:
        st.success("Tudo sob controle. Nenhum item em risco crítico hoje.")
else:
    st.info("Nenhum histórico de estoque encontrado. Suba um relatório para iniciar o monitoramento.")

st.divider()

tab1, tab2 = st.tabs(["📊 Analisar Novo Relatório", "📦 Gestão de Custos"])

with tab2:
    base_custos = carregar_base("Base_Custos")
    base_editada = st.data_editor(base_custos, num_rows="dynamic", use_container_width=True)
    if st.button("💾 Salvar Custos"):
        salvar_dados(base_editada, "Base_Custos")

with tab1:
    st.sidebar.header("⚙️ Configurações")
    data_inicio = st.sidebar.date_input("Início Relatório Olist", datetime.today() - timedelta(days=28))
    data_fim = st.sidebar.date_input("Fim Relatório Olist", datetime.today())
    dias_analise = max(1, (data_fim - data_inicio).days + 1)
    
    fator_crescimento = st.sidebar.slider("Tendência de Crescimento (%)", 0, 50, 10)
    prazo_entrega = st.sidebar.number_input("Dias para a mercadoria chegar:", value=7)
    dias_cobertura = st.sidebar.number_input("Comprar estoque para quantos dias?", value=30)

    uploaded_file = st.file_uploader("Suba o Excel da Olist")

    if uploaded_file:
        try:
            df_olist = pd.read_excel(uploaded_file, engine='calamine')
            df_olist.columns = [str(c).strip() for c in df_olist.columns]
            
            col_sku = 'Código (SKU)'
            col_saidas = 'Saídas'
            col_saldo = [c for c in df_olist.columns if 'Saldo' in str(c)][-1]

            df_olist[col_sku] = df_olist[col_sku].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
            df_olist[col_saidas] = pd.to_numeric(df_olist[col_saidas], errors='coerce').fillna(0)
            df_olist[col_saldo] = pd.to_numeric(df_olist[col_saldo], errors='coerce').fillna(0)

            base_custos = carregar_base("Base_Custos")
            base_custos['Código (SKU)'] = base_custos['Código (SKU)'].astype(str).str.strip()
            
            df = df_olist.merge(base_custos[['Código (SKU)', 'Custo Unitário']], on=col_sku, how='left')
            
            # Cálculos
            df['VMD'] = (df[col_saidas] / dias_analise) * (1 + (fator_crescimento / 100))
            
            # Data de Ruptura: Hoje + (Saldo / VMD)
            df['Dias_Ate_Acabar'] = (df[col_saldo] / df['VMD']).fillna(0).astype(int)
            df['Data_Ruptura'] = [datetime.now().date() + timedelta(days=d) for d in df['Dias_Ate_Acabar']]
            
            df['Qtd_Sugerida_Matematica'] = ((df['VMD'] * (dias_cobertura + prazo_entrega)) - df[col_saldo]).clip(lower=0).astype(int)
            df['Qtd_Final'] = df.apply(ajustar_lote_compra, axis=1)
            
            st.dataframe(df[['Produto', col_saldo, 'VMD', 'Data_Ruptura', 'Qtd_Final']])

            # --- SALVAR STATUS NO BANCO DE DADOS ---
            if st.button("📌 Gravar Previsão no Sistema"):
                historico = df[['Produto', 'Data_Ruptura']].copy()
                historico['Data_Ruptura'] = historico['Data_Ruptura'].astype(str)
                salvar_dados(historico, "Status_Estoque")
                st.success("Previsão gravada! O radar e o e-mail automático agora estão atualizados.")

            # WhatsApp (Mesma lógica anterior...)
            # ... [Botão WhatsApp aqui] ...

        except Exception as e:
            st.error(f"Erro: {e}")
