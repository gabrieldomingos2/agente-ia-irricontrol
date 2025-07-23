# dashboard.py
import streamlit as st
import pandas as pd
import sqlite3
import json
from collections import Counter
import plotly.express as px

# Caminho para o banco de dados corrigido
DB_PATH = "data/sarah_bot.db"

# Função para carregar os dados (com cache para performance)
@st.cache_data(ttl=60)
def carregar_dados():
    try:
        # Garante que a conexão use o mesmo arquivo, mesmo se o dashboard for rodado de outro lugar
        conn = sqlite3.connect(DB_PATH, uri=True, check_same_thread=False)
        df = pd.read_sql_query("SELECT * FROM clientes", conn)
        conn.close()
        # Converte colunas JSON
        df['historico_conversa'] = df['historico_conversa'].apply(lambda x: json.loads(x) if isinstance(x, str) else x or [])
        df['tags_detectadas'] = df['tags_detectadas'].apply(lambda x: json.loads(x) if isinstance(x, str) else x or [])
        return df
    except (sqlite3.OperationalError, FileNotFoundError):
        st.error(f"Banco de dados não encontrado em '{DB_PATH}'. Rode o bot.py primeiro para criá-lo.")
        return pd.DataFrame()

# Layout da página
st.set_page_config(layout="wide", page_title="Sarah's Sales Dashboard")
st.title("🤖 Painel de Vendas da Sarah")
st.markdown("Visão geral dos leads e performance.")

df_clientes = carregar_dados()

if df_clientes.empty:
    st.warning("Nenhum dado de cliente para exibir.")
else:
    tab1, tab2 = st.tabs(["📊 Análise Geral", "💬 Visualizador de Conversas"])

    with tab1:
        st.header("📈 Métricas Principais")
        col1, col2, col3 = st.columns(3)
        col1.metric("Total de Leads", len(df_clientes))
        col2.metric("Lead Score Médio", f"{df_clientes['lead_score'].mean():.2f}")
        col3.metric("Orçamentos Enviados", df_clientes[df_clientes['orcamento_enviado'] > 0].shape[0])

        st.header("🔍 Análise de Dores e Intenções")

        todas_as_tags = [tag for sublist in df_clientes['tags_detectadas'] for tag in sublist]
        if todas_as_tags:
            contagem_tags = Counter(todas_as_tags)
            df_tags = pd.DataFrame(contagem_tags.items(), columns=['Intenção/Dor', 'Ocorrências']).sort_values('Ocorrências', ascending=False)
            fig_tags = px.bar(df_tags, x='Intenção/Dor', y='Ocorrências', title='Dores e Intenções Mais Comuns', text_auto=True)
            st.plotly_chart(fig_tags, use_container_width=True)
        else:
            st.info("Nenhuma tag foi detectada nas conversas ainda.")

        fig_score = px.histogram(df_clientes, x='lead_score', nbins=20, title='Distribuição de Lead Score')
        st.plotly_chart(fig_score, use_container_width=True)

    with tab2:
        st.header("🗣️ Análise de Conversas Individuais")
        
        lista_clientes = df_clientes.sort_values('lead_score', ascending=False)['nome'].unique()
        cliente_selecionado_nome = st.selectbox("Selecione um Cliente", lista_clientes)
        
        if cliente_selecionado_nome:
            cliente_data = df_clientes[df_clientes['nome'] == cliente_selecionado_nome].iloc[0]
            
            st.subheader(f"Detalhes de {cliente_data['nome']}")
            c1, c2, c3 = st.columns(3)
            c1.info(f"**Estado:** {cliente_data['estado_conversa']}")
            c2.warning(f"**Perfil:** {cliente_data['perfil']}")
            c3.error(f"**Lead Score:** {cliente_data['lead_score']}")
            st.write(f"**Tags:** `{', '.join(cliente_data['tags_detectadas'])}`")
            
            st.subheader("Histórico da Conversa")
            for msg in cliente_data['historico_conversa']:
                role = msg.get("role", "desconhecido")
                avatar = "👤" if role == 'user' else "🤖"
                with st.chat_message(name=role, avatar=avatar):
                    st.write(msg['content'])