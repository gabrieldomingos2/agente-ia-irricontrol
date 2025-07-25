# follow_up_bot.py
import os
import asyncio
import logging
from datetime import datetime
from telegram import Bot
from dotenv import load_dotenv

# Importa as funções necessárias da memória, incluindo a nova que criamos
from sarah_bot.memoria import obter_clientes_para_follow_up, atualizar_cliente, adicionar_mensagem_historico, init_db

# --- Configuração de Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("data/follow_up.log", mode='a', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# --- MENSAGENS DE FOLLOW-UP APRIMORADAS E PERSONALIZADAS ---
MSG_FOLLOW_UP_1 = (
    "Olá, {nome}! Tudo bem por aí?\n\n"
    "Aqui é a Sarah, da Irricontrol. Passando para saber se você conseguiu analisar a proposta do sistema SAF. "
    "Lembro que sua preocupação era com '{dor_mencionada}', e queria ter certeza de que a solução que apresentei faz sentido para resolver isso.\n\n"
    "Ficou alguma dúvida que eu possa ajudar a esclarecer? Estou à disposição! 🌾"
)

MSG_FOLLOW_UP_2 = (
    "Oi, {nome}. Espero que esteja tudo certo.\n\n"
    "Lembrei de você pois estamos fechando a agenda de instalações do SAF para as próximas semanas aqui na sua região. "
    "Muitos produtores que também se preocupavam com a segurança dos seus pivôs já garantiram essa tranquilidade para focar 100% na produção.\n\n"
    "Ainda faz sentido para você esse investimento na segurança da sua operação?"
)

async def rodar_follow_up():
    logger.info("🤖 Iniciando rotina de follow-up...")
    if not BOT_TOKEN:
        logger.critical("BOT_TOKEN não encontrado. A rotina de follow-up não pode ser executada.")
        return
        
    bot = Bot(token=BOT_TOKEN)
    clientes_para_follow_up = obter_clientes_para_follow_up()
    
    logger.info(f"  -> Encontrados {len(clientes_para_follow_up)} clientes qualificados para follow-up.")

    for cliente in clientes_para_follow_up:
        user_id = cliente["user_id"]
        try:
            data_ultimo_contato = datetime.fromisoformat(cliente["data_ultimo_contato"])
            dias_passados = (datetime.now() - data_ultimo_contato).days
            
            mensagem_a_enviar = None
            dados_para_atualizar = {}
            proximo_nivel_follow_up = cliente.get("follow_up_enviado", 0)

            # Follow-up Nível 1 (3 dias após o orçamento)
            if dias_passados >= 3 and proximo_nivel_follow_up == 0:
                logger.info(f"  -> Cliente {cliente['nome']} ({user_id}) qualificado para Follow-up Nível 1.")
                dor = cliente.get('dor_mencionada', 'a segurança dos seus equipamentos')
                mensagem_a_enviar = MSG_FOLLOW_UP_1.format(nome=cliente['nome'], dor_mencionada=dor)
                dados_para_atualizar["follow_up_enviado"] = 1
            
            # Follow-up Nível 2 (7 dias após o último contato)
            elif dias_passados >= 7 and proximo_nivel_follow_up == 1:
                logger.info(f"  -> Cliente {cliente['nome']} ({user_id}) qualificado para Follow-up Nível 2.")
                mensagem_a_enviar = MSG_FOLLOW_UP_2.format(nome=cliente['nome'])
                dados_para_atualizar["follow_up_enviado"] = 2
                dados_para_atualizar["estado_conversa"] = "FOLLOW_UP_FINALIZADO" # Muda o estado do lead
            
            if mensagem_a_enviar:
                await bot.send_message(chat_id=user_id, text=mensagem_a_enviar)
                logger.info(f"     ✅ Mensagem de follow-up enviada com sucesso para {cliente['nome']}.")
                
                # Atualiza o cliente no banco de dados
                atualizar_cliente(user_id, dados_para_atualizar)
                # Adiciona o follow-up ao histórico para manter o contexto
                adicionar_mensagem_historico(user_id, "assistant", f"[FOLLOW-UP AUTOMÁTICO]\n{mensagem_a_enviar}")
                
                await asyncio.sleep(1) # Pausa de 1 segundo para não sobrecarregar a API do Telegram
        except Exception as e:
            logger.error(f"     ❌ Erro ao processar follow-up para {user_id}: {e}", exc_info=True)

    logger.info("🏁 Rotina de follow-up finalizada.")

if __name__ == "__main__":
    # Garante que a tabela do DB está atualizada antes de rodar
    init_db()
    asyncio.run(rodar_follow_up())