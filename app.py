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

# --- FUNÇÃO DE ARREDONDAMENTO POR CAIXAS FECHADAS ---
def ajustar_lote_compra(row):
    nome = str(row['Produto']).upper()
    qtd_exata = row['Qtd_Sugerida_Matematica']
    
    if qtd_exata <= 0:
        return 0
        
    if any(palavra in nome for palavra in ['UNIPOLAR', 'MONOPOLAR', '1P', '1 P']):
        multiplo = 12
    elif any(palavra in nome for palavra in ['BIPOLAR', '2P', '2 P', '2 POLOS']):
        multiplo = 6
    elif any(palavra in nome for palavra in ['TRIPOLAR', '3P', '3 P', '3 POLOS']):
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
# 🚨 RADAR DE RUPTURA
# -----------------------------------------------------
st.subheader("🚨 Radar de Ruptura Próxima")
status_atual = carregar_radar()

if not status_atual.empty and 'Data_Ruptura' in status_atual.columns:
    status_atual['Data_Ruptura'] = pd.to_datetime(status_atual['Data_Ruptura'], errors='coerce')
    hoje_dt = pd.Timestamp(datetime.now().date())
    
    risco = status_atual[status_atual['Data_Ruptura'] <= hoje_dt + timedelta(days=10)].dropna()
    
    if not risco.empty:
        cols = st.columns(len(risco) if len(risco) < 4 else 4)
        for i, (_, r) in enumerate(risco.iterrows()):
            dias_restantes = (r['Data_Ruptura'] - hoje_dt).days
            with cols[i % 4]:
                if dias_restantes < 0:
                    st.error(f"**{r['Produto']}**\n\nESTOQUE ESGOTADO!")
                else:
                    st.warning(f"**{r['Produto']}**\n\nAcaba em: {dias_restantes} dias")
    else:
        st.success("Tudo sob controle. Nenhum item em risco crítico hoje.")
else:
    st.info("Nenhum histórico encontrado. Suba um relatório e clique em 'Gravar Previsão' para iniciar o monitoramento.")

