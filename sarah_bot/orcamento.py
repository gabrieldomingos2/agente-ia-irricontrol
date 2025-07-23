# orcamento.py
import os
from dotenv import load_dotenv

load_dotenv()

PRECO_SAF = float(os.getenv("PRECO_SAF", 11900))
PRECO_INSTALACAO = float(os.getenv("PRECO_INSTALACAO", 2500))
MENSALIDADE = float(os.getenv("MENSALIDADE", 150))

def gerar_orcamento(qtd_pivos=0, qtd_bombas=0):
    total_equipamentos = qtd_pivos + qtd_bombas
    valor_total_equipamentos = total_equipamentos * PRECO_SAF
    valor_total_instalacao = total_equipamentos * PRECO_INSTALACAO
    total_geral_inicial = valor_total_equipamentos + valor_total_instalacao
    return total_equipamentos, valor_total_equipamentos, valor_total_instalacao, total_geral_inicial

def formatar_resposta_orcamento(nome, qtd_pivos, qtd_bombas, valor_equipamentos, valor_instalacao, total_geral):
    partes = []
    if qtd_pivos: partes.append(f"{qtd_pivos} pivô(s)")
    if qtd_bombas: partes.append(f"{qtd_bombas} casa(s) de bomba")
    itens = " e ".join(partes)
    total_equipamentos = qtd_pivos + qtd_bombas
    valor_mensalidade_total = total_equipamentos * MENSALIDADE

    return (f"Perfeito, {nome}! Preparei uma simulação para proteger seus {itens}. Veja como é simples ter paz de espírito:\n\n"
            f"**INVESTIMENTO NA SUA SEGURANÇA**\n\n"
            f"📦 **Sistema Antifurto SAF:**\n"
            f"   - Valor: R$ {valor_equipamentos:,.2f} (para {total_equipamentos} pontos)\n"
            f"   - *Tecnologia militar de satélite, imune a 'chupa-cabras', com bateria de longa duração.*\n\n"
            f"🔧 **Instalação Profissional Irricontrol:**\n"
            f"   - Valor: R$ {valor_instalacao:,.2f}\n"
            f"   - *Nossa equipe vai até sua fazenda e deixa tudo 100% funcional.*\n\n"
            f"------------------------------------\n"
            f"💎 **Investimento Total Inicial:** **R$ {total_geral:,.2f}**\n"
            f"------------------------------------\n\n"
            f"📡 **Monitoramento 24h/dia:**\n"
            f"   - Mensalidade: R$ {MENSALIDADE:,.2f} por equipamento.\n"
            f"   - *Sua fazenda vigiada dia e noite, com alertas direto no seu celular.*\n\n"
            f"Este investimento, {nome}, representa uma fração do prejuízo que um único furto pode causar. Analise com calma e me diga o que acha!")