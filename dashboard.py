# dashboard.py (v15.0 - Centralizado)
import streamlit as st
import pandas as pd
import sqlite3
import json
from collections import Counter
import plotly.express as px
import plotly.graph_objects as go
from wordcloud import WordCloud
import matplotlib.pyplot as plt

# --- Importação da Configuração Centralizada ---
from sarah_bot.config import LIMITE_LEAD_QUENTE

# Caminho para o banco de dados
DB_PATH = "data/sarah_bot.db"

# Função para carregar os dados (com cache para performance)
@st.cache_data(ttl=60)
def carregar_dados():
    try:
        conn = sqlite3.connect(DB_PATH, uri=True, check_same_thread=False)
        df = pd.read_sql_query("SELECT * FROM clientes", conn)
        conn.close()
        # Converte colunas JSON e trata valores nulos/inválidos
        df['historico_conversa'] = df['historico_conversa'].apply(lambda x: json.loads(x) if isinstance(x, str) else [])
        df['tags_detectadas'] = df['tags_detectadas'].apply(lambda x: json.loads(x) if isinstance(x, str) else [])
        df['lead_score_historico'] = df['lead_score_historico'].apply(lambda x: json.loads(x) if isinstance(x, str) else [])
        df['dor_mencionada'] = df['dor_mencionada'].fillna('')
        df['etapa_jornada'] = df['etapa_jornada'].fillna('DESCONHECIDA')
        return df
    except (sqlite3.OperationalError, pd.io.sql.DatabaseError):
        st.error(f"Banco de dados não encontrado ou corrompido em '{DB_PATH}'. Rode o bot.py primeiro para criá-lo e gerar dados.")
        return pd.DataFrame()

# Layout da página
st.set_page_config(layout="wide", page_title="Sarah's Sales Dashboard")
st.title("🤖 Painel de Inteligência de Vendas da Sarah")
st.markdown("Análise estratégica de leads, funil de vendas e performance da conversação.")

df_clientes = carregar_dados()

if df_clientes.empty:
    st.warning("Nenhum dado de cliente para exibir. Interaja com o bot para gerar dados.")
