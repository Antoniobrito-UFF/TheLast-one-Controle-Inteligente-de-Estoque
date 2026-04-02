import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import io

st.set_page_config(page_title="Gestão de Estoque Olist", layout="wide")

st.title("⚡ Planejador de Compras (Versão Anti-Corrupção)")

# --- SIDEBAR ---
st.sidebar.header("⚙️ Configurações")
dias_analise = st.sidebar.number_input("Dias do relatório (para média):", min_value=1, value=7)
prazo_fornecedor = st.sidebar.number_input("Prazo do Fornecedor (dias):", min_value=0, value=7)
prazo_envio_full = st.sidebar.number_input("Prazo de envio ao Full (dias):", min_value=0, value=3)
lead_time_total = prazo_fornecedor + prazo_envio_full
dias_cobertura = st.sidebar.number_input("Estoque para quantos dias?", min_value=1, value=30)

# --- UPLOAD ---
uploaded_file = st.file_uploader("Suba o relatório da Olist", type=["xls", "xlsx", "csv"])

if uploaded_file:
    df = None
    try:
        # Usa o motor 'calamine', especialista em arquivos mal formatados/corrompidos
        uploaded_file.seek(0)
        df = pd.read_excel(uploaded_file, engine='calamine')
            
    except Exception as e:
        try:
            # Fallback para HTML ou CSV
            uploaded_file.seek(0)
            df = pd.read_html(uploaded_file)[0]
        except:
            st.error("O arquivo original está muito corrompido pela Olist. Abra-o no seu Excel, clique em 'Salvar Como' -> '.xlsx' e suba novamente.")

    if df is not None:
        try:
            # LIMPEZA DINÂMICA
            df.columns = [str(c).strip() for c in df.columns]
            
            if 'Código (SKU)' not in df.columns:
                for i in range(min(15, len(df))):
                    row_vals = [str(x).strip() for x in df.iloc[i].values]
                    if any("SKU" in x for x in row_vals):
                        df.columns = row_vals
                        df = df.iloc[i+1:]
                        break

            df.columns = [str(c).strip() for c in df.columns]

            col_sku = 'Código (SKU)'
            col_saidas = 'Saídas'
            
            col_saldo_final = [c for c in df.columns if 'Saldo em' in str(c) or 'Saldo final' in str(c)]
            col_saldo_final = col_saldo_final[-1] if col_saldo_final else df.columns[-1]

            df[col_saidas] = pd.to_numeric(df[col_saidas], errors='coerce').fillna(0)
            df[col_saldo_final] = pd.to_numeric(df[col_saldo_final], errors='coerce').fillna(0)
            
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

            # A CORREÇÃO ESTÁ AQUI: Trocamos applymap por map
            st.dataframe(df[[col_sku, 'Produto', col_saldo_final, 'VMD', 'Dias_Restantes', 'Qtd_Sugerida']]
                         .style.map(highlight_row, subset=['Dias_Restantes']))

            # --- GERAÇÃO DE XML ---
            st.divider()
            df_compra = df[df['Qtd_Sugerida'] > 0]
            if not df_compra.empty:
                root = ET.Element("PedidoCompra")
                for _, row in df_compra.iterrows():
                    item = ET.SubElement(root, "Item")
                    ET.SubElement(item, "SKU").text = str(row[col_sku])
                    ET.SubElement(item, "Quantidade").text = str(row['Qtd_Sugerida'])
                
                xml_data = ET.tostring(root, encoding='utf-8')
                st.download_button("📥 Baixar XML de Compra", data=xml_data, file_name="pedido_reposicao.xml", mime="application/xml")
            else:
                st.success("Seu estoque está saudável. Nenhuma compra necessária!")

        except Exception as e:
            st.error(f"Erro ao processar a tabela: {e}")
