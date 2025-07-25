# bot.py (v14.1 - Corrigido e Otimizado)
import os
import logging
import requests
import json
from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters, CommandHandler
from telegram.constants import ChatAction, ParseMode
from typing import Tuple # <--- ADICIONADO

from dotenv import load_dotenv
from sarah_bot.memoria import init_db, recuperar_ou_criar_cliente, atualizar_cliente, adicionar_mensagem_historico, deletar_cliente
from sarah_bot.orcamento import gerar_orcamento, formatar_resposta_orcamento, formatar_resposta_orcamento_inicial
from sarah_bot.vendedora import analisar_mensagem_com_ia, gerar_resposta_sarah, extrair_nome_da_mensagem, extrair_quantidade_da_mensagem

# --- Configuração de Logging Estruturado ---
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if logger.hasHandlers():
    logger.handlers.clear()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
os.makedirs("data", exist_ok=True)
# Usar 'a' para modo append, para não apagar logs anteriores a cada reinício
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

# --- Pesos para o Lead Scoring ---
TAG_WEIGHTS = {
    "INTENCAO_FECHAMENTO": 50,
    "DOR_FURTO_PROPRIO": 25,
    "PEDIDO_ORCAMENTO": 20,
    "DOR_INSEGURANCA_REGIAO": 15,
    "INFORMOU_QUANTIDADE": 10,
    "OBJECÃO_PRECO": 10,  # Objeção é sinal de interesse!
    "PEDIDO_INFORMACOES_GERAIS": 5,
    "PEDIDO_VIDEO": 5,
    "OBJECÃO_ADIAMENTO": 2, # Interesse baixo, mas ainda engajado
}


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Loga os erros causados por Updates e notifica o usuário."""
    logger.error("Exceção ao processar uma atualização:", exc_info=context.error)
    
    # Tenta notificar o usuário sobre o erro
    if isinstance(update, Update) and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Ops! Encontrei um problema técnico. 😥 Já estou trabalhando para resolver. Por favor, tente enviar sua mensagem novamente em alguns instantes."
            )
        except Exception as e:
            logger.error(f"Não foi possível enviar a mensagem de erro ao usuário {update.effective_chat.id}. Erro: {e}")

def escape_markdown_v2(text: str) -> str:
    """Escapa caracteres especiais para o modo MarkdownV2 do Telegram."""
    if not isinstance(text, str):
        return ""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return "".join(f'\\{char}' if char in escape_chars else char for char in text)

def notificar_vendedor_humano(cliente, motivo="LEAD QUENTE"):
    """Envia uma notificação formatada e segura para o gerente."""
    if not GERENTE_CHAT_ID:
        logger.warning("GERENTE_CHAT_ID não definido. Não é possível enviar alerta.")
        return
        
    motivos = {
        "LEAD QUENTE": ("🔥 ALERTA DE LEAD QUENTE\\! 🔥", "Ação recomendada: Entrar em contato com o cliente\\."),
        "FECHAMENTO": ("✅ CLIENTE PRONTO PARA FECHAR\\! ✅", "Ação recomendada: Entrar em contato IMEDIATAMENTE para finalizar o contrato\\.")
    }
    titulo, acao = motivos.get(motivo, motivos["LEAD QUENTE"])

    # Usando escape_markdown_v2 para garantir que a mensagem não quebre
    nome_cliente = escape_markdown_v2(cliente.get('nome', 'N/A'))
    nome_fazenda = escape_markdown_v2(cliente.get('nome_fazenda', 'N/A'))
    localizacao = escape_markdown_v2(cliente.get('localizacao', 'N/A'))
    dor_mencionada = escape_markdown_v2(cliente.get('dor_mencionada', 'Não informada'))
    tags_str = escape_markdown_v2(", ".join(cliente.get('tags_detectadas', [])))
    score = cliente.get('lead_score', 0)
    user_id = cliente.get('user_id')

    mensagem = (
        f"*{titulo}*\n\n"
        f"👤 *Cliente:* {nome_cliente} \\(ID: `{user_id}`\\)\n"
        f"🏡 *Propriedade:* {nome_fazenda}\n"
        f"📍 *Localização:* {localizacao}\n"
        f"⭐ *Lead Score:* *{score}*\n"
        f"🎯 *Tags:* `{tags_str}`\n"
        f"😟 *Principal Dor:* {dor_mencionada}\n\n"
        f"_{acao}_"
    )

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": GERENTE_CHAT_ID, "text": mensagem, "parse_mode": "MarkdownV2"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"Alerta de '{motivo}' enviado com sucesso para o cliente {user_id}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Falha ao enviar notificação de '{motivo}': {e}")
        return False


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"Recebido comando /reset do usuário {user_id}. Apagando dados.")
    if deletar_cliente(str(user_id)):
        await update.message.reply_text("Prontinho! Esqueci nosso histórico e comecei do zero. 😊 Como posso te ajudar?")
    else:
        await update.message.reply_text("Hmm, parece que não encontrei seu registro para apagar ou ocorreu um erro.")


# --- FUNÇÕES AUXILIARES DA MÁQUINA DE ESTADOS (Refatoração) ---

def _handle_estado_inicial(mensagem_usuario: str, cliente: dict) -> Tuple[str, dict]: # <--- CORRIGIDO
    """Lida com os estados iniciais da conversa (INICIANTE, AGUARDANDO_NOME)."""
    estado_atual = cliente["estado_conversa"]
    dados_para_atualizar = {}
    resposta_bot = ""

    if estado_atual == 'INICIANTE':
        logger.info(f"Novo cliente (ID: {cliente['user_id']}). Solicitando nome.")
        resposta_bot = "Olá! Sou a Sarah, especialista em segurança para o agronegócio da Irricontrol. Fico feliz em te ajudar. Para começarmos, como posso te chamar?"
        dados_para_atualizar['estado_conversa'] = 'AGUARDANDO_NOME'
    
    elif estado_atual == 'AGUARDANDO_NOME':
        nome_cliente = extrair_nome_da_mensagem(mensagem_usuario) or mensagem_usuario.strip().title()
        logger.info(f"Cliente (ID: {cliente['user_id']}) informou o nome: {nome_cliente}")
        dados_para_atualizar.update({'nome': nome_cliente, 'estado_conversa': 'AGUARDANDO_DOR'})
        cliente_temp = {**cliente, **dados_para_atualizar} # Cria um cliente temporário para gerar a resposta com o nome já atualizado
        resposta_bot = gerar_resposta_sarah(mensagem_usuario, cliente_temp, 'AGUARDANDO_DOR', cliente['historico_conversa'])

    return resposta_bot, dados_para_atualizar


def _handle_conversa_geral(mensagem_usuario: str, cliente: dict) -> Tuple[str, dict, bool]: # <--- CORRIGIDO
    """Lida com o fluxo principal da conversa após a qualificação inicial."""
    estado_atual = cliente["estado_conversa"]
    dados_para_atualizar = {}
    resposta_bot = ""
    enviar_video = False

    # 1. Análise da IA
    analise_ia = analisar_mensagem_com_ia(mensagem_usuario, cliente.get("historico_conversa", []))
    tags = set(analise_ia.get("tags_relevantes", []))
    
    # 2. Atualiza entidades extraídas
    entidades = analise_ia.get("entidades_extraidas", {})
    if entidades.get("nome_fazenda"): dados_para_atualizar["nome_fazenda"] = entidades["nome_fazenda"]
    if entidades.get("localizacao"): dados_para_atualizar["localizacao"] = entidades["localizacao"]
    
    # 3. Lógica de transição de estados baseada em tags
    if estado_atual == 'AGUARDANDO_DOR':
        logger.info(f"Cliente (ID: {cliente['user_id']}) descreveu sua dor: '{mensagem_usuario}'")
        dados_para_atualizar.update({'dor_mencionada': mensagem_usuario, 'estado_conversa': 'CONFIRMANDO_INTERESSE'})
        resposta_bot = gerar_resposta_sarah(mensagem_usuario, cliente, 'CONFIRMANDO_INTERESSE', cliente['historico_conversa'])

    elif ("sim" in mensagem_usuario.lower() or "pode" in mensagem_usuario.lower()) and estado_atual == 'CONFIRMANDO_INTERESSE':
        dados_para_atualizar['estado_conversa'] = 'APRESENTANDO_SOLUCAO'
        resposta_bot = gerar_resposta_sarah(mensagem_usuario, cliente, 'APRESENTANDO_SOLUCAO', cliente['historico_conversa'])
        if not cliente.get('video_enviado'):
            enviar_video = True
            dados_para_atualizar['video_enviado'] = 1
    
    elif "PEDIDO_ORCAMENTO" in tags:
        quantidade = extrair_quantidade_da_mensagem(mensagem_usuario)
        if quantidade > 0:
            qtd_pivos = quantidade if "pivo" in mensagem_usuario.lower() else 0
            qtd_bombas = quantidade if "bomba" in mensagem_usuario.lower() else (quantidade if qtd_pivos == 0 else 0)
            _, val_eqp, val_inst, total_geral = gerar_orcamento(qtd_pivos, qtd_bombas)
            resposta_bot = formatar_resposta_orcamento(cliente['nome'], qtd_pivos, qtd_bombas, val_eqp, val_inst, total_geral)
            # Adiciona a pergunta de fechamento estratégico
            resposta_bot += "\n\n" + gerar_resposta_sarah("Ok, enviei o orçamento.", cliente, 'ORCAMENTO_APRESENTADO', cliente['historico_conversa'])
            dados_para_atualizar.update({'estado_conversa': 'ORCAMENTO_APRESENTADO', 'orcamento_enviado': total_geral})
        else:
            resposta_bot = formatar_resposta_orcamento_inicial(cliente['nome'])
            dados_para_atualizar['estado_conversa'] = 'AGUARDANDO_QUANTIDADE_ORCAMENTO'

    elif "OBJECÃO_PRECO" in tags or "OBJECÃO_ADIAMENTO" in tags:
        dados_para_atualizar['estado_conversa'] = 'QUEBRANDO_OBJECAO'
        resposta_bot = gerar_resposta_sarah(mensagem_usuario, cliente, 'QUEBRANDO_OBJECAO', cliente['historico_conversa'])

    elif "INTENCAO_FECHAMENTO" in tags:
        dados_para_atualizar['estado_conversa'] = 'FECHAMENTO'
        # Uma resposta padrão pode ser criada no prompt para 'FECHAMENTO'
        resposta_bot = gerar_resposta_sarah(mensagem_usuario, cliente, 'FECHAMENTO', cliente['historico_conversa'])

    else: # Resposta genérica para outros inputs
        resposta_bot = gerar_resposta_sarah(mensagem_usuario, cliente, estado_atual, cliente['historico_conversa'])
    
    # 4. Atualiza tags e perfil
    tags_acumuladas = list(set(cliente.get("tags_detectadas", [])).union(tags))
    dados_para_atualizar.update({
        "perfil": analise_ia.get("perfil_detectado", cliente.get("perfil")), 
        "tags_detectadas": tags_acumuladas,
        "lead_score": _calcular_novo_score(cliente.get('lead_score', 0), tags)
    })

    return resposta_bot, dados_para_atualizar, enviar_video

def _calcular_novo_score(score_atual: int, tags_novas: set) -> int:
    """Calcula o novo lead score com base nas novas tags detectadas."""
    incremento = sum(TAG_WEIGHTS.get(tag, 0) for tag in tags_novas)
    return score_atual + incremento

# --- FUNÇÃO PRINCIPAL DE RESPOSTA (Maestro) ---

async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        logger.warning("Recebida uma atualização sem texto de mensagem. Ignorando.")
        return

    user_id = update.effective_user.id
    mensagem_usuario = update.message.text
    nome_telegram = update.effective_user.first_name
    
    await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)

    # 1. Recupera/Cria Cliente (1 leitura do DB)
    cliente = recuperar_ou_criar_cliente(str(user_id), nome_telegram)
    adicionar_mensagem_historico(str(user_id), "user", mensagem_usuario)

    # 2. Inicializa variáveis do ciclo
    estado_atual = cliente.get("estado_conversa")
    resposta_bot = ""
    dados_para_atualizar = {}
    enviar_video = False

    # 3. MÁQUINA DE ESTADOS REATORADA
    if estado_atual in ['INICIANTE', 'AGUARDANDO_NOME']:
        resposta_bot, dados_para_atualizar = _handle_estado_inicial(mensagem_usuario, cliente)
    else:
        # O cliente já está qualificado, entra no fluxo de conversa geral
        resposta_bot, dados_para_atualizar, enviar_video = _handle_conversa_geral(mensagem_usuario, cliente)

    # 4. Atualiza Cliente (1 escrita no DB)
    if dados_para_atualizar:
        atualizar_cliente(str(user_id), dados_para_atualizar)

    # 5. Envia Respostas ao Usuário
    if resposta_bot:
        await update.message.reply_text(resposta_bot, parse_mode=ParseMode.HTML) # Usar HTML é mais flexível que Markdown
        adicionar_mensagem_historico(str(user_id), "assistant", resposta_bot)

    if enviar_video and VIDEO_DEMO_FILE_ID:
        logger.info(f"Enviando vídeo de demonstração para o cliente {user_id}.")
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_VIDEO)
        await update.message.reply_video(video=VIDEO_DEMO_FILE_ID, caption="Para ilustrar, veja a robustez do nosso sistema em ação! 💪")
        adicionar_mensagem_historico(str(user_id), "assistant", "[VÍDEO DE DEMONSTRAÇÃO ENVIADO]")
    
    # 6. LÓGICA DE NOTIFICAÇÃO AO GERENTE
    cliente_atualizado = {**cliente, **dados_para_atualizar} # Simula o cliente atualizado para a lógica de notificação
    
    notificacao_ja_enviada = cliente.get('notificacao_enviada', 0)
    score_atual = cliente_atualizado.get('lead_score', 0)
    tags_atuais = set(cliente_atualizado.get('tags_detectadas', []))

    if "INTENCAO_FECHAMENTO" in tags_atuais:
        if notificar_vendedor_humano(cliente_atualizado, motivo="FECHAMENTO"):
            atualizar_cliente(str(user_id), {"notificacao_enviada": 1}) # Marca como notificado
    elif score_atual >= LIMITE_LEAD_QUENTE and not notificacao_ja_enviada:
        if notificar_vendedor_humano(cliente_atualizado, motivo="LEAD QUENTE"):
            atualizar_cliente(str(user_id), {"notificacao_enviada": 1}) # Marca como notificado

# --- PONTO DE ENTRADA DA APLICAÇÃO ---

if __name__ == "__main__":
    init_db()
    logger.info("🤖 Sarah Bot (v14.1 - Corrigido e Otimizado) está no ar!")
    if not BOT_TOKEN:
        logger.critical("BOT_TOKEN não encontrado! Verifique o arquivo .env.")
    else:
        app = Application.builder().token(BOT_TOKEN).build()
        
        # Adiciona handlers de comando e mensagem
        app.add_handler(CommandHandler("reset", reset_command))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))
        
        # Adiciona o handler de erro global
        app.add_error_handler(error_handler)
        
        # Inicia o bot
        app.run_polling()