else:
    tab1, tab2 = st.tabs(["📊 Análise Estratégica", "💬 Visualizador de Leads"])

    with tab1:
        st.header("📈 Métricas Principais")
        col1, col2, col3, col4 = st.columns(4)
        total_leads = len(df_clientes)
        leads_quentes = df_clientes[df_clientes['lead_score'] >= LIMITE_LEAD_QUENTE].shape[0]
        orcamentos_enviados = df_clientes[df_clientes['orcamento_enviado'] > 0].shape[0]

        col1.metric("Total de Leads", total_leads)
        col2.metric(f"Leads Quentes (Score >= {LIMITE_LEAD_QUENTE})", f"{leads_quentes} ({leads_quentes/total_leads:.1%})")
        col3.metric("Orçamentos Enviados", f"{orcamentos_enviados} ({orcamentos_enviados/total_leads:.1%})")
        col4.metric("Lead Score Médio", f"{df_clientes['lead_score'].mean():.2f}")

        st.divider()
        st.header("- Funil de Vendas")
        
        estados_funil = ['INICIANTE', 'AGUARDANDO_DOR', 'CONFIRMANDO_INTERESSE', 'ORCAMENTO_APRESENTADO', 'FECHAMENTO']
        contagem_estados = df_clientes['estado_conversa'].value_counts()
        valores_funil = [contagem_estados.get(estado, 0) for estado in estados_funil]
        
        fig_funil = go.Figure(go.Funnel(
            y = estados_funil,
            x = valores_funil,
            textposition = "inside",
            textinfo = "value+percent initial"
        ))
        fig_funil.update_layout(title_text="Funil de Conversão de Leads")
        st.plotly_chart(fig_funil, use_container_width=True)

        st.divider()
        
        col_dor, col_tags = st.columns(2)

        with col_dor:
            st.header("😟 Principais Dores dos Clientes")
            texto_dores = ' '.join(df_clientes['dor_mencionada'].dropna())
            if texto_dores:
                wordcloud = WordCloud(width=800, height=400, background_color='white').generate(texto_dores)
                fig_wc, ax = plt.subplots()
                ax.imshow(wordcloud, interpolation='bilinear')
                ax.axis('off')
                st.pyplot(fig_wc)
            else:
                st.info("Nenhuma dor foi mencionada pelos clientes ainda.")

        with col_tags:
            st.header("🎯 Análise de Tags por Performance")
            tags_quentes = [tag for sublist in df_clientes[df_clientes['lead_score'] >= LIMITE_LEAD_QUENTE]['tags_detectadas'] for tag in sublist]
            tags_frias = [tag for sublist in df_clientes[df_clientes['lead_score'] < LIMITE_LEAD_QUENTE]['tags_detectadas'] for tag in sublist]
            
            df_tags_quentes = pd.DataFrame(Counter(tags_quentes).items(), columns=['Tag', 'Ocorrências']).assign(Tipo='Lead Quente')
            df_tags_frias = pd.DataFrame(Counter(tags_frias).items(), columns=['Tag', 'Ocorrências']).assign(Tipo='Lead Frio')
            
            df_tags_performance = pd.concat([df_tags_quentes, df_tags_frias])
            
            fig_tags = px.bar(df_tags_performance, x='Tag', y='Ocorrências', color='Tipo', title='Frequência de Tags (Leads Quentes vs. Frios)', barmode='group')
            st.plotly_chart(fig_tags, use_container_width=True)


    with tab2:
        st.header("🗣️ Análise de Leads Individuais")
        
        filtro_nome = st.text_input("Buscar lead por nome...")
        df_filtrado = df_clientes
        if filtro_nome:
            df_filtrado = df_clientes[df_clientes['nome'].str.contains(filtro_nome, case=False, na=False)]

        lista_clientes = df_filtrado.sort_values('lead_score', ascending=False)['nome'].unique()
        cliente_selecionado_nome = st.selectbox("Selecione um Cliente", lista_clientes)
        
        if cliente_selecionado_nome:
            cliente_data = df_filtrado[df_filtrado['nome'] == cliente_selecionado_nome].iloc[0].to_dict()
            
            st.subheader(f"Detalhes de {cliente_data['nome']}")
            c1, c2, c3, c4 = st.columns(4)
            c1.info(f"**Estado da Conversa:** {cliente_data['estado_conversa']}")
            c2.warning(f"**Perfil Detectado:** {cliente_data['perfil']}")
            c3.error(f"**Lead Score:** {cliente_data['lead_score']}")
            c4.success(f"**Etapa da Jornada:** {cliente_data.get('etapa_jornada', 'N/A')}")
            
            st.write(f"**📍 Localização:** `{cliente_data.get('localizacao') or 'Não informada'}`")
            st.write(f"**🏡 Fazenda:** `{cliente_data.get('nome_fazenda') or 'Não informada'}`")
            st.write(f"**🎯 Tags:** `{', '.join(cliente_data.get('tags_detectadas', []))}`")
            
            st.subheader("Evolução do Lead Score")
            historico_score = cliente_data.get('lead_score_historico', [])
            
            if historico_score and isinstance(historico_score, list) and len(historico_score) > 1:
                df_score = pd.DataFrame(historico_score)
                df_score['timestamp'] = pd.to_datetime(df_score['timestamp'])
                
                fig_score = px.line(df_score, x='timestamp', y='score', title='Linha do Tempo do Score do Lead', markers=True)
                fig_score.update_layout(xaxis_title='Data', yaxis_title='Lead Score')
                st.plotly_chart(fig_score, use_container_width=True)
            else:
                st.info("Não há dados históricos de score suficientes para gerar um gráfico.")

            st.subheader("Histórico da Conversa")
            historico_conversa = cliente_data.get('historico_conversa', [])
            for msg in historico_conversa:
                role = msg.get("role", "desconhecido")
                avatar = "👤" if role == 'user' else "🤖"
                with st.chat_message(name=role, avatar=avatar):
                    st.write(msg.get('content'))