# vendedora.py
from dotenv import load_dotenv
import os
from openai import OpenAI, OpenAIError
# Import Corrigido
from sarah_bot.prompt_sarah import construir_prompt_sarah

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
modelo = os.getenv("OPENAI_MODEL", "gpt-4o")

if not api_key:
    raise Exception("🚨 OPENAI_API_KEY não foi carregada. Verifique o .env!")

client = OpenAI(api_key=api_key)

def gerar_resposta_sarah(pergunta, nome_cliente, estado_conversa, historico_conversa, perfil_cliente="neutro", tags_detectadas=None):
    if tags_detectadas is None:
        tags_detectadas = []
        
    prompt = construir_prompt_sarah(pergunta, nome_cliente, estado_conversa, historico_conversa, perfil_cliente, tags_detectadas)

    try:
        resposta = client.chat.completions.create(
            model=modelo,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=400,
        )
        return resposta.choices[0].message.content.strip()
    except OpenAIError as e:
        print(f"🚨 Erro na API da OpenAI: {e}")
        return f"Peço desculpas, {nome_cliente}. Estou com uma instabilidade em meu sistema. Poderia, por gentileza, enviar sua mensagem novamente em alguns instantes? 🙏"
    except Exception as e:
        print(f"🚨 Erro inesperado: {e}")
        return "Ops, tive um problema técnico aqui. Pode reformular sua pergunta, por favor?"