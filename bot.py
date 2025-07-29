# bot.py (v26.4 - Correção Definitiva de Prazo)
import os
import logging
import requests
import asyncio
import urllib.parse
import re
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, MessageHandler, ContextTypes, filters,
    CommandHandler, CallbackQueryHandler
)
from telegram.constants import ChatAction, ParseMode
from typing import Tuple, List, Dict, Any, Optional

# --- Importações e Configurações ---
from sarah_bot.config import (BOT_TOKEN, GERENTE_CHAT_ID, LIMITE_LEAD_QUENTE, VIDEO_DEMO_FILE_ID, TAG_WEIGHTS, GUIA_PDF_URL, SUPERVISOR_WHATSAPP_NUMERO)
from sarah_bot.memoria import (init_db, recuperar_ou_criar_cliente, atualizar_cliente, adicionar_mensagem_historico, deletar_cliente, get_cliente)
from sarah_bot.orcamento import (gerar_orcamento, formatar_resposta_orcamento, formatar_resposta_orcamento_inicial)
from sarah_bot.vendedora import (analisar_mensagem_com_ia, gerar_resposta_sarah, extrair_nome_da_mensagem, extrair_quantidade_da_mensagem, gerar_resumo_para_gerente)

# --- Configuração de Logging Estruturado ---
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


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exceção ao processar uma atualização:", exc_info=context.error)
    if isinstance(update, Update) and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Ops! Encontrei um problema técnico. 😥 Já estou trabalhando para resolver. Por favor, tente enviar sua mensagem novamente em alguns instantes."
            )
        except Exception as e:
            logger.error(f"Não foi possível enviar a mensagem de erro ao usuário {update.effective_chat.id}. Erro: {e}")

def escape_markdown_v2(text: str) -> str:
    if not isinstance(text, str): return ""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return "".join(f'\\{char}' if char in escape_chars else char for char in text)

def notificar_vendedor_humano(cliente, motivo="LEAD QUENTE", resumo_ia=""):
    if not GERENTE_CHAT_ID:
        logger.warning("GERENTE_CHAT_ID não definido. Não é possível enviar alerta.")
        return False
        
    motivos = {
        "LEAD QUENTE": ("🔥 ALERTA DE LEAD QUENTE\\! 🔥", "Ação recomendada: Entrar em contato com o cliente\\."),
        "FECHAMENTO": ("✅ CLIENTE PRONTO PARA FECHAR\\! ✅", "Ação recomendada: Entrar em contato IMEDIATAMENTE\\.")
    }
    titulo, acao = motivos.get(motivo, motivos["LEAD QUENTE"])
    nome_cliente = escape_markdown_v2(cliente.get('nome', 'N/A'))
    nome_fazenda = escape_markdown_v2(cliente.get('nome_fazenda', 'N/A'))
    localizacao = escape_markdown_v2(cliente.get('localizacao', 'N/A'))
    dor_mencionada = escape_markdown_v2(cliente.get('dor_mencionada', 'Não informada'))
    tags_str = escape_markdown_v2(", ".join(cliente.get('tags_detectadas', [])))
    score = cliente.get('lead_score', 0)
    user_id = cliente.get('user_id')
    resumo_formatado = escape_markdown_v2(resumo_ia)

    qtd_pivos = cliente.get('pivos', 0)
    qtd_bombas = cliente.get('bombas', 0)
    orcamento_str = ""
    if qtd_pivos > 0 or qtd_bombas > 0:
        total_pontos = qtd_pivos + qtd_bombas
        orcamento_str = (
            f"📦 *Orçamento Solicitado:*\n"
            f"   •  *{total_pontos} Ponto\\(s\\) de SAF*\n"
            f"   •  Pivôs: `{qtd_pivos}`\n"
            f"   •  Casas de Bomba: `{qtd_bombas}`\n\n"
        )

    mensagem = (
        f"*{titulo}*\n\n"
        f"👤 *Cliente:* {nome_cliente} \\(ID: `{user_id}`\\)\n"
        f"⭐ *Lead Score:* *{score}*\n\n"
        f"🗒️ *Resumo da IA:*\n`{resumo_formatado}`\n\n"
        f"{orcamento_str}"
        f"🏡 *Propriedade:* {nome_fazenda}\n"
        f"📍 *Localização:* {localizacao}\n"
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

# --- COMANDOS DO BOT ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    nome_telegram = update.effective_user.first_name
    recuperar_ou_criar_cliente(user_id, nome_telegram)
    dados_iniciais = {"nome": nome_telegram, "estado_conversa": "QUALIFICACAO_INICIADA"}
    atualizar_cliente(user_id, dados_iniciais)
    mensagem = "Sou Sarah, especialista em segurança rural da Irricontrol. Para um atendimento mais preciso, preciso de algumas informações.\n\nPrimeiro, como posso te chamar?"
    await update.message.reply_text(mensagem)
    adicionar_mensagem_historico(user_id, "assistant", mensagem)
    atualizar_cliente(user_id, {"estado_conversa": "AGUARDANDO_NOME"})

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"Recebido comando /reset do usuário {user_id}. Apagando dados.")
    if deletar_cliente(str(user_id)):
        await update.message.reply_text("Prontinho! Esqueci nosso histórico e comecei do zero. 😊")
        await start_command(update, context)
    else:
        await update.message.reply_text("Hmm, parece que não encontrei seu registro para apagar ou ocorreu um erro.")

