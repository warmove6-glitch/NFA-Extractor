"""
Cria/atualiza usuário administrador inicial.

Uso:
    # Senha via variável de ambiente (recomendado)
    set ADMIN_EMAIL=admin@orgatec.com.br
    set ADMIN_PASSWORD=<senha-forte-aqui>
    python scripts/seed_admin.py

    # Ou interativo (não loga a senha)
    python scripts/seed_admin.py
"""
import getpass
import os
import sys
from pathlib import Path

# Garante que a raiz do projeto esteja no path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    try:
        from src.infrastructure.database_v2 import SessionLocal, User, init_db
        from api.auth.security import hash_password
    except ImportError as exc:
        print(f"❌ Falha ao importar módulos do projeto: {exc}")
        return 1

    email = os.environ.get("ADMIN_EMAIL")
    senha = os.environ.get("ADMIN_PASSWORD")
    nome = os.environ.get("ADMIN_NAME", "Administrador")

    if not email:
        email = input("E-mail do admin: ").strip()
    if not senha:
        senha = getpass.getpass("Senha do admin (min. 12 chars): ")

    if len(senha) < 12:
        print("❌ Senha deve ter no mínimo 12 caracteres.")
        return 2

    init_db()
    db = SessionLocal()
    try:
        existente = db.query(User).filter_by(email=email).first()
        if existente:
            existente.hashed_password = hash_password(senha)
            existente.is_active = True
            db.commit()
            print(f"✅ Senha do usuário {email} atualizada (id={existente.id}).")
        else:
            admin = User(
                nome=nome,
                email=email,
                hashed_password=hash_password(senha),
                role="admin",
                is_active=True,
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
            print(f"✅ Admin criado: {email} (id={admin.id}).")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"❌ Erro: {exc}")
        return 3
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
