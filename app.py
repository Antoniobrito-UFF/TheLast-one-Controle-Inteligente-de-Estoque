import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta
import urllib.parse
import os

st.set_page_config(page_title="Controle Inteligente D&G Tech", layout="wide")

# ==========================================
# 🔴 COLE O LINK (URL) DA SUA PLANILHA AQUI:
# ==========================================
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1PkR-fMgs3EA6Cxa_eTgRmD-tbXzrhazR6PXn3C-SOEk/edit?gid=0#gid=0"

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

# --- NOVAS FUNÇÕES PARA O RADAR DE ESTOQUE ---
def carregar_radar():
    try:
        return conn.read(spreadsheet=URL_PLANILHA, worksheet="Status_Estoque", ttl="1m")
    except:
        return pd.DataFrame()

def salvar_radar(df):
    conn.update(spreadsheet=URL_PLANILHA, worksheet="Status_Estoque", data=df)
    st.cache_data.clear()

# --- FUNÇÃO DE ARREDONDAMENTO POR CAIXAS FECHADAS ---
def ajustar_lote_compra(row):
    nome = str(row['Produto']).upper()
    qtd_exata = row['Qtd_Sugerida_Matematica']
    
    if qtd_exata <= 0:
        return 0
        
    # Radar inteligente para capturar variações no nome do produto
    if any(palavra in nome for palavra in ['UNIPOLAR', 'MONOPOLAR', '1P', '1 P']):
        multiplo = 12
    elif any(palavra in nome for palavra in ['BIPOLAR', '2P', '2 P', '2 POLOS']):
        multiplo = 6
    elif any(palavra in nome for palavra in ['TRIPOLAR', '3P', '3 P', '3 POLOS']):
        multiplo = 3
    else:
        return int(qtd_exata) # Itens que não são disjuntores mantêm o valor normal
        
    # Regra da Caixa Fechada
    if qtd_exata < multiplo:
        return 0 # Se precisa de menos que uma caixa, zera a compra
    else:
        # Arredonda sempre para cima, para o próximo múltiplo da caixa
        return int(((qtd_exata + multiplo - 1) // multiplo) * multiplo)

# --- ALERTA DE SEXTA-FEIRA NO SITE ---
if datetime.now().weekday() == 4:
    st.error("🚨 **ALERTA DE SEXTA-FEIRA:** Lembre-se de subir o relatório Olist de 4 semanas (28 dias) para planejar a próxima semana!")

if os.path.exists("Logo alta qualidade fundo azul.jpg"):
    st.image("Logo alta qualidade fundo azul.jpg", width=220)

# -----------------------------------------------------
# 🚨 NOVO: RADAR DE RUPTURA (Aparece logo no topo do site)
# -----------------------------------------------------
st.subheader("🚨 Radar de Ruptura Próxima")
status_atual = carregar_radar()

if not status_atual.empty:
    status_atual['Data_Ruptura'] = pd.to_datetime(status_atual['Data_Ruptura'], errors='coerce')
    hoje_dt = pd.Timestamp(datetime.now().date())
    
    # Puxa quem acaba nos próximos 10 dias
    risco = status_atual[status_atual['