async def pausar_conversa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != GERENTE_CHAT_ID:
        await update.message.reply_text("⛔ Você não tem permissão para usar este comando.")
        return
    try:
        user_id_alvo = context.args[0]
        cliente = get_cliente(user_id_alvo)
        if cliente and cliente.get('estado_conversa') != 'PAUSADO_PELO_GERENTE':
            dados_para_atualizar = {
                'estado_conversa_anterior': cliente['estado_conversa'],
                'estado_conversa': 'PAUSADO_PELO_GERENTE'
            }
            atualizar_cliente(user_id_alvo, dados_para_atualizar)
            await update.message.reply_text(f"✅ Conversa com o usuário {user_id_alvo} ({cliente['nome']}) foi pausada.")
            await context.bot.send_message(chat_id=user_id_alvo, text="Um de nossos especialistas em segurança está analisando seu caso e responderá em breve. Agradeço a paciência! 😊")
        elif cliente:
            await update.message.reply_text(f"A conversa com {cliente['nome']} já está pausada.")
        else:
            await update.message.reply_text("Usuário não encontrado.")
    except (IndexError, ValueError):
        await update.message.reply_text("Uso incorreto. Use: /pausar <user_id>")

async def reativar_conversa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != GERENTE_CHAT_ID:
        await update.message.reply_text("⛔ Você não tem permissão para usar este comando.")
        return
    try:
        user_id_alvo = context.args[0]
        cliente = get_cliente(user_id_alvo)
        if cliente and cliente.get('estado_conversa') == 'PAUSADO_PELO_GERENTE':
            estado_anterior = cliente.get('estado_conversa_anterior', 'CONVERSA_IA')
            atualizar_cliente(user_id_alvo, {'estado_conversa': estado_anterior, 'estado_conversa_anterior': None})
            await update.message.reply_text(f"✅ Conversa com o usuário {user_id_alvo} ({cliente['nome']}) foi reativada.")
        elif cliente:
            await update.message.reply_text(f"A conversa com {cliente['nome']} não está pausada.")
        else:
            await update.message.reply_text("Usuário não encontrado.")
    except (IndexError, ValueError):
        await update.message.reply_text("Uso incorreto. Use: /reativar <user_id>")

async def oferecer_guia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != GERENTE_CHAT_ID:
        await update.message.reply_text("⛔ Você não tem permissão para usar este comando.")
        return
    try:
        user_id_alvo = context.args[0]
        cliente = get_cliente(user_id_alvo)
        if not cliente:
            await update.message.reply_text("Usuário não encontrado."); return
        atualizar_cliente(user_id_alvo, {'estado_conversa': 'OFERECENDO_VALOR'})
        cliente_atualizado = get_cliente(user_id_alvo)
        resposta_oferta = gerar_resposta_sarah(
            "Olá!", cliente_atualizado, 'OFERECENDO_VALOR', cliente_atualizado.get('historico_conversa', []), cliente_atualizado.get('perfil')
        )
        await context.bot.send_message(chat_id=user_id_alvo, text=resposta_oferta)
        adicionar_mensagem_historico(user_id_alvo, "assistant", f"[GATILHO DE RECIPROCIDADE]\n{resposta_oferta}")
        await update.message.reply_text(f"✅ Oferta do guia enviada para {cliente['nome']} ({user_id_alvo}).")
    except (IndexError, ValueError):
        await update.message.reply_text("Uso incorreto. Use: /oferecer_guia <user_id>")

# --- LÓGICA DE CONVERSA ---

