# follow_up_bot.py (v17.0 - Follow-up Direto)
import os
import asyncio
import logging
from datetime import datetime, timedelta
from telegram import Bot
from dotenv import load_dotenv

from sarah_bot.memoria import obter_clientes_para_follow_up, obter_clientes_ativos, atualizar_cliente, adicionar_mensagem_historico, init_db

# --- Configuração de Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("data/follow_up.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
PONTOS_DECAIMENTO_POR_DIA = 2

# Mensagens de follow-up mais diretas e curtas
MSG_FOLLOW_UP_1 = "Olá, {nome}. Aqui é a Sarah, da Irricontrol. Conseguiu analisar a proposta do sistema SAF? Fico à disposição para esclarecer qualquer dúvida."
MSG_FOLLOW_UP_2 = "Olá, {nome}. Nossa agenda de instalação do SAF para sua região está bem movimentada para as próximas semanas. Ainda há interesse em proteger sua operação?"

async def rodar_follow_up():
    logger.info("🤖 Iniciando rotina de manutenção e follow-up...")
    bot = Bot(token=BOT_TOKEN)
    
    # --- 1. LÓGICA DE DECAIMENTO DO SCORE ---
    clientes_ativos = obter_clientes_ativos()
    logger.info(f"  -> Encontrados {len(clientes_ativos)} clientes ativos para verificação de decaimento de score.")
    
    now = datetime.now()
    for cliente in clientes_ativos:
        user_id = cliente["user_id"]
        data_ultimo_contato = datetime.fromisoformat(cliente["data_ultimo_contato"])
        dias_passados = (now - data_ultimo_contato).days
        
        if dias_passados > 0 and cliente.get("lead_score", 0) > 0:
            decaimento = dias_passados * PONTOS_DECAIMENTO_POR_DIA
            score_antigo = cliente["lead_score"]
            novo_score = max(0, score_antigo - decaimento)

            if novo_score < score_antigo:
                logger.info(f"  -> Aplicando decaimento para {cliente['nome']} ({user_id}). Score: {score_antigo} -> {novo_score}")
                dados_decay = {"lead_score": novo_score}
                
                score_historico = cliente.get('lead_score_historico', [])
                if not score_historico or score_historico[-1]['score'] != novo_score:
                    score_historico.append({"score": novo_score, "timestamp": now.isoformat()})
                    dados_decay['lead_score_historico'] = score_historico

                atualizar_cliente(user_id, dados_decay)
    
    # --- 2. LÓGICA DE MENSAGENS DE FOLLOW-UP ---
    clientes_para_follow_up = obter_clientes_para_follow_up()
    logger.info(f"  -> Encontrados {len(clientes_para_follow_up)} clientes com orçamento apresentado para possível follow-up.")

    for cliente in clientes_para_follow_up:
        user_id = cliente["user_id"]
        data_ultimo_contato = datetime.fromisoformat(cliente["data_ultimo_contato"])
        dias_passados = (now - data_ultimo_contato).days
        
        mensagem_a_enviar = None
        proximo_nivel_follow_up = cliente.get("follow_up_enviado", 0)
        dados_para_atualizar = {}

        if dias_passados >= 3 and proximo_nivel_follow_up == 0:
            logger.info(f"  -> Cliente {cliente['nome']} ({user_id}) qualificado para Follow-up Nível 1.")
            mensagem_a_enviar = MSG_FOLLOW_UP_1.format(nome=cliente['nome'])
            dados_para_atualizar["follow_up_enviado"] = 1
        
        elif dias_passados >= 7 and proximo_nivel_follow_up == 1:
            logger.info(f"  -> Cliente {cliente['nome']} ({user_id}) qualificado para Follow-up Nível 2.")
            mensagem_a_enviar = MSG_FOLLOW_UP_2.format(nome=cliente['nome'])
            dados_para_atualizar["follow_up_enviado"] = 2
            dados_para_atualizar["estado_conversa"] = "FOLLOW_UP_FINALIZADO"
        
        if mensagem_a_enviar:
            try:
                await bot.send_message(chat_id=user_id, text=mensagem_a_enviar)
                logger.info(f"     ✅ Mensagem de follow-up enviada com sucesso para {cliente['nome']}.")
                
                atualizar_cliente(user_id, dados_para_atualizar)
                adicionar_mensagem_historico(user_id, "assistant", f"[FOLLOW-UP AUTOMÁTICO]\n{mensagem_a_enviar}")
                
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"     ❌ Erro ao enviar mensagem de follow-up para {user_id}: {e}", exc_info=True)

    logger.info("🏁 Rotina de follow-up finalizada.")

if __name__ == "__main__":
    init_db()
    asyncio.run(rodar_follow_up())