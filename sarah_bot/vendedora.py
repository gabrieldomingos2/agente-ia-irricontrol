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


# --- FUNÇÕES DE EXTRAÇÃO DE DADOS ---

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
    - Frase: "Meu nome é Gabriel Fazenda Sol Nascente" -> {{"nome": "Gabriel"}}
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
        if nome and isinstance(nome, str):
            logger.info(f"Nome extraído da mensagem '{mensagem_usuario}': '{nome}'")
            return nome.strip().title()
        logger.warning(f"Nenhum nome encontrado na mensagem via IA: '{mensagem_usuario}'")
        return None
    except (OpenAIError, json.JSONDecodeError) as e:
        logger.error(f"🚨 Erro ao extrair nome com IA: {e}", exc_info=True)
        return None


# --- FUNÇÃO PRINCIPAL DE ANÁLISE ---

def analisar_mensagem_com_ia(mensagem_usuario: str, historico_conversa: list) -> dict:
    """
    Analisa a mensagem do usuário para extrair intenções, perfil, sentimento e entidades.
    Usa um modelo de IA mais rápido e barato para essa tarefa de classificação.
    """
    historico_resumido = json.dumps(historico_conversa[-5:], ensure_ascii=False)
    
    prompt_analise = f"""
    Analise a seguinte mensagem de um cliente e o histórico da conversa para um sistema de segurança no agronegócio (SAF).

    **Contexto:** O SAF é um sistema antifurto para pivôs de irrigação e casas de bomba.
    **Histórico Recente:** {historico_resumido}
    **Mensagem Atual do Cliente:** "{mensagem_usuario}"

    **Sua Tarefa:** Retorne um objeto JSON VÁLIDO e sem comentários com a seguinte estrutura. Preencha todos os campos.

    {{
        "perfil_detectado": "...",        // analitico, direto, afavel, expressivo
        "sentimento_principal": "...",   // neutro, positivo, negativo, preocupado, urgente
        "tags_relevantes": ["..."],      // Lista de tags aplicáveis
        "entidades_extraidas": {{
            "nome_fazenda": "...",       // Extraia o nome da propriedade, se mencionado. Ex: "Fazenda Sol", "Sítio Boa Esperança".
            "localizacao": "..."         // Extraia a cidade/estado, se mencionado. Ex: "Cristalina-GO", "região de Unaí".
        }}
    }}
    
    **GUIA DE TAGS (Use apenas as tags desta lista):**
    - "SAUDACAO": Cumprimentos iniciais.
    - "PEDIDO_INFORMACOES_GERAIS": Perguntas abertas como "o que é?", "como funciona?".
    - "PEDIDO_ORCAMENTO": Perguntas diretas sobre "preço", "valor", "custo", "orçamento", "cotação".
    - "DOR_FURTO_PROPRIO": O cliente relata que JÁ FOI roubado.
    - "DOR_INSEGURANCA_REGIAO": O cliente relata medo ou insegurança na sua região.
    - "OBJECÃO_PRECO": O cliente afirma que o produto é "caro", "custoso", ou questiona o valor.
    - "OBJECÃO_ADIAMENTO": O cliente diz "vou pensar", "vou analisar", "preciso ver com meu sócio".
    - "INTENCAO_FECHAMENTO": O cliente demonstra interesse claro em comprar. Ex: "como faço pra contratar?", "quero fechar".
    - "PEDIDO_VIDEO": Pede explicitamente por um "vídeo", "demonstração" ou "filme".
    - "INFORMOU_QUANTIDADE": O cliente informa a quantidade de equipamentos que possui.

    **REGRAS CRÍTICAS DE EXTRAÇÃO:**
    1.  **Orçamento vs. Informação:** Se a pergunta é sobre "o que é e quanto custa?", use as tags `PEDIDO_INFORMACOES_GERAIS` e `PEDIDO_ORCAMENTO`.
    2.  **Prioridade de Objeção:** Se detectar `OBJECÃO_PRECO` ou `OBJECÃO_ADIAMENTO`, estas são as tags mais importantes.
    3.  **Entidades:** Extraia `nome_fazenda` e `localizacao` apenas se mencionados explicitamente. Se não, retorne null.
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
        # Validação básica da estrutura para evitar erros posteriores
        if isinstance(analise, dict) and "tags_relevantes" in analise:
            return analise
        else:
            logger.error(f"🚨 Análise da IA retornou um formato inesperado: {analise}")
            return {}

    except (OpenAIError, json.JSONDecodeError) as e:
        logger.error(f"🚨 Erro na análise com IA: {e}", exc_info=True)
        return {} # Retorna um dicionário vazio em caso de erro para não quebrar o fluxo principal


# --- FUNÇÃO PRINCIPAL DE GERAÇÃO DE RESPOSTA ---

def gerar_resposta_sarah(pergunta: str, cliente_info: Dict[str, Any], estado_conversa: str, historico_conversa: List[Dict[str, str]], perfil_cliente="neutro", tags_detectadas=None):
    """
    Gera a resposta da Sarah usando o modelo de IA principal, com base em todo o contexto.
    """
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
    except Exception as e: # Captura outras exceções inesperadas
        logger.error(f"🚨 Erro inesperado ao gerar resposta: {e}", exc_info=True)
        return "Ops, tive um problema técnico aqui. Pode reformular sua pergunta, por favor?"
