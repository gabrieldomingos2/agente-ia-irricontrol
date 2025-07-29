# vendedora.py (v26.2 - Reconhecimento de Prazo)
import json
import logging
import re
from openai import OpenAI, OpenAIError
from typing import Optional, List, Dict, Any

# --- Importação de Configurações e Prompts ---
from sarah_bot.config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_ANALYSIS_MODEL
from sarah_bot.prompt_sarah import construir_prompt_sarah

# --- Configuração do Cliente OpenAI ---
client = OpenAI(api_key=OPENAI_API_KEY)
logger = logging.getLogger(__name__)


# --- FUNÇÕES DE EXTRAÇÃO DE DADOS ---

def extrair_quantidade_da_mensagem(mensagem: str) -> int:
    """Usa expressões regulares para extrair de forma confiável o primeiro número encontrado."""
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
    - Frase: "Quanto custa o produto?" -> {{"nome": null}}
    """
    try:
        resposta = client.chat.completions.create(
            model=OPENAI_ANALYSIS_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        resultado = json.loads(resposta.choices[0].message.content)
        nome = resultado.get("nome")
        if nome and isinstance(nome, str):
            logger.info(f"Nome extraído da mensagem '{mensagem_usuario}': '{nome}'")
            return nome.strip().title()
        return None
    except (OpenAIError, json.JSONDecodeError) as e:
        logger.error(f"🚨 Erro ao extrair nome com IA: {e}", exc_info=True)
        return None


# --- FUNÇÃO PRINCIPAL DE ANÁLISE ---

def analisar_mensagem_com_ia(mensagem_usuario: str, historico_conversa: list) -> dict:
    """Analisa a mensagem do usuário para extrair intenções, perfil, sentimento e entidades."""
    historico_resumido = json.dumps(historico_conversa[-5:], ensure_ascii=False)
    
    prompt_analise = f"""
    Analise a seguinte mensagem de um cliente e o histórico da conversa para um sistema de segurança no agronegócio (SAF).
    **Histórico Recente:** {historico_resumido}
    **Mensagem Atual do Cliente:** "{mensagem_usuario}"

    **Sua Tarefa:** Retorne um objeto JSON VÁLIDO com a estrutura abaixo. Preencha todos os campos.
    {{
        "perfil_detectado": "...",
        "sentimento_principal": "...",
        "tags_relevantes": ["..."],
        "entidades_extraidas": {{"nome_fazenda": "...", "localizacao": "..."}},
        "etapa_jornada": "..."
    }}
    
    **GUIA DE ETAPA DA JORNADA:**
    - "DESCOBERTA": O cliente está aprendendo, perguntando "como funciona?", "o que é?".
    - "CONSIDERACAO": O cliente está comparando, perguntando "qual o valor?", "por que é melhor que X?", "qual o prazo?".
    - "DECISAO": O cliente está pronto para agir, dizendo "quero comprar", "como pago?", "vamos fechar".

    **GUIA DE TAGS:** [SAUDACAO, PEDIDO_INFORMACOES_GERAIS, PEDIDO_ORCAMENTO, DOR_FURTO_PROPRIO, DOR_INSEGURANCA_REGIAO, OBJECÃO_PRECO, OBJECÃO_ADIAMENTO, INTENCAO_FECHAMENTO, PEDIDO_VIDEO, INFORMOU_QUANTIDADE, APENAS_CURIOSIDADE, CONCORRENTE_MENCIONADO, FORA_DE_ESCOPO, QUESTIONAMENTO_PRAZO_ENTREGA]

    **Exemplos de Análise (Use como guia principal):**
    - Mensagem: "como funciona?" -> {{"etapa_jornada": "DESCOBERTA", "tags_relevantes": ["PEDIDO_INFORMACOES_GERAIS"]}}
    - Mensagem: "qual o valor?" -> {{"etapa_jornada": "CONSIDERACAO", "tags_relevantes": ["PEDIDO_ORCAMENTO"]}}
    - Mensagem: "quanto custa para 2 pivos?" -> {{"etapa_jornada": "CONSIDERACAO", "tags_relevantes": ["PEDIDO_ORCAMENTO", "INFORMOU_QUANTIDADE"]}}
    - Mensagem: "quero comprar" -> {{"etapa_jornada": "DECISAO", "tags_relevantes": ["INTENCAO_FECHAMENTO"]}}
    - Mensagem: "qual o prazo de instalação?" -> {{"etapa_jornada": "CONSIDERACAO", "tags_relevantes": ["QUESTIONAMENTO_PRAZO_ENTREGA"]}}
    """
    try:
        resposta = client.chat.completions.create(
            model=OPENAI_ANALYSIS_MODEL,
            messages=[{"role": "user", "content": prompt_analise}],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        analise = json.loads(resposta.choices[0].message.content)
        logger.info(f"Análise da IA bem-sucedida: {analise}")
        if isinstance(analise, dict) and "tags_relevantes" in analise:
            return analise
        else:
            return {}
    except (OpenAIError, json.JSONDecodeError) as e:
        logger.error(f"🚨 Erro na análise com IA: {e}", exc_info=True)
        return {}


# --- FUNÇÃO PRINCIPAL DE GERAÇÃO DE RESPOSTA ---

def gerar_resposta_sarah(pergunta: str, cliente_info: Dict[str, Any], estado_conversa: str, historico_conversa: List[Dict[str, str]], perfil_cliente="neutro", tags_detectadas=None, usar_gatilho_escassez=False):
    """Gera a resposta da Sarah usando o modelo de IA principal, com base em todo o contexto."""
    prompt = construir_prompt_sarah(pergunta, cliente_info, estado_conversa, historico_conversa, perfil_cliente, tags_detectadas, usar_gatilho_escassez)
    try:
        resposta = client.chat.completions.create(
            model=OPENAI_MODEL,
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


# --- NOVAS FUNÇÕES COM IA ---

def gerar_resumo_para_gerente(historico_conversa: List[Dict[str, str]]) -> str:
    """Usa a IA para gerar um resumo conciso da conversa para um vendedor humano."""
    if not historico_conversa:
        return "Nenhum histórico de conversa disponível."

    historico_formatado = "\n".join(
        [f"{'Cliente' if msg['role'] == 'user' else 'Sarah'}: {msg['content']}" for msg in historico_conversa]
    )
    
    prompt = f"""
    Analise o seguinte histórico de conversa entre a vendedora Sarah e um cliente.
    Sua tarefa é criar um resumo de no máximo 3 linhas para o gerente de vendas.
    O resumo deve ser direto, em português, e focar em:
    1. A principal "dor" ou necessidade do cliente.
    2. O último ponto discutido ou a última pergunta feita pelo cliente.
    3. O sentimento geral do cliente (ex: interessado, cético, pronto para comprar).
    Histórico da Conversa:
    ---
    {historico_formatado}
    ---
    Gere apenas o texto do resumo.
    """
    try:
        resposta = client.chat.completions.create(
            model=OPENAI_ANALYSIS_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=150,
        )
        resumo = resposta.choices[0].message.content.strip()
        logger.info(f"Resumo da IA para gerente gerado com sucesso.")
        return resumo
    except OpenAIError as e:
        logger.error(f"🚨 Erro ao gerar resumo com IA: {e}")
        return "Não foi possível gerar o resumo da conversa."

def gerar_follow_up_personalizado(cliente_info: dict) -> str:
    """Usa a IA para gerar uma mensagem de follow-up única e pessoal."""
    # (Esta função não foi alterada, mas é mantida por completude)
    historico_conversa = cliente_info.get('historico_conversa', [])
    historico_formatado = "\n".join(
        [f"{'Cliente' if msg['role'] == 'user' else 'Sarah'}: {msg['content']}" for msg in historico_conversa[-10:]]
    )

    prompt = f"""
    Você é Sarah, a vendedora. Crie uma mensagem de follow-up curta e pessoal para reengajar um cliente.
    **Contexto do Cliente:**
    - **Nome:** {cliente_info.get('nome')}
    - **Principal Dor Mencionada:** {cliente_info.get('dor_mencionada')}
    - **Últimas mensagens:**
    {historico_formatado}
    **Regras:**
    1. Seja amigável, use o nome do cliente.
    2. Mencione sutilmente a dor que ele compartilhou.
    3. Termine com uma pergunta aberta e de baixa pressão.
    4. NÃO mencione "follow-up". Soe natural.
    Gere apenas o texto da mensagem.
    """
    try:
        resposta = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=250,
        )
        mensagem = resposta.choices[0].message.content.strip()
        logger.info(f"Follow-up personalizado para {cliente_info.get('user_id')} gerado com sucesso.")
        return mensagem
    except OpenAIError as e:
        logger.error(f"🚨 Erro ao gerar follow-up com IA: {e}")
        return f"Olá, {cliente_info.get('nome')}! Tudo bem? Passando para saber se conseguiu avaliar a proposta do sistema SAF. Ficou alguma dúvida? Estou à disposição!"