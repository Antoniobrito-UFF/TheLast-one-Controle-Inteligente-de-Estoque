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

# --- FUNÇÃO DE ARREDONDAMENTO POR CAIXAS FECHADAS ---
def ajustar_lote_compra(row):
    nome = str(row['Produto']).upper()
    # Pega a quantidade matemática exata que já foi calculada e clipada em zero
    qtd_exata = row['Qtd_Sugerida_Matematica']
    
    if qtd_exata <= 0:
        return 0
        
    if 'UNIPOLAR' in nome:
        multiplo = 12
    elif 'BIPOLAR' in nome:
        multiplo = 6
    elif 'TRIPOLAR' in nome:
        multiplo = 3
    else:
        return int(qtd_exata) # Se não for disjuntor, mantém o valor normal
        
    # Regras para os disjuntores:
    if qtd_exata < multiplo:
        return 0 # Se precisa de menos que uma caixa, não compra
    else:
        # Arredonda para cima, para o próximo múltiplo da caixa
        return int(((qtd_exata + multiplo - 1) // multiplo) * multiplo)

# --- ALERTA DE SEXTA-FEIRA NO SITE ---
if datetime.now().weekday() == 4:
    st.error("🚨 **ALERTA DE SEXTA-FEIRA:** Lembre-se de subir o relatório Olist de 4 semanas (28 dias) para planejar a próxima semana!")

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
    st.sidebar.header("⚙️ Parâmetros de Tempo")
    
    st.sidebar.markdown("**Selecione o exato intervalo puxado na Olist:**")
    col1, col2 = st.sidebar.columns(2)
    
    # 🛡️ CORREÇÃO: Definindo um padrão de 30 dias para evitar o erro dos R$ 66.000
    hoje = datetime.today()
    trinta_dias_atras = hoje - timedelta(days=30)
    
    data_inicio = col1.date_input("De", value=trinta_dias_atras)
    data_fim = col2.date_input("Até", value=hoje)
    
    # Calcula quantos dias tem entre as datas selecionadas (+1 para incluir o dia de hoje)
    dias_analise = (data_fim - data_inicio).days + 1
    
    if dias_analise <= 0:
        st.sidebar.error("A data final deve ser maior que a inicial.")
        dias_analise = 1 # Evitar divisão por zero e travar o código
    else:
        st.sidebar.info(f"O sistema usará **{dias_analise} dias** para calcular a Venda Média Diária.")

    st.sidebar.divider()
    st.sidebar.subheader("📈 Acelerador de Tendência")
    fator_crescimento = st.sidebar.slider("Aceleração de Vendas (%)", 0, 50, 10)
    
    prazo_total = st.sidebar.number_input("Prazo Logístico Total (dias):", value=10)
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
            
            skus_olist = df_olist[[col_sku, 'Produto']].drop_duplicates()
            novos = skus_olist[~skus_olist[col_sku].isin(base_custos['Código (SKU)'].tolist())]
            
            if not novos.empty:
                st.warning(f"Adicionando {len(novos)} novos SKUs à base de dados...")
                novos['Custo Unitário'] = 0.0
                base_nova = pd.concat([base_custos, novos], ignore_index=True)
                salvar_base(base_nova)
                base_custos = base_nova

            df = df_olist.merge(base_custos[['Código (SKU)', 'Custo Unitário']], on='Código (SKU)', how='left')
            
            # --- CÁLCULO SEGURO ---
            df['VMD_Pura'] = df[col_saidas] / dias_analise
            df['Venda Média Diária'] = df['VMD_Pura'] * (1 + (fator_crescimento / 100))
            df['Dias_Restantes'] = (df[col_saldo_final] / df['Venda Média Diária']).replace([float('inf')], 999).fillna(999).astype(int)
            
            # 1. Primeiro descobre a quantidade exata matemática
            df['Qtd_Sugerida_Matematica'] = ((df['Venda Média Diária'] * dias_cobertura) - df[col_saldo_final]).clip(lower=0).astype(int)
            
            # 2. Depois aplica a regra de caixas fechadas dos disjuntores
            df['Qtd_Sugerida'] = df.apply(ajustar_lote_compra, axis=1)
            
            # 3. Calcula o total financeiro baseado na quantidade já arredondada
            df['Total Pedido'] = df['Qtd_Sugerida'] * df['Custo Unitário']
            
            st.subheader("📋 Diagnóstico de Reposição")
            colunas_exibir = [col_sku, 'Produto', 'Custo Unitário', col_saldo_final, 'Venda Média Diária', 'Dias_Restantes', 'Qtd_Sugerida', 'Total Pedido']
            st.dataframe(df[colunas_exibir])
            
            custo_total = df['Total Pedido'].sum()
            st.metric("Investimento Total Necessário", f"R$ {custo_total:,.2f}")

            # -----------------------------------------------------
            # NOVO FORMATO WHATSAPP PARA FORNECEDOR (Sem SKU)
            # -----------------------------------------------------
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
