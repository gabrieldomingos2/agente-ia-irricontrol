# bot.py (v8.0 - Estrutura Profissional)
import os
import re
import json
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
from dotenv import load_dotenv

# --- Módulos do projeto com imports corrigidos ---
from sarah_bot.memoria import init_db, recuperar_ou_criar_cliente, atualizar_cliente, adicionar_mensagem_historico, get_cliente
from sarah_bot.orcamento import gerar_orcamento, formatar_resposta_orcamento
from sarah_bot.vendedora import gerar_resposta_sarah
from sarah_bot.classificador import classificar_perfil
from sarah_bot.analisador_intencao import analisar_mensagem

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# --- FUNÇÃO DE ALERTA SIMPLIFICADA ---
async def notificar_vendedor_humano(cliente):
    """Função que apenas exibe um alerta no console sobre um lead quente."""
    print("\n" + "🔥" * 20)
    print(f"🔥 ALERTA DE LEAD QUENTE! 🔥")
    print(f"🔥 Cliente: {cliente.get('nome')} (ID: {cliente.get('user_id')})")
    print(f"🔥 Score Atingido: {cliente.get('lead_score')}")
    print("🔥 Ação manual recomendada: Entrar em contato com o cliente.")
    print("🔥" * 20 + "\n")

# --- HANDLERS DE ESTADO ---
async def handle_initial_message(cliente, mensagem_usuario):
    """Trata a primeira interação, fazendo a análise completa."""
    perfil_cliente = classificar_perfil(mensagem_usuario)
    analise = analisar_mensagem(mensagem_usuario)
    tags = analise.get('tags', [])
    score = analise.get('score', 0)

    resposta_bot = gerar_resposta_sarah(
        pergunta=mensagem_usuario,
        nome_cliente=cliente.get("nome", ""),
        estado_conversa="INICIANTE",
        historico_conversa=[],
        perfil_cliente=perfil_cliente,
        tags_detectadas=tags
    )

    dados_para_atualizar = {
        "perfil": perfil_cliente,
        "estado_conversa": "QUALIFICANDO",
        "tags_detectadas": tags,
        "lead_score": score
    }

    LIMITE_LEAD_QUENTE = 40
    if score >= LIMITE_LEAD_QUENTE:
        await notificar_vendedor_humano({**cliente, **dados_para_atualizar})

    return resposta_bot, dados_para_atualizar

async def handle_conversation(cliente, mensagem_usuario):
    """Trata a conversa geral, atualizando o score e as tags a cada mensagem."""
    analise = analisar_mensagem(mensagem_usuario)
    score_anterior = cliente.get('lead_score', 0)
    novo_score = score_anterior + analise.get('score', 0)

    tags_atuais = set(cliente.get("tags_detectadas", []))
    tags_atuais.update(analise.get('tags', []))

    dados_para_atualizar = {
        "lead_score": novo_score,
        "tags_detectadas": list(tags_atuais)
    }

    resposta_bot = gerar_resposta_sarah(
        pergunta=mensagem_usuario,
        nome_cliente=cliente.get("nome", ""),
        estado_conversa=cliente.get("estado_conversa", "QUALIFICANDO"),
        historico_conversa=cliente.get("historico_conversa", []),
        perfil_cliente=cliente.get("perfil", "neutro"),
        tags_detectadas=list(tags_atuais)
    )

    LIMITE_LEAD_QUENTE = 40
    if novo_score >= LIMITE_LEAD_QUENTE and score_anterior < LIMITE_LEAD_QUENTE:
        await notificar_vendedor_humano({**cliente, **dados_para_atualizar})

    return resposta_bot, dados_para_atualizar

# --- FUNÇÃO PRINCIPAL ---
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Função principal que gerencia a conversa."""
    user_id = update.effective_user.id
    print(f"INFO: Mensagem recebida do usuário ID: {user_id}")
    mensagem_usuario = update.message.text
    nome_telegram = update.effective_user.first_name

    recuperar_ou_criar_cliente(user_id, nome_telegram)
    adicionar_mensagem_historico(user_id, "user", mensagem_usuario)

    cliente = get_cliente(user_id)
    resposta_bot = ""
    dados_para_atualizar = {}

    qtd_pivos = extrair_quantidade(mensagem_usuario, r"piv[oô]s?")
    qtd_bombas = extrair_quantidade(mensagem_usuario, r"(bombas?|casa de bomba|casas de bombas)")

    if qtd_pivos > 0 or qtd_bombas > 0:
        _, val_eqp, val_inst, total_geral = gerar_orcamento(qtd_pivos, qtd_bombas)
        resposta_bot = formatar_resposta_orcamento(cliente['nome'], qtd_pivos, qtd_bombas, val_eqp, val_inst, total_geral)

        score_orcamento = 15 * (qtd_pivos + qtd_bombas)
        score_anterior = cliente.get('lead_score', 0)
        novo_score = score_anterior + score_orcamento

        dados_para_atualizar = {
            "pivos": cliente.get("pivos", 0) + qtd_pivos,
            "bombas": cliente.get("bombas", 0) + qtd_bombas,
            "estado_conversa": "ORCAMENTO_APRESENTADO",
            "orcamento_enviado": total_geral,
            "lead_score": novo_score
        }

        LIMITE_LEAD_QUENTE = 40
        if novo_score >= LIMITE_LEAD_QUENTE and score_anterior < LIMITE_LEAD_QUENTE:
            await notificar_vendedor_humano({**cliente, **dados_para_atualizar})
    else:
        estado_atual = cliente.get("estado_conversa", "INICIANTE")
        estado_handlers = {
            "INICIANTE": handle_initial_message,
            "QUALIFICANDO": handle_conversation,
            "ORCAMENTO_APRESENTADO": handle_conversation,
            "FOLLOW_UP_FINALIZADO": handle_conversation,
        }
        handler = estado_handlers.get(estado_atual, handle_conversation)
        resposta_bot, dados_para_atualizar_handler = await handler(cliente, mensagem_usuario)
        dados_para_atualizar.update(dados_para_atualizar_handler)

    if resposta_bot:
        await update.message.reply_text(resposta_bot, parse_mode="Markdown")
        adicionar_mensagem_historico(user_id, "assistant", resposta_bot)

    if dados_para_atualizar:
        atualizar_cliente(user_id, dados_para_atualizar)

def extrair_quantidade(texto, padrao_item):
    """Função utilitária para extrair números."""
    match = re.search(rf"(\d+|uma?)\s*{padrao_item}", texto, re.IGNORECASE)
    if not match:
        match = re.search(rf"{padrao_item}[\s\w,]*(\d+|uma?)", texto, re.IGNORECASE)
    if not match: return 0
    quantidade_str = next((g for g in match.groups() if g is not None), "0").lower()
    mapa_numeros = {"um": 1, "uma": 1}
    numero_encontrado = re.search(r'\d+', quantidade_str)
    return mapa_numeros.get(quantidade_str, int(numero_encontrado.group()) if numero_encontrado else 0)

if __name__ == "__main__":
    init_db()
    print("🤖 Sarah Bot (v8.0 - Estrutura Profissional) está no ar!")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))
    app.run_polling()