async def fluxo_de_qualificacao(update: Update, context: ContextTypes.DEFAULT_TYPE, cliente: dict):
    user_id = str(update.effective_user.id)
    estado_atual = cliente["estado_conversa"]
    mensagem_usuario = update.message.text
    adicionar_mensagem_historico(user_id, "user", mensagem_usuario)
    dados_para_atualizar = {}
    proxima_mensagem = ""
    
    if estado_atual == "AGUARDANDO_NOME":
        dados_para_atualizar["nome"] = mensagem_usuario.strip().title()
        proxima_mensagem = f"Prazer, {dados_para_atualizar['nome']}! Para continuar, em qual cidade e estado fica sua propriedade?"
        dados_para_atualizar["estado_conversa"] = "AGUARDANDO_LOCALIZACAO"
    elif estado_atual == "AGUARDANDO_LOCALIZACAO":
        dados_para_atualizar["localizacao"] = mensagem_usuario.strip()
        proxima_mensagem = "Entendido. E qual sua principal preocupação com segurança hoje? Por favor, selecione uma das opções abaixo."
        keyboard = [
            [InlineKeyboardButton("Roubo de cabos/equipamentos", callback_data="dor_roubo")],
            [InlineKeyboardButton("Insegurança geral na região", callback_data="dor_inseguranca")],
            [InlineKeyboardButton("Apenas pesquisando valores", callback_data="dor_pesquisa")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(proxima_mensagem, reply_markup=reply_markup)
        adicionar_mensagem_historico(user_id, "assistant", proxima_mensagem + " [Botões enviados]")
        dados_para_atualizar["estado_conversa"] = "AGUARDANDO_DOR"

    if dados_para_atualizar:
        atualizar_cliente(user_id, dados_para_atualizar)
    if proxima_mensagem and estado_atual != "AGUARDANDO_LOCALIZACAO":
        await update.message.reply_text(proxima_mensagem)
        adicionar_mensagem_historico(user_id, "assistant", proxima_mensagem)

def _extrair_numero_da_resposta(texto: str) -> int:
    texto = texto.lower()
    if 'nenhum' in texto or 'zero' in texto:
        return 0
    numeros = re.findall(r'\d+', texto)
    return int(numeros[0]) if numeros else -1

async def fluxo_de_orcamento(update: Update, context: ContextTypes.DEFAULT_TYPE, cliente: dict):
    user_id = str(update.effective_user.id)
    estado_atual = cliente['estado_conversa']
    mensagem_usuario = update.message.text
    adicionar_mensagem_historico(user_id, "user", mensagem_usuario)

    quantidade_informada = _extrair_numero_da_resposta(mensagem_usuario)
    if quantidade_informada == -1:
        await update.message.reply_text("Não entendi. Por favor, digite um número (como 1, 2, 3...) ou a palavra 'nenhum'.")
        return

    if estado_atual == "AGUARDANDO_QTD_PIVOS":
        atualizar_cliente(user_id, {"pivos": quantidade_informada})
        pergunta_bombas = "Entendido. E quantas **casas de bomba** você precisa proteger?"
        await update.message.reply_text(pergunta_bombas, parse_mode=ParseMode.MARKDOWN)
        adicionar_mensagem_historico(user_id, "assistant", pergunta_bombas)
        atualizar_cliente(user_id, {"estado_conversa": "AGUARDANDO_QTD_BOMBAS"})
    
    elif estado_atual == "AGUARDANDO_QTD_BOMBAS":
        atualizar_cliente(user_id, {"bombas": quantidade_informada})
        cliente_atualizado = get_cliente(user_id)
        
        qtd_pivos = cliente_atualizado.get('pivos', 0)
        qtd_bombas = cliente_atualizado.get('bombas', 0)

        if qtd_pivos == 0 and qtd_bombas == 0:
            await update.message.reply_text("Ok, sem problemas! Se precisar de mais alguma informação ou mudar de ideia, é só chamar. Estou à disposição! 😊")
            atualizar_cliente(user_id, {"estado_conversa": "CONVERSA_IA"})
            return

        await update.message.reply_text("Perfeito! Calculando sua proposta personalizada...")
        await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)
        
        total_eq, val_eq, val_inst, total_geral = gerar_orcamento(qtd_pivos, qtd_bombas)
        resposta_orcamento = formatar_resposta_orcamento(cliente['nome'], qtd_pivos, qtd_bombas, val_eq, val_inst, total_geral)
        pergunta_fechamento = gerar_resposta_sarah("Ok, enviei o orçamento.", cliente_atualizado, 'ORCAMENTO_APRESENTADO', cliente_atualizado['historico_conversa'])
        
        resposta_final = f"{resposta_orcamento}\n\n{pergunta_fechamento}"
        keyboard = [[InlineKeyboardButton("Falar com um Supervisor para fechar", callback_data="falar_supervisor")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(resposta_final, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        adicionar_mensagem_historico(user_id, "assistant", resposta_final)
        atualizar_cliente(user_id, {'estado_conversa': 'ORCAMENTO_APRESENTADO', 'orcamento_enviado': total_geral})

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    callback_data = query.data
    cliente = get_cliente(user_id)

    if callback_data.startswith("dor_"):
        mapa_dores = {"dor_roubo": "Roubo de cabos e equipamentos", "dor_inseguranca": "Insegurança geral na região", "dor_pesquisa": "Apenas pesquisando valores"}
        dor_selecionada = mapa_dores.get(callback_data)

        if callback_data == "dor_pesquisa":
            await query.edit_message_text(text=f"Sua intenção: {dor_selecionada}.")
            await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)
            resposta_inteligente = gerar_resposta_sarah("O cliente disse que está apenas pesquisando valores.", cliente, "LIDANDO_COM_CURIOSIDADE", cliente['historico_conversa'])
            keyboard = [[InlineKeyboardButton("Sim, quero ver o vídeo", callback_data="ver_solucao")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(chat_id=user_id, text=resposta_inteligente, reply_markup=reply_markup)
            adicionar_mensagem_historico(user_id, "assistant", resposta_inteligente)
            atualizar_cliente(user_id, {"estado_conversa": "AGUARDANDO_CONFIRMACAO_SOLUCAO"})
        else:
            await query.edit_message_text(text=f"Sua preocupação: {dor_selecionada}.")
            atualizar_cliente(user_id, {"dor_mencionada": dor_selecionada, "tags_detectadas": [callback_data.upper()]})
            cliente_atualizado = get_cliente(user_id)
            nome_cliente = cliente_atualizado.get('nome', 'Cliente')
            mensagem_empatia = f"{nome_cliente}, eu entendo perfeitamente sua preocupação com '{dor_selecionada.lower()}'. É uma situação desgastante que tira o foco do que realmente importa: a produção.\n\nFelizmente, existe uma solução tecnológica definitiva para esse problema."
            keyboard = [[InlineKeyboardButton("Quero conhecer a solução", callback_data="ver_solucao")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(chat_id=user_id, text=mensagem_empatia, reply_markup=reply_markup)
            adicionar_mensagem_historico(user_id, "assistant", f"[Qualificação Finalizada] Dor: {dor_selecionada}")
            adicionar_mensagem_historico(user_id, "assistant", mensagem_empatia)
            atualizar_cliente(user_id, {"estado_conversa": "AGUARDANDO_CONFIRMACAO_SOLUCAO"})

    elif callback_data == "ver_solucao":
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(chat_id=user_id, text="✅ Ótima decisão! Preparando a apresentação...")
        await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)
        mensagem_frame_valor = gerar_resposta_sarah("O cliente quer conhecer a solução.", cliente, "FRAME_DE_VALOR_SOLUCAO", cliente['historico_conversa'])
        keyboard = [[InlineKeyboardButton("Ver detalhes e vídeo do SAF", callback_data="mostrar_detalhes_video")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id=user_id, text=mensagem_frame_valor, reply_markup=reply_markup)
        adicionar_mensagem_historico(user_id, "assistant", mensagem_frame_valor)
        atualizar_cliente(user_id, {"estado_conversa": "AGUARDANDO_DETALHES_VIDEO"})

    elif callback_data == "mostrar_detalhes_video":
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(chat_id=user_id, text="✅ Perfeito! Preparando a apresentação completa...")
        await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)
        explicacao_completa = gerar_resposta_sarah("O cliente quer ver os detalhes da solução.", cliente, "APRESENTANDO_SOLUCAO_COMPLETA", cliente['historico_conversa'])
        await context.bot.send_message(chat_id=user_id, text=explicacao_completa, parse_mode=ParseMode.HTML)
        adicionar_mensagem_historico(user_id, "assistant", explicacao_completa)
        await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.UPLOAD_VIDEO)
        await context.bot.send_video(chat_id=user_id, video=VIDEO_DEMO_FILE_ID)
        adicionar_mensagem_historico(user_id, "assistant", "[VÍDEO DE DEMONSTRAÇÃO ENVIADO]")
        await asyncio.sleep(1)
        pergunta_feedback = "Gostaria de saber mais sobre o valor do nosso produto?"
        keyboard = [[InlineKeyboardButton("Saber mais sobre o valor do SAF", callback_data="saber_valor")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id=user_id, text=pergunta_feedback, reply_markup=reply_markup)
        adicionar_mensagem_historico(user_id, "assistant", pergunta_feedback)
        atualizar_cliente(user_id, {"estado_conversa": "AGUARDANDO_RESPOSTA_VALOR", "video_enviado": 1})

    elif callback_data == "saber_valor":
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)
        mensagem_de_valor = gerar_resposta_sarah("O cliente quer saber o valor.", cliente, "APRESENTANDO_VALOR_PRODUTO", cliente['historico_conversa'])
        await context.bot.send_message(chat_id=user_id, text=mensagem_de_valor)
        adicionar_mensagem_historico(user_id, "assistant", mensagem_de_valor)
        await asyncio.sleep(1.5)
        resposta_orcamento_inicial = formatar_resposta_orcamento_inicial(cliente['nome'])
        await context.bot.send_message(chat_id=user_id, text=resposta_orcamento_inicial, parse_mode=ParseMode.HTML)
        adicionar_mensagem_historico(user_id, "assistant", resposta_orcamento_inicial)
        await asyncio.sleep(1)
        pergunta_pivos_estrategica = gerar_resposta_sarah("Acabei de mostrar o preço unitário.", cliente, "SOLICITANDO_QUANTIDADE_ESTRATEGICA", cliente['historico_conversa'])
        await context.bot.send_message(chat_id=user_id, text=pergunta_pivos_estrategica, parse_mode=ParseMode.MARKDOWN)
        adicionar_mensagem_historico(user_id, "assistant", pergunta_pivos_estrategica)
        atualizar_cliente(user_id, {"estado_conversa": "AGUARDANDO_QTD_PIVOS"})

    elif callback_data == "falar_supervisor":
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(chat_id=user_id, text="✅ Ótima escolha! Conectando você com nosso supervisor...")
        resumo_ia = gerar_resumo_para_gerente(cliente.get('historico_conversa', []))
        notificar_vendedor_humano(cliente, motivo="FECHAMENTO", resumo_ia=resumo_ia)
        texto_whatsapp = (f"Olá! Gostaria de falar sobre o sistema SAF.\n\n"
                        f"Meu nome: {cliente.get('nome')}\n"
                        f"Localização: {cliente.get('localizacao')}\n"
                        f"Minha principal preocupação é: {cliente.get('dor_mencionada')}")
        texto_whatsapp_encoded = urllib.parse.quote(texto_whatsapp)
        link_whatsapp = f"https://wa.me/{SUPERVISOR_WHATSAPP_NUMERO}?text={texto_whatsapp_encoded}"
        mensagem_final = (f"Para agilizar seu atendimento, clique no link abaixo para falar diretamente com nosso supervisor de vendas no WhatsApp. Ele já recebeu suas informações e está pronto para te ajudar a finalizar a proposta.\n\n"
                        f"🔗 [Clique aqui para falar com o Supervisor]({link_whatsapp})")
        await context.bot.send_message(chat_id=user_id, text=mensagem_final, parse_mode=ParseMode.MARKDOWN)
        adicionar_mensagem_historico(user_id, "assistant", mensagem_final)
        mensagem_acompanhamento = "Enquanto isso, posso te ajudar com mais alguma informação sobre o sistema SAF?"
        await context.bot.send_message(chat_id=user_id, text=mensagem_acompanhamento)
        adicionar_mensagem_historico(user_id, "assistant", mensagem_acompanhamento)
        atualizar_cliente(user_id, {"estado_conversa": "CONVERSA_IA"})

def _calcular_novo_score(score_atual: int, tags_novas: set) -> int:
    incremento = sum(TAG_WEIGHTS.get(tag, 0) for tag in tags_novas)
    return score_atual + incremento

async def conversa_geral_ia(update: Update, context: ContextTypes.DEFAULT_TYPE, cliente: dict):
    user_id = str(update.effective_user.id)
    mensagem_usuario = update.message.text
    await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)
    adicionar_mensagem_historico(user_id, "user", mensagem_usuario)
    
    analise_ia = analisar_mensagem_com_ia(mensagem_usuario, cliente.get("historico_conversa", []))
    tags = set(analise_ia.get("tags_relevantes", []))
    dados_para_atualizar = {}

    entidades = analise_ia.get("entidades_extraidas", {})
    if entidades.get("nome_fazenda"): dados_para_atualizar["nome_fazenda"] = entidades["nome_fazenda"]
    perfil_cliente_detectado = analise_ia.get("perfil_detectado", cliente.get("perfil"))
    dados_para_atualizar['perfil'] = perfil_cliente_detectado
    
    proximo_estado = "CONVERSA_IA"
    if "QUESTIONAMENTO_PRAZO_ENTREGA" in tags:
        proximo_estado = 'RESPONDENDO_PRAZO_ENTREGA'
    elif "OBJECÃO_PRECO" in tags or "OBJECÃO_ADIAMENTO" in tags:
        proximo_estado = 'QUEBRANDO_OBJECAO'
    elif "INTENCAO_FECHAMENTO" in tags:
        proximo_estado = 'FECHAMENTO'

    resposta_bot = gerar_resposta_sarah(mensagem_usuario, cliente, proximo_estado, cliente['historico_conversa'])
    dados_para_atualizar['estado_conversa'] = proximo_estado

    novo_score = _calcular_novo_score(cliente.get('lead_score', 0), tags)
    score_historico = cliente.get('lead_score_historico', [])
    if not score_historico or score_historico[-1]['score'] != novo_score:
        score_historico.append({"score": novo_score, "timestamp": datetime.now().isoformat()})
    tags_acumuladas = list(set(cliente.get("tags_detectadas", [])).union(tags))
    dados_para_atualizar.update({"tags_detectadas": tags_acumuladas, "lead_score": novo_score, "lead_score_historico": score_historico})

    if dados_para_atualizar:
        atualizar_cliente(user_id, dados_para_atualizar)
    if resposta_bot:
        await update.message.reply_text(resposta_bot, parse_mode=ParseMode.HTML)
        adicionar_mensagem_historico(user_id, "assistant", resposta_bot)
    
    cliente_atualizado = get_cliente(user_id)
    notificacao_ja_enviada = cliente.get('notificacao_enviada', 0)
    score_atual = cliente_atualizado.get('lead_score', 0)
    motivo_notificacao = "FECHAMENTO" if "INTENCAO_FECHAMENTO" in tags else ("LEAD QUENTE" if score_atual >= LIMITE_LEAD_QUENTE and not notificacao_ja_enviada else None)
    if motivo_notificacao:
        resumo_ia = gerar_resumo_para_gerente(cliente_atualizado.get('historico_conversa', []))
        if notificar_vendedor_humano(cliente_atualizado, motivo=motivo_notificacao, resumo_ia=resumo_ia):
            atualizar_cliente(user_id, {"notificacao_enviada": 1})

async def roteador_de_mensagem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    user_id = str(update.effective_user.id)
    cliente = recuperar_ou_criar_cliente(user_id, update.effective_user.first_name)
    estado_conversa = cliente.get("estado_conversa")

    if estado_conversa == "PAUSADO_PELO_GERENTE":
        logger.info(f"Conversa com {user_id} está pausada. Ignorando mensagem.")
        return
    
    if estado_conversa in ["QUALIFICACAO_INICIADA", "AGUARDANDO_NOME", "AGUARDANDO_LOCALIZACAO"]:
        await fluxo_de_qualificacao(update, context, cliente)
    
    elif estado_conversa in ["AGUARDANDO_QTD_PIVOS", "AGUARDANDO_QTD_BOMBAS"]:
        await fluxo_de_orcamento(update, context, cliente)

    elif estado_conversa in ["AGUARDANDO_DOR", "AGUARDANDO_CONFIRMACAO_SOLUCAO", "AGUARDANDO_RESPOSTA_VALOR", "AGUARDANDO_DETALHES_VIDEO"]:
        logger.info(f"Usuário {user_id} enviou texto em vez de clicar no botão. Aguardando clique.")
        await context.bot.send_message(chat_id=user_id, text="Por favor, selecione uma das opções acima para continuar. 😊")
    else:
        await conversa_geral_ia(update, context, cliente)


if __name__ == "__main__":
    init_db()
    logger.info("🤖 Sarah Bot (v26.4 - Tratamento de Curiosidade) está no ar!")
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CommandHandler("pausar", pausar_conversa))
    app.add_handler(CommandHandler("reativar", reativar_conversa))
    app.add_handler(CommandHandler("oferecer_guia", oferecer_guia))
    app.add_handler(CallbackQueryHandler(callback_query_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, roteador_de_mensagem))
    app.add_error_handler(error_handler)
    app.run_polling()