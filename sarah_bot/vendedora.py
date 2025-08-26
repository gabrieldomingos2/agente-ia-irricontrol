# vendedora.py
import os
import json
import logging
import re
from dotenv import load_dotenv
from openai import OpenAI, OpenAIError
from typing import Optional, List, Dict, Any
from sarah_bot.prompt_sarah import construir_prompt_sarah

# Configuração
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
modelo_principal = os.getenv("OPENAI_MODEL", "gpt-4o")
modelo_analise = os.getenv("OPENAI_ANALYSIS_MODEL", "gpt-3.5-turbo")

if not api_key:
    raise Exception("🚨 OPENAI_API_KEY não foi carregada. Verifique o .env!")

client = OpenAI(api_key=api_key)
logger = logging.getLogger(__name__)


# --- NOVA FUNÇÃO ---
def extrair_quantidade_da_mensagem(mensagem: str) -> int:
    """
    Usa expressões regulares para extrair de forma confiável o primeiro número
    encontrado em uma mensagem de texto. É mais robusto que a IA para essa tarefa.
    """
    numeros = re.findall(r'\d+', mensagem)
    if numeros:
        logger.info(f"Quantidade extraída da mensagem via regex: {numeros[0]}")
        return int(numeros[0])
    logger.info("Nenhuma quantidade numérica encontrada na mensagem via regex.")
    return 0

def extrair_nome_da_mensagem(mensagem_usuario: str) -> Optional[str]:
    """Usa a IA para extrair apenas o nome próprio de uma frase."""
    prompt = f"""
    Analise a frase a seguir e extraia APENAS o nome próprio da pessoa.
    Frase: "{mensagem_usuario}"
    
    Retorne um objeto JSON com a chave "nome". Se nenhum nome for encontrado, retorne null.
    Exemplos:
    - Frase: "Meu nome é Gabriel" -> {{"nome": "Gabriel"}}
    - Frase: "Pode me chamar de Ana Clara" -> {{"nome": "Ana Clara"}}
    - Frase: "Sou o João" -> {{"nome": "João"}}
    - Frase: "Marcela" -> {{"nome": "Marcela"}}
    - Frase: "Quanto custa o produto?" -> {{"nome": null}}
    """
    try:
        resposta = client.chat.completions.create(
            model=modelo_analise,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        resultado = json.loads(resposta.choices[0].message.content)
        nome = resultado.get("nome")
        if nome:
            logger.info(f"Nome extraído da mensagem '{mensagem_usuario}': '{nome}'")
            return nome.strip().title()
        logger.warning(f"Nenhum nome encontrado na mensagem via IA: '{mensagem_usuario}'")
        return None
    except Exception as e:
        logger.error(f"🚨 Erro ao extrair nome com IA: {e}")
        return None


def analisar_mensagem_com_ia(mensagem_usuario: str, historico_conversa: list) -> dict:
    historico_resumido = json.dumps(historico_conversa[-5:])
    
    prompt_analise = f"""
    Analise a seguinte mensagem de um cliente em potencial para um sistema de segurança no agronegócio.
    Histórico recente da conversa para contexto: {historico_resumido}
    Mensagem do Cliente: "{mensagem_usuario}"

    Sua tarefa é retornar APENAS um objeto JSON válido com a seguinte estrutura:
    {{
        "perfil_detectado": "...",
        "sentimento_principal": "...",
        "tags_relevantes": ["..."],
        "entidades_extraidas": {{ "qtd_pivos": null, "qtd_bombas": null }}
    }}
    
    Exemplos de tags: "SAUDACAO", "INTENCAO_EXPLICACAO_SAF", "INTENCAO_ORCAMENTO", "DOR_INSEGURANCA_REGIAO", "OBJECÃO_PRECO", "INTENCAO_ADIAR_DECISAO", "INTENCAO_FECHAMENTO", "INTENCAO_PEDIR_VIDEO".
    
    REGRAS CRÍTICAS DE EXTRAÇÃO:
    1.  **Explicação vs. Orçamento:**
        - Se a pergunta for sobre "o que é", "como funciona", "me fale mais sobre", a tag é **'INTENCAO_EXPLICACAO_SAF'**.
        - A tag **'INTENCAO_ORCAMENTO'** SÓ deve ser usada para perguntas diretas sobre "preço", "valor", "custo", "orçamento", "cotação".
        - Se a mensagem contiver AMBAS as intenções (ex: "o que é e quanto custa?"), retorne as duas tags: ['INTENCAO_EXPLICACAO_SAF', 'INTENCAO_ORCAMENTO'].
    2.  **Pedido de Vídeo:** Se a mensagem pedir explicitamente para ver um "vídeo", "demonstração" ou "filme", a tag principal deve ser **'INTENCAO_PEDIR_VIDEO'**.
    3.  **Extração de Números:** Extraia 'qtd_pivos' ou 'qtd_bombas' APENAS se o cliente mencionar um número junto de um pedido de ORÇAMENTO.
    4.  **Prioridade de Objeção:** Se detectar 'OBJECÃO_PRECO' ou 'INTENCAO_ADIAR_DECISAO', não extraia nenhuma outra tag de intenção. O foco é a objeção.
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
        return {}


def gerar_resposta_sarah(pergunta: str, cliente_info: Dict[str, Any], estado_conversa: str, historico_conversa: List[Dict[str, str]], perfil_cliente="neutro", tags_detectadas=None):
    prompt = construir_prompt_sarah(pergunta, cliente_info, estado_conversa, historico_conversa, perfil_cliente, tags_detectadas)
    try:
        resposta = client.chat.completions.create(
            model=modelo_principal,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.75,
            max_tokens=450,
        )
        return resposta.choices[0].message.content.strip()
    except OpenAIError as e:
        logger.error(f"🚨 Erro na API da OpenAI ao gerar resposta: {e}", exc_info=True)
        return f"Peço desculpas, {cliente_info.get('nome', 'cliente')}. Estou com uma instabilidade em meu sistema. Poderia, por gentileza, enviar sua mensagem novamente em alguns instantes? 🙏"
    except Exception as e:
        logger.error(f"🚨 Erro inesperado ao gerar resposta: {e}", exc_info=True)
        return "Ops, tive um problema técnico aqui. Pode reformular sua pergunta, por favor?"
