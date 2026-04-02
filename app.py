import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import io

st.set_page_config(page_title="Gestão de Estoque Olist", layout="wide")

st.title("⚡ Planejador de Compras (Versão Olist Safe)")

# --- SIDEBAR ---
st.sidebar.header("⚙️ Configurações")
dias_analise = st.sidebar.number_input("Dias do relatório (para média):", min_value=1, value=7)
prazo_fornecedor = st.sidebar.number_input("Prazo do Fornecedor (dias):", min_value=0, value=7)
prazo_envio_full = st.sidebar.number_input("Prazo de envio ao Full (dias):", min_value=0, value=3)
lead_time_total = prazo_fornecedor + prazo_envio_full
dias_cobertura = st.sidebar.number_input("Deseja estoque para quantos dias?", min_value=1, value=30)

# --- UPLOAD ---
uploaded_file = st.file_uploader("Suba o relatório da Olist", type=["xls", "xlsx", "csv"])

if uploaded_file:
    df = None
    try:
        # Tentativa 1: Ler como Excel padrão (XLSX)
        df = pd.read_excel(uploaded_file)
    except:
        try:
            # Tentativa 2: Forçar leitura de XLS (caso seja um HTML disfarçado)
            uploaded_file.seek(0)
            df = pd.read_html(uploaded_file)[0]
        except:
            try:
                # Tentativa 3: Ler como CSV (caso o separador seja ponto e vírgula)
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, sep=";", encoding='latin1')
            except Exception as e:
                st.error(f"Erro crítico ao processar o arquivo. Detalhes: {e}")

    if df is not None:
        try:
            # Limpeza básica: remover linhas vazias
            df = df.dropna(subset=['Código (SKU)'])
            
            # Identificando colunas
            col_sku = 'Código (SKU)'
            col_produto = 'Produto'
            col_saidas = 'Saídas'
            col_saldo_final = df.columns[-1] 

            # Converter para número (caso venha como texto do HTML)
            df[col_saidas] = pd.to_numeric(df[col_saidas], errors='coerce').fillna(0)
            df[col_saldo_final] = pd.to_numeric(df[col_saldo_final], errors='coerce').fillna(0)

            # --- CÁLCULOS ---
            df['VMD'] = df[col_saidas] / dias_analise
            df['Dias_Restantes'] = df[col_saldo_final] / df['VMD']
            df['Dias_Restantes'] = df['Dias_Restantes'].fillna(999).replace([float('inf')], 999)

            df['Qtd_Sugerida'] = (df['VMD'] * dias_cobertura) - df[col_saldo_final]
            df['Qtd_Sugerida'] = df['Qtd_Sugerida'].apply(lambda x: int(x) if x > 0 else 0)

            df['Data_Pedido'] = df.apply(
                lambda x: (datetime.now() + timedelta(days=(x['Dias_Restantes'] - lead_time_total))).strftime('%d/%m/%Y') 
                if x['Dias_Restantes'] < 100 else "Estoque OK", axis=1
            )

            # --- EXIBIÇÃO ---
            st.subheader("📋 Diagnóstico de Inventário")
            
            def highlight_row(val):
                if val <= lead_time_total: return 'background-color: #ffcccc'
                if val <= lead_time_total + 5: return 'background-color: #fff4cc'
                return ''

            st.dataframe(df[[col_sku, col_produto, col_saldo_final, 'VMD', 'Dias_Restantes', 'Qtd_Sugerida', 'Data_Pedido']]
                         .style.applymap(highlight_row, subset=['Dias_Restantes']))

            # --- XML ---
            st.divider()
            df_compra = df[df['Qtd_Sugerida'] > 0]
            if not df_compra.empty:
                root = ET.Element("PedidoCompra")
                for _, row in df_compra.iterrows():
                    item = ET.SubElement(root, "Item")
                    ET.SubElement(item, "SKU").text = str(row[col_sku])
                    ET.SubElement(item, "Quantidade").text = str(row['Qtd_Sugerida'])

                xml_str = ET.tostring(root, encoding='utf-8')
                st.download_button("📥 Baixar XML de Compra", data=xml_str, file_name="compra.xml", mime="application/xml")
        
        except Exception as e:
            st.error(f"Erro na estrutura das colunas: {e}")
