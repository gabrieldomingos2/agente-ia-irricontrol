# follow_up_bot.py
import os
import asyncio
from datetime import datetime
from telegram import Bot
from dotenv import load_dotenv

# Imports Corrigidos
from sarah_bot.memoria import obter_clientes_para_follow_up, atualizar_cliente, adicionar_mensagem_historico, init_db

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

MSG_FOLLOW_UP_1 = "Olá, {nome}! Tudo bem por aí?\n\nAqui é a Sarah, da Irricontrol. Passando para saber se você conseguiu analisar a proposta do sistema SAF que te enviei.\n\nFicou alguma dúvida que eu possa ajudar a esclarecer? Estou à disposição! 🌾"
MSG_FOLLOW_UP_2 = "Oi, {nome}. Espero que esteja tudo certo.\n\nLembrei de você pois estamos fechando a agenda de instalações do SAF para as próximas semanas aqui na sua região. Muitos produtores já garantiram essa tranquilidade para focar 100% na produção.\n\nAinda faz sentido para você esse investimento em segurança?"

async def rodar_follow_up():
    print(f"[{datetime.now()}] 🤖 Iniciando rotina de follow-up...")
    bot = Bot(token=BOT_TOKEN)
    clientes_para_follow_up = obter_clientes_para_follow_up()
    
    print(f"  -> Encontrados {len(clientes_para_follow_up)} clientes com orçamento apresentado.")

    for cliente in clientes_para_follow_up:
        user_id = cliente["user_id"]
        data_ultimo_contato = datetime.fromisoformat(cliente["data_ultimo_contato"])
        dias_passados = (datetime.now() - data_ultimo_contato).days
        
        mensagem_a_enviar = None
        proximo_nivel_follow_up = cliente.get("follow_up_enviado", 0)
        dados_para_atualizar = {}

        if dias_passados >= 3 and proximo_nivel_follow_up == 0:
            print(f"  -> Cliente {cliente['nome']} ({user_id}) qualificado para Follow-up Nível 1.")
            mensagem_a_enviar = MSG_FOLLOW_UP_1.format(nome=cliente['nome'])
            dados_para_atualizar["follow_up_enviado"] = 1
        
        elif dias_passados >= 7 and proximo_nivel_follow_up == 1:
            print(f"  -> Cliente {cliente['nome']} ({user_id}) qualificado para Follow-up Nível 2.")
            mensagem_a_enviar = MSG_FOLLOW_UP_2.format(nome=cliente['nome'])
            dados_para_atualizar["follow_up_enviado"] = 2
            dados_para_atualizar["estado_conversa"] = "FOLLOW_UP_FINALIZADO"
        
        if mensagem_a_enviar:
            try:
                await bot.send_message(chat_id=user_id, text=mensagem_a_enviar)
                print(f"     ✅ Mensagem enviada com sucesso para {cliente['nome']}.")
                
                atualizar_cliente(user_id, dados_para_atualizar)
                adicionar_mensagem_historico(user_id, "assistant", f"[FOLLOW-UP AUTOMÁTICO]\n{mensagem_a_enviar}")
                
                await asyncio.sleep(1)
            except Exception as e:
                print(f"     ❌ Erro ao enviar mensagem para {user_id}: {e}")

    print("🏁 Rotina de follow-up finalizada.")

if __name__ == "__main__":
    init_db()
    asyncio.run(rodar_follow_up())