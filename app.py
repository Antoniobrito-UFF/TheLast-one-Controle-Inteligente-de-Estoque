import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import io

st.set_page_config(page_title="Gestão de Estoque Olist", layout="wide")

st.title("⚡ Planejador de Estoque (Versão Universal)")

# --- SIDEBAR ---
st.sidebar.header("⚙️ Configurações")
dias_analise = st.sidebar.number_input("Dias do relatório (para média):", min_value=1, value=7)
prazo_fornecedor = st.sidebar.number_input("Prazo do Fornecedor (dias):", min_value=0, value=7)
prazo_envio_full = st.sidebar.number_input("Prazo de envio ao Full (dias):", min_value=0, value=3)
lead_time_total = prazo_fornecedor + prazo_envio_full
dias_cobertura = st.sidebar.number_input("Estoque para quantos dias?", min_value=1, value=30)

# --- UPLOAD ---
uploaded_file = st.file_uploader("Suba o relatório da Olist", type=None) # Aceita qualquer tipo para testar

if uploaded_file:
    df = None
    content = uploaded_file.read()
    
    # --- TENTATIVAS DE LEITURA ---
    try:
        # Tentativa 1: HTML (Truque clássico da Olist)
        df = pd.read_html(io.BytesIO(content))[0]
    except:
        try:
            # Tentativa 2: Excel Real (.xlsx ou .xls)
            df = pd.read_excel(io.BytesIO(content))
        except:
            try:
                # Tentativa 3: CSV com ponto e vírgula
                df = pd.read_csv(io.BytesIO(content), sep=";", encoding='latin1')
                if 'Código (SKU)' not in df.columns: raise Exception
            except:
                try:
                    # Tentativa 4: CSV com vírgula ou UTF-16
                    df = pd.read_csv(io.BytesIO(content), sep=",", encoding='utf-16')
                except:
                    st.error("❌ Formato não reconhecido. Tente salvar o arquivo como 'Excel (.xlsx)' no seu computador antes de subir.")

    if df is not None:
        try:
            # LIMPEZA DE CABEÇALHO (Procurando a linha do SKU)
            if 'Código (SKU)' not in df.columns:
                for i in range(min(15, len(df))): # Procura nas primeiras 15 linhas
                    row_values = [str(x).strip() for x in df.iloc[i].values]
                    if any("SKU" in x for x in row_values):
                        df.columns = row_values
                        df = df.iloc[i+1:]
                        break

            # Limpar nomes das colunas
            df.columns = [str(c).strip() for c in df.columns]
            
            # Identificar colunas vitais
            col_sku = 'Código (SKU)'
            col_saidas = 'Saídas'
            col_saldo_final = [c for c in df.columns if 'Saldo em' in c or 'Saldo final' in c]
            col_saldo_final = col_saldo_final[-1] if col_saldo_final else df.columns[-1]

            # Converter para números
            for col in [col_saidas, col_saldo_final]:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            df = df.dropna(subset=[col_sku])

            # --- CÁLCULOS ---
            df['VMD'] = df[col_saidas] / dias_analise
            df['Dias_Restantes'] = df[col_saldo_final] / df['VMD']
            df['Dias_Restantes'] = df['Dias_Restantes'].replace([float('inf')], 999).fillna(999)

            df['Qtd_Sugerida'] = (df['VMD'] * dias_cobertura) - df[col_saldo_final]
            df['Qtd_Sugerida'] = df['Qtd_Sugerida'].apply(lambda x: int(x) if x > 0 else 0)

            # --- EXIBIÇÃO ---
            st.subheader("📋 Diagnóstico de Inventário")
            
            def highlight_row(val):
                if val <= lead_time_total: return 'background-color: #ffcccc'
                if val <= lead_time_total + 5: return 'background-color: #fff4cc'
                return ''

            st.dataframe(df[[col_sku, 'Produto', col_saldo_final, 'VMD', 'Dias_Restantes', 'Qtd_Sugerida']]
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
                
                xml_data = ET.tostring(root, encoding='utf-8')
                st.download_button("📥 Baixar XML de Compra", data=xml_data, file_name="compra_olist.xml")

        except Exception as e:
            st.error(f"Erro ao organizar dados: {e}")
            st.write("Colunas encontradas:", list(df.columns))
