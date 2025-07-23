# bot.py (v9.3 - Versão Limpa)
import os
import logging
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters, CommandHandler
from telegram.constants import ChatAction
from dotenv import load_dotenv

# --- Módulos do projeto ---
from sarah_bot.memoria import init_db, recuperar_ou_criar_cliente, atualizar_cliente, adicionar_mensagem_historico, get_cliente, deletar_cliente
from sarah_bot.orcamento import gerar_orcamento, formatar_resposta_orcamento
from sarah_bot.vendedora import analisar_mensagem_com_ia, gerar_resposta_sarah

# --- Configuração de Logging Robusta ---
logger = logging.getLogger()
logger.setLevel(logging.INFO)
if logger.hasHandlers():
    logger.handlers.clear()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
os.makedirs("data", exist_ok=True)
file_handler = logging.FileHandler("data/sarah_bot.log", mode='a', encoding='utf-8')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

# --- Carregamento de Variáveis de Ambiente ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
GERENTE_CHAT_ID = os.getenv("GERENTE_CHAT_ID")
LIMITE_LEAD_QUENTE = int(os.getenv("LIMITE_LEAD_QUENTE", 40))
VIDEO_DEMO_FILE_ID = os.getenv("VIDEO_DEMO_FILE_ID") # Carrega o ID do vídeo

def notificar_vendedor_humano(cliente):
    """Envia uma mensagem de alerta para um chat de gerência no Telegram."""
    if not GERENTE_CHAT_ID:
        logger.warning("GERENTE_CHAT_ID não definido. Não é possível enviar alerta.")
        return

    mensagem = (
        f"🔥 ALERTA DE LEAD QUENTE! 🔥\n\n"
        f"👤 *Cliente:* {cliente.get('nome')} (ID: {cliente.get('user_id')})\n"
        f"⭐ *Score:* {cliente.get('lead_score')}\n"
        f"🎯 *Tags:* `{', '.join(cliente.get('tags_detectadas', []))}`\n\n"
        f"Ação recomendada: Entrar em contato com o cliente."
    )
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": GERENTE_CHAT_ID, "text": mensagem, "parse_mode": "Markdown"}

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"Alerta de lead quente enviado com sucesso para o cliente {cliente.get('user_id')}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Falha ao enviar notificação de lead quente: {e}")

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"Recebido comando /reset do usuário {user_id}. Apagando dados.")
    if deletar_cliente(user_id):
        await update.message.reply_text("Prontinho! Esqueci tudo sobre nosso histórico. Podemos começar do zero. 😊")
    else:
        await update.message.reply_text("Hmm, parece que não consegui encontrar seu registro para apagar ou ocorreu um erro.")


# --- FUNÇÃO PRINCIPAL DE RESPOSTA ---
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # O código de debug que estava aqui foi removido.
    # A função agora lida apenas com mensagens de texto, pois o filtro no handler foi ajustado.
    
    user_id = update.effective_user.id
    mensagem_usuario = update.message.text
    nome_telegram = update.effective_user.first_name
    logger.info(f"Mensagem recebida de {nome_telegram} ({user_id}): '{mensagem_usuario}'")

    cliente = recuperar_ou_criar_cliente(user_id, nome_telegram)
    adicionar_mensagem_historico(user_id, "user", mensagem_usuario)
    cliente = get_cliente(user_id) 

    analise_ia = analisar_mensagem_com_ia(mensagem_usuario, cliente.get("historico_conversa", []))
    if not analise_ia:
        await update.message.reply_text("Desculpe, estou com dificuldade para processar sua mensagem agora. Poderia tentar novamente em um instante?")
        return

    qtd_pivos = analise_ia.get("entidades_extraidas", {}).get("qtd_pivos") or 0
    qtd_bombas = analise_ia.get("entidades_extraidas", {}).get("qtd_bombas") or 0
    
    tags_novas = set(analise_ia.get("tags_relevantes", []))
    tags_atuais = set(cliente.get("tags_detectadas", []))
    tags_combinadas = list(tags_atuais.union(tags_novas))

    score_analise = len(tags_novas) * 10
    score_orcamento = 15 * (qtd_pivos + qtd_bombas)
    score_anterior = cliente.get('lead_score', 0)
    novo_score = score_anterior + score_analise + score_orcamento

    dados_para_atualizar = { "perfil": analise_ia.get("perfil_detectado", cliente.get("perfil")), "tags_detectadas": tags_combinadas, "lead_score": novo_score }
    
    resposta_bot = ""

    if qtd_pivos > 0 or qtd_bombas > 0:
        logger.info(f"Gerando orçamento para {qtd_pivos} pivôs e {qtd_bombas} bombas.")
        _, val_eqp, val_inst, total_geral = gerar_orcamento(qtd_pivos, qtd_bombas)
        resposta_bot = formatar_resposta_orcamento(cliente['nome'], qtd_pivos, qtd_bombas, val_eqp, val_inst, total_geral)
        dados_para_atualizar.update({ "pivos": cliente.get("pivos", 0) + qtd_pivos, "bombas": cliente.get("bombas", 0) + qtd_bombas, "estado_conversa": "ORCAMENTO_APRESENTADO", "orcamento_enviado": total_geral })
    else:
        logger.info("Gerando resposta conversacional com a IA.")
        if cliente['estado_conversa'] == "INICIANTE":
            dados_para_atualizar["estado_conversa"] = "QUALIFICANDO"
        resposta_bot = gerar_resposta_sarah(pergunta=mensagem_usuario, nome_cliente=cliente.get("nome", ""), estado_conversa=cliente.get("estado_conversa", "QUALIFICANDO"), historico_conversa=cliente.get("historico_conversa", []), perfil_cliente=dados_para_atualizar["perfil"], tags_detectadas=tags_combinadas)

    if resposta_bot:
        await update.message.reply_text(resposta_bot, parse_mode="Markdown")
        adicionar_mensagem_historico(user_id, "assistant", resposta_bot)

        # --- LÓGICA PARA ENVIAR O VÍDEO ---
        if "vídeo" in resposta_bot.lower() and VIDEO_DEMO_FILE_ID:
            logger.info(f"Enviando vídeo de demonstração para o usuário {user_id}")
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_VIDEO)
            await update.message.reply_video(
                video=VIDEO_DEMO_FILE_ID,
                caption="Aqui está o vídeo que mencionei. Veja a robustez do sistema em ação! 💪"
            )

    if dados_para_atualizar:
        atualizar_cliente(user_id, dados_para_atualizar)

    if novo_score >= LIMITE_LEAD_QUENTE and score_anterior < LIMITE_LEAD_QUENTE:
        cliente_atualizado = {**cliente, **dados_para_atualizar}
        notificar_vendedor_humano(cliente_atualizado)

if __name__ == "__main__":
    init_db()
    logger.info("🤖 Sarah Bot (v9.3 - Versão Limpa) está no ar!")
    if not BOT_TOKEN:
        logger.critical("BOT_TOKEN não encontrado! O bot não pode iniciar.")
    else:
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("reset", reset_command))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))   
        app.run_polling()