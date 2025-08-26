# memoria.py
import sqlite3
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any, List

# Caminho para o banco de dados
DATA_DIR = "data"
DB_PATH = os.path.join(DATA_DIR, "sarah_bot.db")

def init_db():
    """Inicializa o banco de dados e cria/atualiza a tabela de clientes."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Cria a tabela se ela não existir, já com os novos campos
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clientes (
        user_id TEXT PRIMARY KEY,
        nome TEXT,
        nome_fazenda TEXT,
        localizacao TEXT,
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
        lead_score INTEGER DEFAULT 0,
        video_enviado INTEGER DEFAULT 0
    )
    """)
    
    # Adiciona as novas colunas se a tabela já existir (para não quebrar bancos antigos)
    colunas_existentes = [desc[1] for desc in cursor.execute("PRAGMA table_info(clientes)").fetchall()]
    if 'nome_fazenda' not in colunas_existentes:
        cursor.execute("ALTER TABLE clientes ADD COLUMN nome_fazenda TEXT")
    if 'localizacao' not in colunas_existentes:
        cursor.execute("ALTER TABLE clientes ADD COLUMN localizacao TEXT")
        
    conn.commit()
    conn.close()

def dict_factory(cursor: sqlite3.Cursor, row: sqlite3.Row) -> Dict[str, Any]:
    # (código inalterado)
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def get_cliente(user_id: str) -> Optional[Dict[str, Any]]:
    # (código inalterado)
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
    cliente = get_cliente(user_id)
    if cliente:
        return cliente
    
    novo_cliente = {
        "user_id": str(user_id),
        "nome": nome_telegram,
        "nome_fazenda": None,
        "localizacao": None,
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
        "video_enviado": 0,
    }

    colunas = ', '.join(novo_cliente.keys())
    placeholders = ', '.join(['?'] * len(novo_cliente))
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(f"INSERT INTO clientes ({colunas}) VALUES ({placeholders})", tuple(novo_cliente.values()))
    conn.commit()
    conn.close()
    
    novo_cliente['historico_conversa'] = []
    novo_cliente['tags_detectadas'] = []
    return novo_cliente

def atualizar_cliente(user_id: str, dados_atualizados: Dict[str, Any]):
    # (código inalterado)
    user_id_str = str(user_id)
    dados_atualizados["data_ultimo_contato"] = datetime.now().isoformat()
    
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
    # (código inalterado)
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

def deletar_cliente(user_id: str):
    # (código inalterado)
    user_id_str = str(user_id)
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM clientes WHERE user_id = ?", (user_id_str,))
            conn.commit()
            return cursor.rowcount > 0 
    except sqlite3.Error as e:
        print(f"Erro ao deletar cliente {user_id_str}: {e}")
        return False