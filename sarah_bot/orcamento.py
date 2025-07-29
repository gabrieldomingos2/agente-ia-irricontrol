# orcamento.py (v26.0 - Foco no Preço Unitário)

# Importa as configurações de preço do módulo centralizado
from sarah_bot.config import PRECO_SAF, PRECO_INSTALACAO, MENSALIDADE

def gerar_orcamento(qtd_pivos=0, qtd_bombas=0):
    """Calcula os valores totais para um orçamento com base na quantidade de equipamentos."""
    total_equipamentos = qtd_pivos + qtd_bombas
    valor_total_equipamentos = total_equipamentos * PRECO_SAF
    valor_total_instalacao = total_equipamentos * PRECO_INSTALACAO
    total_geral_inicial = valor_total_equipamentos + valor_total_instalacao
    return total_equipamentos, valor_total_equipamentos, valor_total_instalacao, total_geral_inicial

def formatar_resposta_orcamento_inicial(nome):
    """
    Cria a resposta inicial para um pedido de preço, focando no valor e ancorando o preço de uma unidade.
    NÃO pergunta mais a quantidade aqui.
    """
    f_preco_saf = f"{PRECO_SAF:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    f_preco_instalacao = f"{PRECO_INSTALACAO:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    f_mensalidade = f"{MENSALIDADE:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    return (
        f"Excelente pergunta, {nome}. Proteger um ativo que vale centenas de milhares de reais é um investimento muito inteligente.\n\n"
        f"Para você ter uma ideia, o investimento para blindar **1 equipamento** com o SAF é:\n\n"
        f"🛡️ *Equipamento SAF:* `R$ {f_preco_saf}`\n"
        f"🛠️ *Instalação Profissional:* `R$ {f_preco_instalacao}`\n\n"
        f"Depois disso, a tranquilidade custa apenas `R$ {f_mensalidade}` por mês para o monitoramento 24h via satélite, mesmo nos locais mais remotos."
    )


def formatar_resposta_orcamento(nome, qtd_pivos, qtd_bombas, valor_equipamentos, valor_instalacao, total_geral):
    """
    Formata uma resposta de orçamento de forma visual e clara para chats.
    """
    total_equipamentos = qtd_pivos + qtd_bombas
    partes = []
    if qtd_pivos > 0: partes.append(f"{qtd_pivos} pivô(s)")
    if qtd_bombas > 0: partes.append(f"{qtd_bombas} casa(s) de bomba")
    itens = " e ".join(partes)

    f_valor_equipamentos = f"{valor_equipamentos:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    f_valor_instalacao = f"{valor_instalacao:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    f_total_geral = f"{total_geral:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    
    f_mensalidade_unitaria = f"{MENSALIDADE:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    mensagem = (
        f"Perfeito, {nome}! 📄✨\n"
        f"Preparei o orçamento detalhado para a proteção completa dos seus **{itens}**:\n\n"
        f"**💰 INVESTIMENTO INICIAL**\n"
        f"──────────────────\n"
        f"🛡️  *Equipamentos SAF ({total_equipamentos} un.):* `R$ {f_valor_equipamentos}`\n"
        f"🛠️  *Instalação Profissional:* `R$ {f_valor_instalacao}`\n\n"
        f"✅  **TOTAL DO INVESTIMENTO:**\n"
        f"## R$ {f_total_geral}\n"
        f"──────────────────\n\n"
        f"**🌙 MENSALIDADE**\n"
        f"──────────────────\n"
        f"📡  *Monitoramento 24h:* `R$ {f_mensalidade_unitaria} por equipamento`\n"
        f"──────────────────\n\n"
        "Com o sistema ativo, você reduz drasticamente o risco de roubo, evita perdas na produção e garante tranquilidade 24h por dia!"
    )
    return mensagem