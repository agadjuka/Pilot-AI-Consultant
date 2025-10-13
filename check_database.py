"""Скрипт для проверки содержимого базы данных"""
from app.core.database import get_session_local
from app.models.service import Service
from app.models.master import Master

def main():
    SessionLocal = get_session_local()
    db = SessionLocal()
    
    try:
        services = db.query(Service).all()
        masters = db.query(Master).all()
        
        print("\n" + "="*60)
        print("СОДЕРЖИМОЕ БАЗЫ ДАННЫХ")
        print("="*60)
        
        print(f"\n📋 Услуги ({len(services)}):")
        for service in services:
            print(f"  • {service.name} - {service.price}₽ ({service.duration_minutes} мин)")
        
        print(f"\n👤 Мастера ({len(masters)}):")
        for master in masters:
            master_services = [s.name for s in master.services]
            print(f"  • {master.name}")
            print(f"    Услуги: {', '.join(master_services)}")
        
        print("\n" + "="*60 + "\n")
        
    finally:
        db.close()

if __name__ == "__main__":
    main()

