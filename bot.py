# bot.py (v13.1 - Corrigido e Otimizado)
import os
import logging
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters, CommandHandler
from telegram.constants import ChatAction
from dotenv import load_dotenv
from sarah_bot.memoria import init_db, recuperar_ou_criar_cliente, atualizar_cliente, adicionar_mensagem_historico, get_cliente, deletar_cliente
from sarah_bot.orcamento import gerar_orcamento, formatar_resposta_orcamento, formatar_resposta_orcamento_inicial
from sarah_bot.vendedora import analisar_mensagem_com_ia, gerar_resposta_sarah, extrair_nome_da_mensagem, extrair_quantidade_da_mensagem


# --- Configuração de Logging ---
logger = logging.getLogger(__name__)
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
VIDEO_DEMO_FILE_ID = os.getenv("VIDEO_DEMO_FILE_ID")

def escape_markdown(text: str) -> str:
    """
    Escapa caracteres especiais para o modo MarkdownV2 do Telegram.
    Isso previne o erro '400 Bad Request' por formatação inválida.
    """
    if not isinstance(text, str):
        return ""
    # Caracteres que precisam ser escapados no modo MarkdownV2
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return "".join(f'\\{char}' if char in escape_chars else char for char in text)

def notificar_vendedor_humano(cliente, motivo="LEAD QUENTE"):
    """Envia uma notificação formatada e segura para o gerente."""
    if not GERENTE_CHAT_ID:
        logger.warning("GERENTE_CHAT_ID não definido. Não é possível enviar alerta.")
        return
        
    titulo = "🔥 ALERTA DE LEAD QUENTE\\! 🔥"
    acao_recomendada = "Ação recomendada: Entrar em contato com o cliente\\."
    if motivo == "FECHAMENTO":
        titulo = "✅ CLIENTE PRONTO PARA FECHAR\\! ✅"
        acao_recomendada = "Ação recomendada: Entrar em contato IMEDIATAMENTE para finalizar o contrato\\."

    # Usando escape_markdown para garantir que a mensagem não quebre
    nome_cliente = escape_markdown(cliente.get('nome', 'N/A'))
    nome_fazenda = escape_markdown(cliente.get('nome_fazenda', 'N/A'))
    localizacao = escape_markdown(cliente.get('localizacao', 'N/A'))
    dor_mencionada = escape_markdown(cliente.get('dor_mencionada', 'Não informada'))
    tags_str = escape_markdown(", ".join(cliente.get('tags_detectadas', [])))

    # A construção da mensagem agora usa as strings corrigidas
    mensagem = (
        f"*{titulo}*\n\n"
        f"👤 *Cliente:* {nome_cliente} \\(ID: {cliente.get('user_id')}\\)\n"
        f"🏡 *Propriedade:* {nome_fazenda} em {localizacao}\n"
        f"⭐ *Score:* {cliente.get('lead_score')}\n"
        f"🎯 *Tags:* `{tags_str}`\n"
        f"😟 *Principal Dor:* {dor_mencionada}\n\n"
        f"_{acao_recomendada}_"
    )

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": GERENTE_CHAT_ID, "text": mensagem, "parse_mode": "MarkdownV2"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"Alerta de '{motivo}' enviado com sucesso para o cliente {cliente.get('user_id')}")
    except requests.exceptions.RequestException as e:
        error_details = e.response.json() if e.response else str(e)
        logger.error(f"Falha ao enviar notificação de '{motivo}': {e} - Detalhes: {error_details}")


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"Recebido comando /reset do usuário {user_id}. Apagando dados.")
    if deletar_cliente(str(user_id)):
        await update.message.reply_text("Prontinho! Esqueci tudo sobre nosso histórico. Podemos começar do zero. 😊")
    else:
        await update.message.reply_text("Hmm, parece que não consegui encontrar seu registro para apagar ou ocorreu um erro.")


