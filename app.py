import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import urllib.parse
import os

st.set_page_config(page_title="Controle de Estoque D&G Tech", layout="wide")

# Função auxiliar para formatar moeda no padrão brasileiro (R$ 1.234,56)
def formatar_moeda(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --- LOGO E TÍTULO ---
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
    except Exception:
        try:
            uploaded_file.seek(0)
            df = pd.read_html(uploaded_file)[0]
        except:
            st.error("Erro ao ler o arquivo. Tente salvar como .xlsx no Excel antes de subir.")

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

            # --- CÁLCULOS LOGÍSTICOS ---
            df['Venda Média Diária'] = (df[col_saidas] / dias_analise).round(2)
            df['Dias_Restantes'] = (df[col_saldo_final] / df['Venda Média Diária']).replace([float('inf')], 999).fillna(999).astype(int)
            df['Qtd_Sugerida'] = ((df['Venda Média Diária'] * dias_cobertura) - df[col_saldo_final]).apply(lambda x: int(x) if x > 0 else 0)

            def calcular_data(dias):
                if dias >= 999: return "Estoque OK"
                dias_para_zerar = dias - lead_time_total
                if dias_para_zerar <= 0: return "🚨 COMPRAR HOJE!"
                return (datetime.now() + timedelta(days=dias_para_zerar)).strftime('%d/%m/%Y')

            df['Data Limite P/ Pedido'] = df['Dias_Restantes'].apply(calcular_data)
            
            # --- PREPARAÇÃO FINANCEIRA ---
            # Cria a coluna de custo com valor zero (será editada pelo usuário)
            if 'Custo Unitário (R$)' not in df.columns:
                df['Custo Unitário (R$)'] = 0.0

            st.divider()
            st.subheader("📋 Diagnóstico e Planejamento Financeiro")
            st.markdown("⚠️ **Dica:** Dê um duplo clique na coluna `Custo Unitário (R$)` para digitar o preço de compra de cada produto e simular o custo do pedido.")

            colunas_exibir = [col_sku, 'Produto', 'Custo Unitário (R$)', col_saldo_final, 'Venda Média Diária', 'Dias_Restantes', 'Qtd_Sugerida', 'Data Limite P/ Pedido']
            
            # --- TABELA INTERATIVA ---
            # st.data_editor permite que o usuário edite APENAS a coluna de custo
            df_editado = st.data_editor(
                df[colunas_exibir],
                disabled=[col_sku, 'Produto', col_saldo_final, 'Venda Média Diária', 'Dias_Restantes', 'Qtd_Sugerida', 'Data Limite P/ Pedido'],
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Custo Unitário (R$)": st.column_config.NumberColumn(
                        "Custo Unitário (R$)",
                        help="Digite o preço que você paga no fornecedor",
                        min_value=0.0,
                        format="R$ %.2f"
                    )
                }
            )

            # --- CÁLCULO FINANCEIRO PÓS-EDIÇÃO ---
            # Multiplica a quantidade sugerida pelo valor digitado na tabela
            df_editado['Custo Total Item'] = df_editado['Qtd_Sugerida'] * df_editado['Custo Unitário (R$)']
            custo_total_pedido = df_editado['Custo Total Item'].sum()

            # Bloco de destaque financeiro
            st.info(f"💰 **Custo Estimado do Pedido de Reposição:** {formatar_moeda(custo_total_pedido)}")

            # --- AÇÕES ---
            st.divider()
            df_compra = df_editado[df_editado['Qtd_Sugerida'] > 0].copy()
            
            if not df_compra.empty:
                col1, col2 = st.columns(2)
                
                # Gerar Excel para o Fornecedor
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_fornecedor = df_compra[[col_sku, 'Produto', 'Qtd_Sugerida', 'Custo Unitário (R$)', 'Custo Total Item']]
                    df_fornecedor.columns = ['SKU', 'Descrição do Produto', 'Quantidade Solicitada', 'Custo Unitário Acordado', 'Total do Item']
                    df_fornecedor.to_excel(writer, index=False, sheet_name='Pedido_Compra')
                excel_data = output.getvalue()

                with col1:
                    st.download_button(
                        label="📥 Baixar Planilha para Fornecedor (Excel)",
                        data=excel_data,
                        file_name=f"pedido_compra_dgtech_{datetime.now().strftime('%d_%m_%Y')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                
                # WhatsApp Clean e Financeiro
                texto_wpp = "*PEDIDO DE REPOSIÇÃO - D&G TECH*\n\n"
                for _, row in df_compra.iterrows():
                    texto_wpp += f"• {row[col_sku]} | {row['Qtd_Sugerida']} un. ({row['Produto']})\n"
                
                texto_wpp += f"\n💰 *Estimativa de Custo:* {formatar_moeda(custo_total_pedido)}\n"
                texto_wpp += f"_Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}_"
                link_wpp = f"https://api.whatsapp.com/send?text={urllib.parse.quote(texto_wpp)}"
                
                with col2:
                    st.markdown(f'<a href="{link_wpp}" target="_blank"><button style="background-color:#25D366; color:white; border:none; padding:10px 20px; border-radius:5px; cursor:pointer; font-weight:bold; width:100%;">💬 Enviar Resumo p/ WhatsApp</button></a>', unsafe_allow_html=True)
            else:
                st.success("Estoque em dia! Nenhuma compra necessária.")

        except Exception as e:
            st.error(f"Erro ao processar dados: {e}")
