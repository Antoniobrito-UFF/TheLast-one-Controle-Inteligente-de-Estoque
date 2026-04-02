import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import io

st.set_page_config(page_title="Gestão de Estoque Olist", layout="wide")

st.title("⚡ Planejador de Compras e Reposição")

# --- SIDEBAR: Parâmetros ---
st.sidebar.header("⚙️ Configurações")

# 1. Período de Análise
dias_analise = st.sidebar.number_input("Dias do relatório (para média):", min_value=1, value=7)

# 2. Lead Times
prazo_fornecedor = st.sidebar.number_input("Prazo do Fornecedor (dias):", min_value=0, value=7)
prazo_envio_full = st.sidebar.number_input("Prazo de envio ao Full (dias):", min_value=0, value=3)
lead_time_total = prazo_fornecedor + prazo_envio_full

# 3. Meta de Estoque
dias_cobertura = st.sidebar.number_input("Deseja estoque para quantos dias?", min_value=1, value=30)

# --- UPLOAD ---
uploaded_file = st.file_uploader("Suba o relatório da Olist (CSV)", type=["csv"])

if uploaded_file:
    # Lendo o arquivo (ajustando o separador para ponto e vírgula, comum na Olist)
    df = pd.read_csv(uploaded_file, sep=";")
    
    # Mapeando colunas do seu print
    col_sku = 'Código (SKU)'
    col_produto = 'Produto'
    col_saidas = 'Saídas'
    col_saldo_final = df.columns[-1] # Pega a última coluna (Saldo em...)

    # --- CÁLCULOS ---
    # Venda Média Diária
    df['VMD'] = df[col_saidas] / dias_analise
    
    # Quantos dias o estoque atual dura
    df['Dias_Restantes'] = df[col_saldo_final] / df['VMD']
    df['Dias_Restantes'] = df['Dias_Restantes'].fillna(999).replace([float('inf')], 999)

    # Cálculo da Quantidade de Compra (Estratégia Inteligente)
    # Fórmula: (VMD * Dias de Cobertura Desejados) - Estoque Atual
    df['Qtd_Sugerida'] = (df['VMD'] * dias_cobertura) - df[col_saldo_final]
    df['Qtd_Sugerida'] = df['Qtd_Sugerida'].apply(lambda x: int(x) if x > 0 else 0)

    # Data Limite para o Pedido
    df['Data_Pedido'] = df.apply(
        lambda x: (datetime.now() + timedelta(days=(x['Dias_Restantes'] - lead_time_total))).strftime('%d/%m/%Y') 
        if x['Dias_Restantes'] < 100 else "Estoque OK", axis=1
    )

    # --- EXIBIÇÃO ---
    st.subheader("📋 Diagnóstico de Inventário")
    
    def highlight_row(val):
        if val <= lead_time_total: return 'background-color: #ffcccc' # Vermelho (Crítico)
        if val <= lead_time_total + 5: return 'background-color: #fff4cc' # Amarelo (Atenção)
        return ''

    st.dataframe(df[[col_sku, col_produto, col_saldo_final, 'VMD', 'Dias_Restantes', 'Qtd_Sugerida', 'Data_Pedido']]
                 .style.applymap(highlight_row, subset=['Dias_Restantes']))

    # --- GERAÇÃO DE XML PARA COMPRA ---
    st.divider()
    st.subheader("📦 Gerar Pedido de Compra")
    
    # Filtrar apenas o que precisa ser comprado
    df_compra = df[df['Qtd_Sugerida'] > 0]

    if not df_compra.empty:
        # Criar estrutura XML
        root = ET.Element("PedidoCompra")
        root.set("data", datetime.now().strftime('%Y-%m-%d'))
        
        for _, row in df_compra.iterrows():
            item = ET.SubElement(root, "Item")
            ET.SubElement(item, "SKU").text = str(row[col_sku])
            ET.SubElement(item, "Descricao").text = str(row[col_produto])
            ET.SubElement(item, "Quantidade").text = str(row['Qtd_Sugerida'])

        # Converter para string e disponibilizar download
        xml_str = ET.tostring(root, encoding='utf-8', method='xml')
        
        st.write(f"Itens identificados para compra: **{len(df_compra)}**")
        st.download_button(
            label="📥 Baixar XML de Compra",
            data=xml_str,
            file_name=f"pedido_compra_{datetime.now().strftime('%Y%m%d')}.xml",
            mime="application/xml"
        )
    else:
        st.success("Seu estoque está saudável para o período de cobertura definido! Nada para comprar agora.")
