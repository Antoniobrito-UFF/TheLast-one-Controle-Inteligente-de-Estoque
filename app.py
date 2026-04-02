import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import io

st.set_page_config(page_title="Gestão de Estoque Olist", layout="wide")

st.title("⚡ Planejador de Compras (Versão Excel)")

# --- SIDEBAR: Parâmetros ---
st.sidebar.header("⚙️ Configurações")
dias_analise = st.sidebar.number_input("Dias do relatório (para média):", min_value=1, value=7)
prazo_fornecedor = st.sidebar.number_input("Prazo do Fornecedor (dias):", min_value=0, value=7)
prazo_envio_full = st.sidebar.number_input("Prazo de envio ao Full (dias):", min_value=0, value=3)
lead_time_total = prazo_fornecedor + prazo_envio_full
dias_cobertura = st.sidebar.number_input("Deseja estoque para quantos dias?", min_value=1, value=30)

# --- UPLOAD ---
# Agora aceitando formatos de Excel
uploaded_file = st.file_uploader("Suba o relatório da Olist (XLS ou XLSX)", type=["xls", "xlsx"])

if uploaded_file:
    try:
        # Lendo o Excel de forma automática
        df = pd.read_excel(uploaded_file)
        
        # Mapeando colunas conforme o seu print
        # Usamos nomes exatos para SKU e Produto, mas índices para as datas (que mudam)
        col_sku = 'Código (SKU)'
        col_produto = 'Produto'
        col_saidas = 'Saídas'
        # A última coluna do seu print é o saldo final ("Saldo em DD/MM")
        col_saldo_final = df.columns[-1] 

        # --- CÁLCULOS ---
        df['VMD'] = df[col_saidas] / dias_analise
        df['Dias_Restantes'] = df[col_saldo_final] / df['VMD']
        df['Dias_Restantes'] = df['Dias_Restantes'].fillna(999).replace([float('inf')], 999)

        # Sugestão de Compra Inteligente
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
            if val <= lead_time_total: return 'background-color: #ffcccc' # Crítico
            if val <= lead_time_total + 5: return 'background-color: #fff4cc' # Atenção
            return ''

        # Mostrando a tabela formatada
        st.dataframe(df[[col_sku, col_produto, col_saldo_final, 'VMD', 'Dias_Restantes', 'Qtd_Sugerida', 'Data_Pedido']]
                     .style.applymap(highlight_row, subset=['Dias_Restantes']))

        # --- GERAÇÃO DE XML ---
        st.divider()
        st.subheader("📦 Gerar Pedido de Compra")
        df_compra = df[df['Qtd_Sugerida'] > 0]

        if not df_compra.empty:
            root = ET.Element("PedidoCompra")
            root.set("data_geracao", datetime.now().strftime('%Y-%m-%d'))
            
            for _, row in df_compra.iterrows():
                item = ET.SubElement(root, "Item")
                ET.SubElement(item, "SKU").text = str(row[col_sku])
                ET.SubElement(item, "Descricao").text = str(row[col_produto])
                ET.SubElement(item, "Quantidade").text = str(row['Qtd_Sugerida'])

            xml_str = ET.tostring(root, encoding='utf-8', method='xml')
            
            st.write(f"Itens para reposição: **{len(df_compra)}**")
            st.download_button(
                label="📥 Baixar XML de Compra",
                data=xml_str,
                file_name=f"pedido_compra_{datetime.now().strftime('%Y%m%d')}.xml",
                mime="application/xml"
            )
        else:
            st.success("Tudo certo! Seu estoque aguenta o tranco por enquanto.")

    except Exception as e:
        st.error(f"Erro ao ler o arquivo: {e}. Verifique se o relatório segue o padrão da imagem.")
