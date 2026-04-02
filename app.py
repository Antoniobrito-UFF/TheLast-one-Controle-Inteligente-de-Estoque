import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import io
import urllib.parse
import os

st.set_page_config(page_title="Controle de Estoque D&G Tech", layout="wide")

# --- LOGO E TÍTULO ---
# Verifica se a imagem da logo existe na mesma pasta do GitHub
if os.path.exists("Logo alta qualidade fundo azul.jpg"):
    st.image("Logo alta qualidade fundo azul.jpg", width=250)

st.title("📊 Controle Inteligente de Estoque D&G Tech")

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
        uploaded_file.seek(0)
        df = pd.read_excel(uploaded_file, engine='calamine')
    except Exception as e:
        try:
            uploaded_file.seek(0)
            df = pd.read_html(uploaded_file)[0]
        except:
            st.error("O arquivo original está muito corrompido pela Olist. Abra-o no Excel, clique em 'Salvar Como' -> '.xlsx' e suba novamente.")

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
            # 1. Venda Média Diária
            df['Venda Média Diária'] = (df[col_saidas] / dias_analise).round(2)
            
            # 2. Dias Restantes (Inteiro)
            df['Dias_Restantes'] = df[col_saldo_final] / df['Venda Média Diária']
            df['Dias_Restantes'] = df['Dias_Restantes'].replace([float('inf')], 999).fillna(999)
            df['Dias_Restantes'] = df['Dias_Restantes'].astype(int) 

            # 3. Quantidade Sugerida
            df['Qtd_Sugerida'] = (df['Venda Média Diária'] * dias_cobertura) - df[col_saldo_final]
            df['Qtd_Sugerida'] = df['Qtd_Sugerida'].apply(lambda x: int(x) if x > 0 else 0)

            # 4. Data Limite para Pedido
            def calcular_data(dias):
                if dias >= 999:
                    return "Estoque OK"
                dias_para_zerar = dias - lead_time_total
                if dias_para_zerar <= 0:
                    return "🚨 COMPRAR HOJE!"
                
                data_compra = datetime.now() + timedelta(days=dias_para_zerar)
                return data_compra.strftime('%d/%m/%Y')

            df['Data Limite P/ Pedido'] = df['Dias_Restantes'].apply(calcular_data)

            # --- EXIBIÇÃO (Sem cores) ---
            st.subheader("📋 Diagnóstico de Inventário")
            
            colunas_exibir = [col_sku, 'Produto', col_saldo_final, 'Venda Média Diária', 'Dias_Restantes', 'Qtd_Sugerida', 'Data Limite P/ Pedido']
            # Agora renderizamos a tabela de forma simples e limpa
            st.dataframe(df[colunas_exibir])

            # --- AÇÕES (XML E WHATSAPP) ---
            st.divider()
            st.subheader("🚀 Ações")
            
            df_compra = df[df['Qtd_Sugerida'] > 0]
            
            if not df_compra.empty:
                col1, col2 = st.columns(2)
                
                # Botão XML
                root = ET.Element("PedidoCompra")
                for _, row in df_compra.iterrows():
                    item = ET.SubElement(root, "Item")
                    ET.SubElement(item, "SKU").text = str(row[col_sku])
                    ET.SubElement(item, "Quantidade").text = str(row['Qtd_Sugerida'])
                
                xml_data = ET.tostring(root, encoding='utf-8')
                with col1:
                    st.download_button("📥 Baixar XML de Compra", data=xml_data, file_name="pedido_reposicao.xml", mime="application/xml")
                
                # Botão WhatsApp
                texto_wpp = "🚨 *Alerta de Reposição de Estoque D&G Tech* 🚨\n\n"
                texto_wpp += "Equipa, precisamos comprar os seguintes itens para não pausar anúncios:\n\n"
                
                for _, row in df_compra.iterrows():
                    texto_wpp += f"📦 *Produto:* {row['Produto']} (SKU: {row[col_sku]})\n"
                    texto_wpp += f"🛒 *Quantidade:* {row['Qtd_Sugerida']} unidades\n"
                    texto_wpp += f"📅 *Comprar até:* {row['Data Limite P/ Pedido']}\n"
                    texto_wpp += "------------------------\n"
                
                link_wpp = f"https://api.whatsapp.com/send?text={urllib.parse.quote(texto_wpp)}"
                
                with col2:
                    st.markdown(f'<a href="{link_wpp}" target="_blank"><button style="background-color:#25D366; color:white; border:none; padding:8px 16px; border-radius:5px; cursor:pointer; font-weight:bold;">💬 Enviar para o WhatsApp da Empresa</button></a>', unsafe_allow_html=True)
            else:
                st.success("O seu estoque está saudável. Nenhuma compra necessária!")

        except Exception as e:
            st.error(f"Erro ao processar a tabela: {e}")
