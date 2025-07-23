# vendedora.py
import os
import json
import logging
from dotenv import load_dotenv
from openai import OpenAI, OpenAIError
from sarah_bot.prompt_sarah import construir_prompt_sarah

# Configuração
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
modelo_principal = os.getenv("OPENAI_MODEL", "gpt-4o")
modelo_analise = os.getenv("OPENAI_ANALYSIS_MODEL", "gpt-3.5-turbo") # Modelo mais rápido e barato para análise

if not api_key:
    raise Exception("🚨 OPENAI_API_KEY não foi carregada. Verifique o .env!")

client = OpenAI(api_key=api_key)
logger = logging.getLogger(__name__)

def analisar_mensagem_com_ia(mensagem_usuario: str, historico_conversa: list) -> dict:
    """
    Usa um LLM para extrair intenções, perfil, sentimentos e entidades da mensagem do cliente.
    Retorna um dicionário estruturado.
    """
    historico_resumido = json.dumps(historico_conversa[-4:]) # Pega as últimas 4 trocas para contexto
    
    prompt_analise = f"""
    Analise a seguinte mensagem de um cliente em potencial para um sistema de segurança no agronegócio.
    Histórico recente da conversa para contexto: {historico_resumido}
    Mensagem do Cliente: "{mensagem_usuario}"

    Sua tarefa é retornar APENAS um objeto JSON válido com a seguinte estrutura:
    {{
      "perfil_detectado": "...", // Classifique entre: 'tecnico', 'desconfiado', 'curioso', 'informal', 'direto_ao_ponto', 'neutro'
      "sentimento_principal": "...", // Ex: 'frustracao', 'medo', 'ceticismo', 'curiosidade', 'urgencia', 'neutro'
      "tags_relevantes": ["..."], // Ex: "DOR_ROUBO_PASSADO", "INTENCAO_ORCAMENTO", "INTENCAO_TECNICA", "DOR_CUSTO_OPERACIONAL"
      "entidades_extraidas": {{
        "qtd_pivos": <numero_ou_null>,
        "qtd_bombas": <numero_ou_null>
      }}
    }}
    Se uma informação não for encontrada, retorne null para o campo correspondente ou uma lista vazia.
    IMPORTANTE: Só extraia 'qtd_pivos' ou 'qtd_bombas' se o cliente MENCIONAR um NÚMERO de forma explícita. Se ele apenas cumprimentar ou fizer uma pergunta geral, retorne null ou 0 para essas entidades. NÃO INVENTE NÚMEROS.
    """
    try:
        resposta = client.chat.completions.create(
            model=modelo_analise,
            messages=[{"role": "user", "content": prompt_analise}],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        analise = json.loads(resposta.choices[0].message.content)
        logger.info(f"Análise da IA bem-sucedida: {analise}")
        return analise
    except Exception as e:
        logger.error(f"🚨 Erro na análise com IA: {e}", exc_info=True)
        return {} # Retorna um dicionário vazio em caso de falha para não quebrar o fluxo

def gerar_resposta_sarah(pergunta, nome_cliente, estado_conversa, historico_conversa, perfil_cliente, tags_detectadas):
    """Gera a resposta da Sarah usando o modelo principal."""
    prompt = construir_prompt_sarah(pergunta, nome_cliente, estado_conversa, historico_conversa, perfil_cliente, tags_detectadas)

    try:
        resposta = client.chat.completions.create(
            model=modelo_principal,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=400,
        )
        return resposta.choices[0].message.content.strip()
    except OpenAIError as e:
        logger.error(f"🚨 Erro na API da OpenAI ao gerar resposta: {e}", exc_info=True)
        return f"Peço desculpas, {nome_cliente}. Estou com uma instabilidade em meu sistema. Poderia, por gentileza, enviar sua mensagem novamente em alguns instantes? 🙏"
    except Exception as e:
        logger.error(f"🚨 Erro inesperado ao gerar resposta: {e}", exc_info=True)
        return "Ops, tive um problema técnico aqui. Pode reformular sua pergunta, por favor?"