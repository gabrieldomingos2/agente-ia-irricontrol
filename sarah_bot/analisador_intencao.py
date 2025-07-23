# analisador_intencao.py
from typing import List, Dict, Tuple

# Agora, as regras incluem um peso (pontuação) para cada palavra-chave
MAPEAMENTO_REGRAS: Dict[str, List[Tuple[str, int]]] = {
    "DOR_ROUBO_PASSADO": [("roubaram", 25), ("fui roubado", 25), ("levaram meus cabos", 25)],
    "DOR_INSEGURANCA_REGIAO": [("muito roubo na região", 15), ("vizinho foi roubado", 15)],
    "DOR_SISTEMA_ATUAL_FALHO": [("meu alarme não funcionou", 20), ("câmera não adianta", 10)],
    "DOR_CUSTO_OPERACIONAL": [("pivô parado", 20), ("perder a safra", 20)],
    "INTENCAO_TECNICA": [("tecnologia", 5), ("satélite", 10), ("jammer", 10)],
    "INTENCAO_ORCAMENTO": [("preço", 15), ("valor", 15), ("quanto custa", 15), ("orçamento", 15)],
    "INTENCAO_PREVENCAO": [("proteger", 10), ("segurança", 5), ("ficar tranquilo", 5)]
}

def analisar_mensagem(mensagem: str) -> Dict:
    """
    Analisa a mensagem, retorna um dicionário com tags detectadas e a pontuação total.
    """
    msg_lower = mensagem.lower()
    tags_detectadas = set()
    score = 0

    for tag, regras in MAPEAMENTO_REGRAS.items():
        for palavra_chave, peso in regras:
            if palavra_chave in msg_lower:
                tags_detectadas.add(tag)
                score += peso
    
    return {"tags": list(tags_detectadas), "score": score}

def formatar_diagnostico_para_prompt(tags: List[str]) -> str:
    """Cria uma frase clara para ser injetada no prompt da Sarah."""
    # (Esta função permanece a mesma, não precisa de alterações)
    if not tags:
        return "Nenhuma dor ou intenção específica detectada. Siga o fluxo padrão de qualificação."

    diagnosticos = {
        "DOR_ROUBO_PASSADO": "O cliente JÁ FOI ROUBADO. Ele está frustrado e buscando uma solução definitiva. VALIDE o sentimento dele antes de tudo.",
        "DOR_INSEGURANCA_REGIAO": "O cliente está com MEDO devido a roubos na região. Use o gatilho de Prova Social ('outros produtores da região...').",
        "DOR_SISTEMA_ATUAL_FALHO": "O cliente está CÉTICO com soluções de segurança. Foque nos DIFERENCIAIS do SAF.",
        "DOR_CUSTO_OPERACIONAL": "A preocupação principal do cliente é o PREJUÍZO da operação parada. Ancore a conversa nos custos.",
        "INTENCAO_TECNICA": "O cliente tem um perfil técnico. Seja direto e use as informações sobre a tecnologia.",
        "INTENCAO_ORCAMENTO": "O cliente quer saber o PREÇO. Responda, mas tente qualificá-lo antes.",
        "INTENCAO_PREVENCAO": "O cliente busca PAZ E TRANQUILIDADE. Foque nos benefícios emocionais."
    }
    descricao_diagnostico = "\n".join([f"- {diagnosticos[tag]}" for tag in tags if tag in diagnosticos])
    return f"Diagnóstico rápido com base na mensagem do cliente:\n{descricao_diagnostico}"