async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # --- CORREÇÃO 1: Impede o bot de travar com atualizações sem texto ---
    if not update.message or not update.message.text:
        logger.warning("Recebida uma atualização sem texto de mensagem. Ignorando.")
        return

    user_id = update.effective_user.id
    mensagem_usuario = update.message.text
    nome_telegram = update.effective_user.first_name

    cliente = recuperar_ou_criar_cliente(str(user_id), nome_telegram)
    adicionar_mensagem_historico(str(user_id), "user", mensagem_usuario)
    
    estado_atual = cliente.get("estado_conversa")
    resposta_bot = ""
    enviar_video = False
    dados_para_atualizar = {}
    analise_ia = {} # Inicializa a análise da IA

    # --- MÁQUINA DE ESTADOS ---

    if estado_atual == 'INICIANTE':
        logger.info(f"Novo cliente (ID: {user_id}). Solicitando nome.")
        resposta_bot = "Olá! Sou a Sarah, especialista em segurança para o agronegócio da Irricontrol. Fico feliz em ajudar. Para começarmos, como posso chamá-lo(a)?"
        dados_para_atualizar['estado_conversa'] = 'AGUARDANDO_NOME'

    elif estado_atual == 'AGUARDANDO_NOME':
        nome_cliente = extrair_nome_da_mensagem(mensagem_usuario) or mensagem_usuario.strip().title()
        logger.info(f"Cliente (ID: {user_id}) informou o nome: {nome_cliente}")
        dados_para_atualizar.update({'nome': nome_cliente, 'estado_conversa': 'AGUARDANDO_DOR'})
        cliente_temp = {**cliente, **dados_para_atualizar}
        resposta_bot = gerar_resposta_sarah(mensagem_usuario, cliente_temp, 'AGUARDANDO_DOR', cliente['historico_conversa'])

    elif estado_atual == 'AGUARDANDO_DOR':
        logger.info(f"Cliente (ID: {user_id}) descreveu sua dor/preocupação: '{mensagem_usuario}'")
        dados_para_atualizar.update({'dor_mencionada': mensagem_usuario, 'estado_conversa': 'CONFIRMANDO_INTERESSE'})
        resposta_bot = gerar_resposta_sarah(mensagem_usuario, cliente, 'CONFIRMANDO_INTERESSE', cliente['historico_conversa'])
    
    else:
        # --- FLUXO DINÂMICO PÓS-QUALIFICAÇÃO ---
        cliente = get_cliente(str(user_id))
        analise_ia = analisar_mensagem_com_ia(mensagem_usuario, cliente.get("historico_conversa", []))
        tags_da_mensagem_atual = set(analise_ia.get("tags_relevantes", []))
        
        if "sim" in mensagem_usuario.lower() and estado_atual == 'CONFIRMANDO_INTERESSE':
            dados_para_atualizar['estado_conversa'] = 'APRESENTANDO_SOLUCAO'
            resposta_bot = gerar_resposta_sarah(mensagem_usuario, cliente, 'APRESENTANDO_SOLUCAO', cliente['historico_conversa'])
            if not cliente.get('video_enviado'):
                enviar_video = True
                dados_para_atualizar['video_enviado'] = 1
        
        elif "INTENCAO_ORCAMENTO" in tags_da_mensagem_atual:
            quantidade = extrair_quantidade_da_mensagem(mensagem_usuario)
            if quantidade > 0:
                qtd_pivos, qtd_bombas = (0, quantidade) if "bomba" in mensagem_usuario.lower() else (quantidade, 0)
                _, val_eqp, val_inst, total_geral = gerar_orcamento(qtd_pivos, qtd_bombas)
                resposta_bot = formatar_resposta_orcamento(cliente['nome'], qtd_pivos, qtd_bombas, val_eqp, val_inst, total_geral)
                resposta_bot += "\n\n" + gerar_resposta_sarah("Ok, enviei o orçamento.", cliente, 'ORCAMENTO_APRESENTADO', cliente['historico_conversa'])
                dados_para_atualizar.update({'estado_conversa': 'ORCAMENTO_APRESENTADO', 'orcamento_enviado': total_geral})
            else:
                resposta_bot = formatar_resposta_orcamento_inicial(cliente['nome'])
                dados_para_atualizar['estado_conversa'] = 'AGUARDANDO_QUANTIDADE_ORCAMENTO'

        elif "INTENCAO_ADIAR_DECISAO" in tags_da_mensagem_atual:
            resposta_bot = gerar_resposta_sarah(mensagem_usuario, cliente, 'INTENCAO_ADIAR_DECISAO', cliente['historico_conversa'])
            dados_para_atualizar['estado_conversa'] = 'FOLLOW_UP_POS_ORCAMENTO'
        
        elif "OBJECÃO_PRECO" in tags_da_mensagem_atual:
            resposta_bot = gerar_resposta_sarah(mensagem_usuario, cliente, 'OBJECÃO_PRECO', cliente['historico_conversa'])
        
        elif "INTENCAO_FECHAMENTO" in tags_da_mensagem_atual:
            resposta_bot = gerar_resposta_sarah(mensagem_usuario, cliente, 'FECHAMENTO', cliente['historico_conversa'])
            dados_para_atualizar['estado_conversa'] = 'FECHAMENTO'

        else: 
            resposta_bot = gerar_resposta_sarah(mensagem_usuario, cliente, estado_atual, cliente['historico_conversa'])
        
        tags_acumuladas = list(set(cliente.get("tags_detectadas", [])).union(tags_da_mensagem_atual))
        dados_para_atualizar.update({"perfil": analise_ia.get("perfil_detectado", cliente.get("perfil")), "tags_detectadas": tags_acumuladas})

    # --- FINALIZAÇÃO, ENVIO E ATUALIZAÇÃO ---
    if dados_para_atualizar:
        atualizar_cliente(str(user_id), dados_para_atualizar)
    
    if resposta_bot:
        await update.message.reply_text(resposta_bot, parse_mode="Markdown")
        adicionar_mensagem_historico(str(user_id), "assistant", resposta_bot)

    if enviar_video and VIDEO_DEMO_FILE_ID:
        logger.info(f"Enviando vídeo de demonstração para o cliente {user_id}.")
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_VIDEO)
        await update.message.reply_video(video=VIDEO_DEMO_FILE_ID, caption="Para ilustrar, veja a robustez do nosso sistema em ação! 💪")
        adicionar_mensagem_historico(str(user_id), "assistant", "[VÍDEO DE DEMONSTRAÇÃO ENVIADO]")
    
    # --- LÓGICA DE LEAD SCORE E NOTIFICAÇÃO ---
    cliente_atualizado = get_cliente(str(user_id))
    score_anterior = cliente.get('lead_score', 0)
    
    tags_da_mensagem_atual = set(analise_ia.get("tags_relevantes", []))
    score_analise = len(tags_da_mensagem_atual) * 5 
    score_orcamento = 25 if "ORCAMENTO_APRESENTADO" in dados_para_atualizar.get("estado_conversa", "") else 0
    novo_score = score_anterior + score_analise + score_orcamento
    if "INTENCAO_FECHAMENTO" in tags_da_mensagem_atual: novo_score += 50
    
    if novo_score != score_anterior:
        atualizar_cliente(str(user_id), {"lead_score": novo_score})
        cliente_atualizado["lead_score"] = novo_score

    # --- CORREÇÃO 2: Lógica de notificação para evitar duplicatas ---
    notificacao_ja_enviada = cliente_atualizado.get('notificacao_enviada', 0)

    if "INTENCAO_FECHAMENTO" in tags_da_mensagem_atual:
        notificar_vendedor_humano(cliente_atualizado, motivo="FECHAMENTO")
    elif cliente_atualizado.get('lead_score', 0) >= LIMITE_LEAD_QUENTE and not notificacao_ja_enviada:
        notificar_vendedor_humano(cliente_atualizado, motivo="LEAD QUENTE")
        # Marca que a notificação foi enviada para não repetir
        atualizar_cliente(str(user_id), {"notificacao_enviada": 1})


if __name__ == "__main__":
    init_db()
    logger.info("🤖 Sarah Bot (v13.1 - Corrigido e Otimizado) está no ar!")
    if not BOT_TOKEN:
        logger.critical("BOT_TOKEN não encontrado! Verifique o arquivo .env.")
    else:
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("reset", reset_command))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))
        app.run_polling()