st.divider()

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
    st.sidebar.header("⚙️ Parâmetros de Tempo")
    col1, col2 = st.sidebar.columns(2)
    
    hoje = datetime.today()
    trinta_dias_atras = hoje - timedelta(days=30)
    
    data_inicio = col1.date_input("De", value=trinta_dias_atras)
    data_fim = col2.date_input("Até", value=hoje)
    
    dias_analise = (data_fim - data_inicio).days + 1
    
    if dias_analise <= 0:
        st.sidebar.error("A data final deve ser maior que a inicial.")
        dias_analise = 1
    else:
        st.sidebar.info(f"O sistema usará **{dias_analise} dias** para calcular a VMD.")

    st.sidebar.divider()
    fator_crescimento = st.sidebar.slider("Aceleração de Vendas (%)", 0, 50, 10)
    prazo_total = st.sidebar.number_input("Prazo Logístico Total (dias):", value=10)
    dias_cobertura = st.sidebar.number_input("Estoque para quantos dias?", value=30)

    uploaded_file = st.file_uploader("Suba o relatório da Olist", type=["xlsx", "xls", "csv"])

    if uploaded_file:
        try:
            df_olist = pd.read_excel(uploaded_file, engine='calamine')
            df_olist.columns = [str(c).strip() for c in df_olist.columns]
            
            col_sku = 'Código (SKU)'
            col_saidas = 'Saídas'
            col_saldo_final = [c for c in df_olist.columns if 'Saldo' in str(c)]
            col_saldo_final = col_saldo_final[-1] if col_saldo_final else df_olist.columns[-1]

            df_olist = df_olist.dropna(subset=[col_sku])
            
            df_olist[col_sku] = df_olist[col_sku].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
            df_olist[col_saidas] = pd.to_numeric(df_olist[col_saidas], errors='coerce').fillna(0)
            df_olist[col_saldo_final] = pd.to_numeric(df_olist[col_saldo_final], errors='coerce').fillna(0)

            base_custos = carregar_base()
            base_custos['Código (SKU)'] = base_custos['Código (SKU)'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
            
            skus_olist = df_olist[[col_sku, 'Produto']].drop_duplicates()
            novos = skus_olist[~skus_olist[col_sku].isin(base_custos['Código (SKU)'].tolist())]
            
            if not novos.empty:
                st.warning(f"Adicionando {len(novos)} novos SKUs à base de dados...")
                novos['Custo Unitário'] = 0.0
                base_nova = pd.concat([base_custos, novos], ignore_index=True)
                salvar_base(base_nova)
                base_custos = base_nova

            df = df_olist.merge(base_custos[['Código (SKU)', 'Custo Unitário']], on='Código (SKU)', how='left')
            
            df['VMD_Pura'] = df[col_saidas] / dias_analise
            df['Venda Média Diária'] = df['VMD_Pura'] * (1 + (fator_crescimento / 100))
            df['Dias_Restantes'] = (df[col_saldo_final] / df['Venda Média Diária']).replace([float('inf')], 999).fillna(999).astype(int)
            
            df['Data_Ruptura'] = [datetime.now().date() + timedelta(days=min(d, 365)) for d in df['Dias_Restantes']]
            
            df['Qtd_Sugerida_Matematica'] = ((df['Venda Média Diária'] * dias_cobertura) - df[col_saldo_final]).clip(lower=0).astype(int)
            df['Qtd_Sugerida'] = df.apply(ajustar_lote_compra, axis=1)
            df['Total Pedido'] = df['Qtd_Sugerida'] * df['Custo Unitário']
            
            st.subheader("📋 Diagnóstico de Reposição")
            colunas_exibir = [col_sku, 'Produto', 'Custo Unitário', col_saldo_final, 'Venda Média Diária', 'Dias_Restantes', 'Data_Ruptura', 'Qtd_Sugerida', 'Total Pedido']
            st.dataframe(df[colunas_exibir])
            
            custo_total = df['Total Pedido'].sum()
            st.metric("Investimento Total Necessário", f"R$ {custo_total:,.2f}")

            # GRAVAR RADAR
            if st.button("📌 Gravar Previsão no Radar"):
                previsao = df[['Produto', 'Data_Ruptura']].copy()
                previsao['Data_Ruptura'] = previsao['Data_Ruptura'].astype(str)
                salvar_radar(previsao)
                st.success("Radar atualizado com sucesso no Google Sheets! Recarregue a página para ver no topo.")

            st.divider()
            df_compra = df[df['Qtd_Sugerida'] > 0].copy()
            
            if not df_compra.empty:
                texto_wpp = "*PEDIDO DE COMPRA - D&G TECH*\n\n"
                for _, row in df_compra.iterrows():
                    texto_wpp += f"📦 *{row['Produto']}*\n"
                    texto_wpp += f"Quantidade: *{row['Qtd_Sugerida']} unidades*\n"
                    texto_wpp += "----------------------------\n"
                
                texto_wpp += f"\n💰 *Estimativa de Custo:* R$ {custo_total:,.2f}\n"
                texto_wpp += f"_Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}_"
                
                link_wpp = f"https://api.whatsapp.com/send?text={urllib.parse.quote(texto_wpp)}"
                st.markdown(f'<a href="{link_wpp}" target="_blank"><button style="background-color:#25D366; color:white; border:none; padding:12px 24px; border-radius:8px; cursor:pointer; font-weight:bold; font-size:16px;">🟢 Enviar Pedido para o Fornecedor (WhatsApp)</button></a>', unsafe_allow_html=True)
            else:
                st.success("Estoque em dia! Nenhuma compra necessária.")

        except Exception as e:
            st.error(f"Erro ao processar: {e}")
