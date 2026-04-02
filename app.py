import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import io

st.set_page_config(page_title="Gestão de Estoque Olist", layout="wide")

st.title("⚡ Planejador de Compras (Versão Final)")

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
        # Tenta ler como HTML (padrão Olist XLS)
        uploaded_file.seek(0)
        df = pd.read_html(uploaded_file)[0]
    except:
        try:
            # Tenta ler como Excel real
            uploaded_file.seek(0)
            df = pd.read_excel(uploaded_file)
        except:
            st.error("Não foi possível processar o formato deste arquivo.")

    if df is not None:
        try:
            # LIMPEZA DINÂMICA: Procura a linha onde as colunas reais começam
            # Se a primeira coluna não for 'Código (SKU)', vamos procurar a linha correta
            if 'Código (SKU)' not in df.columns:
                for i in range(len(df)):
                    if "SKU" in str(df.iloc[i].values):
                        df.columns = df.iloc[i] # Transforma essa linha no cabeçalho
                        df = df.iloc[i+1:] # Remove as linhas de cima
                        break
            
            # Remove espaços extras dos nomes das colunas
            df.columns = [str(c).strip() for c in df.columns]
            
            # Mapeamento de colunas
            col_sku = 'Código (SKU)'
            col_produto = 'Produto'
            col_saidas = 'Saídas'
            col_saldo_final = df.columns[-1] 

            # Garantir que são números
            df[col_saidas] = pd.to_numeric(df[col_saidas], errors='coerce').fillna(0)
            df[col_saldo_final] = pd.to_numeric(df[col_saldo_final], errors='coerce').fillna(0)
            
            # Remover linhas que não tenham SKU (como rodapés)
            df = df.dropna(subset=[col_sku])

            # --- CÁLCULOS ---
            df['VMD'] = df[col_saidas] / dias_analise
            df['Dias_Restantes'] = df[col_saldo_final] / df['VMD']
            df['Dias_Restantes'] = df['Dias_Restantes'].replace([float('inf')], 999).fillna(999)

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

            # Mostra apenas as colunas importantes para não poluir
            exibir = [col_sku, col_produto, col_saldo_final, 'VMD', 'Dias_Restantes', 'Qtd_Sugerida', 'Data_Pedido']
            st.dataframe(df[exibir].style.applymap(highlight_row, subset=['Dias_Restantes']))

            # --- GERAÇÃO DE XML ---
            st.divider()
            df_compra = df[df['Qtd_Sugerida'] > 0]
            if not df_compra.empty:
                root = ET.Element("PedidoCompra")
                for _, row in df_compra.iterrows():
                    item = ET.SubElement(root, "Item")
                    ET.SubElement(item, "SKU").text = str(row[col_sku])
                    ET.SubElement(item, "Qtd").text = str(row['Qtd_Sugerida'])

                xml_str = ET.tostring(root, encoding='utf-8')
                st.download_button("📥 Baixar XML de Compra", data=xml_str, file_name="pedido_estoque.xml", mime="application/xml")
            else:
                st.success("Estoque saudável!")

        except Exception as e:
            st.error(f"Erro ao processar as colunas: {e}")
            st.write("Colunas detectadas:", list(df.columns))
