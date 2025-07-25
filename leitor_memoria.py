# leitor_memoria.py
import sqlite3
import json

# Caminho do banco de dados corrigido
DB_PATH = "data/sarah_bot.db"

def ler_conversa_cliente():
    """Lê e exibe o histórico e os dados de um cliente específico."""
    user_id = input("Digite o ID do usuário para ver os dados: ")

    if not user_id.strip():
        print("❌ ID do usuário não pode ser vazio.")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM clientes WHERE user_id = ?", (user_id,))
        cliente = cursor.fetchone()
        conn.close()

        if cliente:
            print("\n" + "="*50)
            print(f"🔍 DADOS DO CLIENTE: {cliente['nome']} (ID: {user_id})")
            print("="*50)
            print(f"  - Perfil: {cliente['perfil']}")
            print(f"  - Estado da Conversa: {cliente['estado_conversa']}")
            print(f"  - Lead Score: {cliente['lead_score']}")
            print(f"  - Nome da Fazenda: {cliente['nome_fazenda'] or 'Não informado'}")
            print(f"  - Localização: {cliente['localizacao'] or 'Não informada'}")
            print(f"  - Dor Mencionada: {cliente['dor_mencionada'] or 'Não informada'}")
            print(f"  - Orçamento Enviado (Valor): R$ {cliente['orcamento_enviado'] or 0:.2f}")
            print(f"  - Notificação de Lead Quente Enviada: {'Sim' if cliente['notificacao_enviada'] else 'Não'}")
            
            tags_json = cliente.get('tags_detectadas', '[]')
            tags_lista = json.loads(tags_json)
            print(f"  - Tags Detectadas: {tags_lista if tags_lista else 'Nenhuma'}")
            
            historico_json = cliente.get('historico_conversa', '[]')
            historico = json.loads(historico_json)

            print("\n" + "="*50)
            print("💬 HISTÓRICO DA CONVERSA")
            print("="*50)

            if not historico:
                print("Ainda não há mensagens no histórico.")
            else:
                for mensagem in historico:
                    role = mensagem.get("role", "desconhecido").upper()
                    content = mensagem.get("content", "")
                    
                    if role == 'USER':
                        print(f"👤  CLIENTE: {content}\n")
                    else:
                        print(f"🤖  SARAH: {content}\n")
            print("="*50)
        else:
            print(f"Nenhum cliente encontrado com o ID: {user_id}")

    except (sqlite3.Error, FileNotFoundError) as e:
        print(f"Erro de banco de dados ou arquivo não encontrado: {e}")
    except json.JSONDecodeError as e:
        print(f"Erro ao ler os dados. O formato JSON parece estar corrompido: {e}")
    except Exception as e:
        print(f"Ocorreu um erro inesperado: {e}")

if __name__ == "__main__":
    ler_conversa_cliente()