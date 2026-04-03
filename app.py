import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import urllib.parse
import os

st.set_page_config(page_title="Controle D&G Tech - Compras", layout="wide")

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

# --- FUNÇÃO DE AJUSTE DE LOTE (NOVA REGRA) ---
def ajustar_lote_compra(row):
    nome = str(row['Produto']).upper()
    qtd_bruta = row['Qtd_Sugerida_Bruta']
    
    # Define o múltiplo com base no nome
    if 'UNIPOLAR' in nome:
        multiplo = 12
    elif 'BIPOLAR' in nome:
        multiplo = 6
    elif 'TRIPOLAR' in nome:
        multiplo = 3
    else:
        return int(max(0, qtd_bruta)) # Itens sem regra específica
    
    # Regra: Se for menor que o lote, não compra (zero)
    if qtd_bruta < multiplo:
        return 0
    else:
        # Arredonda para cima para o próximo múltiplo da caixa
        return int(((qtd_bruta + multiplo - 1) // multiplo) * multiplo)

# Alerta de Sexta-feira
if datetime.now().weekday() == 4:
    st.error("🚨 **ALERTA DE SEXTA-FEIRA:** Gere o relatório Olist de 28 dias!")

if os.path.exists("Logo alta qualidade fundo azul.jpg"):
    st.image("Logo alta qualidade fundo azul.jpg", width=220)

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
    col1, col2 = st.sidebar.columns(2)
    data_inicio = col1.date_input("De")
    data_fim = col2.date_input("Até")
    dias_analise = (data_fim - data_inicio).days + 1
    
    fator_crescimento = st.sidebar.slider("Aceleração de Vendas (%)", 0, 50, 10)
    dias_cobertura = st.sidebar.number_input("Estoque para quantos dias?", value=30)

    uploaded_file = st.file_uploader("Suba o relatório da Olist", type=["xls", "xlsx", "csv"])

    if uploaded_file:
        try:
            df_olist = pd.read_excel(uploaded_file, engine='calamine')
            df_olist.columns = [str(c).strip() for c in df_olist.columns]
            
            col_sku = 'Código (SKU)'
            col_saidas = 'Saídas'
            col_saldo_final = [c for c in df_olist.columns if 'Saldo' in str(c)]
            col_saldo_final = col_saldo_final[-1] if col_saldo_final else df_olist.columns[-1]

            df_olist = df_olist.dropna(subset=[col_sku])
            df_olist[col_sku] = df_olist[col_sku].astype(str).str.strip()
            df_olist[col_saidas] = pd.to_numeric(df_olist[col_saidas], errors='coerce').fillna(0)
            df_olist[col_saldo_final] = pd.to_numeric(df_olist[col_saldo_final], errors='coerce').fillna(0)

            base_custos = carregar_base()
            base_custos['Código (SKU)'] = base_custos['Código (SKU)'].astype(str).str.strip()
            
            # Sincronização de novos itens
            skus_olist = df_olist[[col_sku, 'Produto']].drop_duplicates()
            novos = skus_olist[~skus_olist[col_sku].isin(base_custos['Código (SKU)'].tolist())]
            if not novos.empty:
                novos['Custo Unitário'] = 0.0
                base_nova = pd.concat([base_custos, novos], ignore_index=True)
                salvar_base(base_nova)
                base_custos = base_nova

            df = df_olist.merge(base_custos[['Código (SKU)', 'Custo Unitário']], on='Código (SKU)', how='left')
            
            # Cálculos de demanda
            df['VMD'] = (df[col_saidas] / (dias_analise if dias_analise > 0 else 1)) * (1 + (fator_crescimento / 100))
            df['Qtd_Sugerida_Bruta'] = (df['VMD'] * dias_cobertura) - df[col_saldo_final]
            
            # APLICAÇÃO DA REGRA DE LOTE (MULTIPLOS)
            df['Qtd_Sugerida'] = df.apply(ajustar_lote_compra, axis=1)
            df['Total Pedido'] = df['Qtd_Sugerida'] * df['Custo Unitário']
            
            st.subheader("📋 Diagnóstico de Reposição (Ajustado por Lote)")
            st.dataframe(df[['Produto', col_saldo_final, 'Qtd_Sugerida', 'Total Pedido']])
            
            custo_total = df['Total Pedido'].sum()
            st.metric("Investimento Total", f"R$ {custo_total:,.2f}")

            # --- MENSAGEM WHATSAPP MELHORADA ---
            st.divider()
            df_compra = df[df['Qtd_Sugerida'] > 0].copy()
            
            if not df_compra.empty:
                texto_wpp = "*PEDIDO DE COMPRA - D&G TECH*\n\n"
                for _, row in df_compra.iterrows():
                    # Formato mais visível e organizado para o fornecedor
                    texto_wpp += f"📦 *{row['Produto']}*\n"
                    texto_wpp += f"Quantidade: *{row['Qtd_Sugerida']} unidades*\n"
                    texto_wpp += "----------------------------\n"
                
                texto_wpp += f"\n💰 *Custo Estimado:* R$ {custo_total:,.2f}"
                
                link_wpp = f"https://api.whatsapp.com/send?text={urllib.parse.quote(texto_wpp)}"
                st.markdown(f'<a href="{link_wpp}" target="_blank"><button style="background-color:#25D366; color:white; border:none; padding:12px 24px; border-radius:8px; cursor:pointer; font-weight:bold; font-size:16px;">🟢 Enviar Pedido para o Fornecedor (WhatsApp)</button></a>', unsafe_allow_html=True)
            else:
                st.success("Estoque saudável. Nenhuma caixa fechada precisa ser comprada agora.")

        except Exception as e:
            st.error(f"Erro no processamento: {e}")
