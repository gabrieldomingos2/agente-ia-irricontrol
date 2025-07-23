# memoria.py
import sqlite3
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any, List

# Caminho para o banco de dados corrigido e mais robusto
DATA_DIR = "data"
DB_PATH = os.path.join(DATA_DIR, "sarah_bot.db")

def init_db():
    """Inicializa o banco de dados e cria a tabela de clientes se não existir."""
    # Garante que o diretório 'data' exista
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clientes (
        user_id TEXT PRIMARY KEY,
        nome TEXT,
        perfil TEXT,
        pivos INTEGER,
        bombas INTEGER,
        estado_conversa TEXT,
        data_criacao TEXT,
        data_ultimo_contato TEXT,
        dor_mencionada TEXT,
        orcamento_enviado REAL,
        follow_up_enviado INTEGER,
        historico_conversa TEXT,
        tags_detectadas TEXT,
        lead_score INTEGER DEFAULT 0
    )
    """)
    conn.commit()
    conn.close()

def dict_factory(cursor: sqlite3.Cursor, row: sqlite3.Row) -> Dict[str, Any]:
    """Converte as linhas do banco de dados em dicionários."""
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def get_cliente(user_id: str) -> Optional[Dict[str, Any]]:
    """Recupera um cliente do banco de dados."""
    user_id_str = str(user_id)
    try:
        conn = sqlite3.connect(DB_PATH, uri=True)
        conn.row_factory = dict_factory
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM clientes WHERE user_id = ?", (user_id_str,))
        cliente = cursor.fetchone()
        conn.close()
        if cliente:
            if cliente.get('historico_conversa'):
                cliente['historico_conversa'] = json.loads(cliente['historico_conversa'])
            if cliente.get('tags_detectadas'):
                cliente['tags_detectadas'] = json.loads(cliente['tags_detectadas'])
        return cliente
    except (sqlite3.OperationalError, FileNotFoundError):
        return None


def recuperar_ou_criar_cliente(user_id: str, nome_telegram: str) -> Dict[str, Any]:
    """Busca um cliente. Se não existir, cria um registro e o retorna."""
    user_id_str = str(user_id)
    cliente = get_cliente(user_id_str)
    if cliente:
        return cliente
    
    novo_cliente = {
        "user_id": user_id_str,
        "nome": nome_telegram,
        "perfil": "indefinido",
        "pivos": 0,
        "bombas": 0,
        "estado_conversa": "INICIANTE",
        "data_criacao": datetime.now().isoformat(),
        "data_ultimo_contato": datetime.now().isoformat(),
        "dor_mencionada": None,
        "orcamento_enviado": 0.0,
        "follow_up_enviado": 0,
        "historico_conversa": "[]",
        "tags_detectadas": "[]",
        "lead_score": 0,
    }

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO clientes (user_id, nome, perfil, pivos, bombas, estado_conversa, data_criacao, data_ultimo_contato, dor_mencionada, orcamento_enviado, follow_up_enviado, historico_conversa, tags_detectadas, lead_score)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, tuple(novo_cliente.values()))
    conn.commit()
    conn.close()
    
    novo_cliente['historico_conversa'] = []
    novo_cliente['tags_detectadas'] = []
    return novo_cliente

def atualizar_cliente(user_id: str, dados_atualizados: Dict[str, Any]):
    """Atualiza os dados de um cliente específico no banco de dados."""
    user_id_str = str(user_id)
    dados_atualizados["data_ultimo_contato"] = datetime.now().isoformat()
    
    # Prepara os dados para inserção segura
    update_values = {}
    for key, value in dados_atualizados.items():
        if isinstance(value, (list, dict)):
            update_values[key] = json.dumps(value, ensure_ascii=False)
        else:
            update_values[key] = value

    update_fields = ", ".join([f"{key} = ?" for key in update_values])
    values = list(update_values.values()) + [user_id_str]
    
    query = f"UPDATE clientes SET {update_fields} WHERE user_id = ?"
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(query, tuple(values))
        conn.commit()

def adicionar_mensagem_historico(user_id: str, role: str, content: str):
    """Adiciona uma nova mensagem ao histórico do cliente."""
    cliente = get_cliente(user_id)
    if not cliente:
        return

    historico = cliente.get("historico_conversa", [])
    if not isinstance(historico, list):
        historico = []
        
    historico.append({"role": role, "content": content})
    
    max_historico = 30
    historico = historico[-max_historico:]
    
    atualizar_cliente(user_id, {"historico_conversa": historico})

def obter_clientes_para_follow_up() -> List[Dict[str, Any]]:
    """Busca todos os clientes que estão no estágio de orçamento apresentado."""
    try:
        conn = sqlite3.connect(DB_PATH, uri=True)
        conn.row_factory = dict_factory
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM clientes WHERE estado_conversa = 'ORCAMENTO_APRESENTADO'")
        clientes = cursor.fetchall()
        conn.close()
        return clientes
    except (sqlite3.OperationalError, FileNotFoundError):
        return []
    
    

def deletar_cliente(user_id: str):
    """Deleta um cliente do banco de dados com base no user_id."""
    user_id_str = str(user_id)
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM clientes WHERE user_id = ?", (user_id_str,))
            conn.commit()
            return cursor.rowcount > 0 # Retorna True se alguma linha foi deletada
    except sqlite3.Error as e:
        # Em produção, o ideal seria usar o logger aqui também
        print(f"Erro ao deletar cliente {user_id_str}: {e}")
        return False    