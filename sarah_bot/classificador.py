# classificador.py

def classificar_perfil(mensagem):
    """
    Analisa a mensagem para classificar o perfil com base em um sistema de pontuação.
    Isso evita classificações erradas quando uma mensagem contém palavras de vários perfis.
    """
    msg = mensagem.lower()
    scores = {"tecnico": 0, "desconfiado": 0, "informal": 0, "curioso": 0}

    # Palavras-chave e seus pesos. Pesos maiores indicam maior certeza do perfil.
    regras = {
        "desconfiado": [("preço", 2), ("quanto custa", 2), ("valor", 2), ("funciona", 1), ("é seguro", 1), ("garantia", 1)],
        "tecnico": [("sistema", 2), ("tecnologia", 2), ("satélite", 1), ("automatização", 1), ("como funciona", 1), ("integrar", 1)],
        "curioso": [("saber mais", 2), ("me explica", 2), ("como é", 1), ("detalhes", 1)],
        "informal": [("oi", 1), ("e aí", 1), ("bom dia", 1), ("boa tarde", 1), ("tudo bem", 1), 
                    ("roubo", -1), ("ladrão", -1)] # Termos que podem aparecer em qualquer perfil, peso menor.
    }

    for perfil, palavras in regras.items():
        for palavra, peso in palavras:
            if palavra in msg:
                scores[perfil] += peso
    
    # Se nenhuma palavra-chave foi encontrada, retorna neutro.
    if not any(scores.values()):
        return "neutro"
        
    # Retorna o perfil com a maior pontuação.
    perfil_final = max(scores, key=scores.get)
    return perfil_final


def obter_mensagem_boas_vindas(perfil, nome_cliente):
    """
    Retorna uma mensagem de boas-vindas personalizada com base no perfil detectado.
    (Esta função permanece a mesma, pois já era excelente).
    """
    mensagens = {
        "tecnico": f"Olá, {nome_cliente}! 👨‍💻 Sou a Sarah, da Irricontrol. Vi seu interesse no nosso sistema. Ele usa tecnologia de satélite criptografada para monitoramento preciso. Antes de detalharmos a arquitetura, me diga, por favor: qual tecnologia você utiliza hoje para a gestão da sua propriedade?",

        "desconfiado": f"Olá, {nome_cliente}. Sou a Sarah, da Irricontrol. Direto ao ponto: sim, a tecnologia funciona e é extremamente segura. Para eu te provar isso, me conta uma coisa: qual foi a sua maior dor de cabeça com segurança na fazenda até hoje?",

        "informal": f"E aí, {nome_cliente}! 😄 Aqui é a Sarah. Vamos resolver essa questão da segurança? Me conta, já teve problema com roubo de equipamento por aí? Tô aqui pra te ajudar a botar um cadeado nisso de vez!",

        "curioso": f"Olá, {nome_cliente}! Que bom ver seu interesse. Sou a Sarah, e vou te mostrar como o sistema SAF pode trazer mais tranquilidade para a sua operação. Para começar, você já utiliza algum tipo de monitoramento ou segurança eletrônica atualmente?",

        "neutro": f"Olá, {nome_cliente}! 😊 Tudo bem? Sou a Sarah, consultora de segurança da Irricontrol. Para eu entender como posso te ajudar, me conta: como você cuida da segurança dos seus pivôs e bombas hoje?"
    }
    return mensagens.get(perfil, mensagens["neutro"])