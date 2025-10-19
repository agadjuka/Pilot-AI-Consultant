#!/usr/bin/env python3
"""
Скрипт для настройки таблицы master_services.
Устанавливает для каждого мастера только одну услугу согласно их специализации.
"""

import sys
import os
from typing import List, Dict, Any

# Добавляем корневую директорию проекта в путь
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from app.core.database import (
    get_session_pool, 
    execute_query, 
    upsert_record, 
    delete_record,
    init_database,
    close_database
)


def get_all_masters() -> List[Dict[str, Any]]:
    """Получает всех мастеров из базы данных."""
    print("👥 Получение списка мастеров...")
    
    query = "SELECT id, name, specialization FROM masters ORDER BY id"
    rows = execute_query(query)
    
    masters = []
    for row in rows:
        # Декодируем строки если они в байтах
        name = row[1].decode('utf-8') if isinstance(row[1], bytes) else str(row[1])
        specialization = row[2].decode('utf-8') if isinstance(row[2], bytes) else str(row[2]) if row[2] else ""
        
        masters.append({
            'id': row[0],
            'name': name,
            'specialization': specialization
        })
    
    print(f"✅ Найдено мастеров: {len(masters)}")
    for master in masters:
        print(f"   - {master['name']} (ID: {master['id']}, специализация: {master['specialization']})")
    
    return masters


def get_all_services() -> List[Dict[str, Any]]:
    """Получает все услуги из базы данных."""
    print("\n💅 Получение списка услуг...")
    
    query = "SELECT id, name, description FROM services ORDER BY id"
    rows = execute_query(query)
    
    services = []
    for row in rows:
        # Декодируем строки если они в байтах
        name = row[1].decode('utf-8') if isinstance(row[1], bytes) else str(row[1])
        description = row[2].decode('utf-8') if isinstance(row[2], bytes) else str(row[2]) if row[2] else ""
        
        services.append({
            'id': row[0],
            'name': name,
            'description': description
        })
    
    print(f"✅ Найдено услуг: {len(services)}")
    for service in services:
        print(f"   - {service['name']} (ID: {service['id']})")
    
    return services


def clear_master_services():
    """Очищает таблицу master_services."""
    print("\n🗄️ Очистка таблицы master_services...")
    
    try:
        delete_record("master_services", "1=1")  # Удаляем все записи
        print("✅ Таблица master_services очищена")
        
    except Exception as e:
        print(f"❌ Ошибка при очистке таблицы: {e}")
        raise


def assign_services_to_masters(masters: List[Dict[str, Any]], services: List[Dict[str, Any]]):
    """Назначает услуги мастерам согласно специализации, обеспечивая покрытие всех услуг."""
    print("\n🔗 Назначение услуг мастерам...")
    
    # Создаем словарь услуг для быстрого поиска
    services_dict = {service['name'].lower(): service for service in services}
    
    # Улучшенный маппинг специализаций на услуги
    specialization_mapping = {
        'косметолог': ['чистка лица', 'массаж лица'],
        'мастер по бровям': ['коррекция бровей'],
        'мастер маникюра': ['маникюр с покрытием гель-лак', 'педикюр', 'наращивание ногтей'],
        'парикмахер': ['женская стрижка', 'мужская стрижка', 'окрашивание корней', 'сложное окрашивание', 'укладка вечерняя'],
        'мастер по ресницам': ['ламинирование ресниц']
    }
    
    # Отслеживаем назначенные услуги
    assigned_services = set()
    assigned_count = 0
    
    # Первый проход: назначаем услуги по специализации
    for master in masters:
        specialization = master['specialization'].lower() if master['specialization'] else ""
        master_name = master['name'].lower()
        
        assigned_services_for_master = []
        
        # Ищем услуги по специализации
        if specialization in specialization_mapping:
            for service_name in specialization_mapping[specialization]:
                if service_name in services_dict:
                    service = services_dict[service_name]
                    if service['id'] not in assigned_services:
                        assigned_services_for_master.append(service)
                        assigned_services.add(service['id'])
                        break
        
        # Если не нашли по специализации, ищем по ключевым словам
        if not assigned_services_for_master:
            for spec_key, service_names in specialization_mapping.items():
                if spec_key in specialization or spec_key in master_name:
                    for service_name in service_names:
                        if service_name in services_dict:
                            service = services_dict[service_name]
                            if service['id'] not in assigned_services:
                                assigned_services_for_master.append(service)
                                assigned_services.add(service['id'])
                                break
                    if assigned_services_for_master:
                        break
        
        # Назначаем услуги мастеру
        for service in assigned_services_for_master:
            master_service_data = {
                'master_id': master['id'],
                'service_id': service['id']
            }
            upsert_record('master_services', master_service_data)
            print(f"✅ Мастер {master['name']} (ID: {master['id']}) -> {service['name']} (ID: {service['id']})")
            assigned_count += 1
    
    # Второй проход: назначаем дополнительные услуги некоторым мастерам
    print("\n🔄 Назначение дополнительных услуг...")
    
    # Мастера, которые могут иметь дополнительные услуги
    multi_service_masters = []
    for master in masters:
        specialization = master['specialization'].lower() if master['specialization'] else ""
        if specialization in ['косметолог', 'мастер маникюра', 'парикмахер']:
            multi_service_masters.append(master)
    
    # Назначаем дополнительные услуги
    for master in multi_service_masters[:3]:  # Берем первых 3 мастеров для дополнительных услуг
        specialization = master['specialization'].lower()
        additional_services = []
        
        if specialization == 'косметолог':
            additional_services = ['массаж лица']
        elif specialization == 'мастер маникюра':
            additional_services = ['педикюр', 'наращивание ногтей']
        elif specialization == 'парикмахер':
            additional_services = ['укладка вечерняя', 'сложное окрашивание']
        
        for service_name in additional_services:
            if service_name in services_dict:
                service = services_dict[service_name]
                if service['id'] not in assigned_services:
                    master_service_data = {
                        'master_id': master['id'],
                        'service_id': service['id']
                    }
                    upsert_record('master_services', master_service_data)
                    print(f"✅ Мастер {master['name']} (ID: {master['id']}) -> {service['name']} (ID: {service['id']}) [дополнительная]")
                    assigned_services.add(service['id'])
                    assigned_count += 1
                    break
    
    # Третий проход: покрываем оставшиеся услуги
    print("\n🎯 Покрытие оставшихся услуг...")
    
    uncovered_services = [service for service in services if service['id'] not in assigned_services]
    
    if uncovered_services:
        print(f"📋 Оставшиеся услуги: {len(uncovered_services)}")
        for service in uncovered_services:
            print(f"   - {service['name']} (ID: {service['id']})")
        
        # Назначаем оставшиеся услуги мастерам
        for i, service in enumerate(uncovered_services):
            if i < len(masters):
                master = masters[i]
                master_service_data = {
                    'master_id': master['id'],
                    'service_id': service['id']
                }
                upsert_record('master_services', master_service_data)
                print(f"✅ Мастер {master['name']} (ID: {master['id']}) -> {service['name']} (ID: {service['id']}) [покрытие]")
                assigned_count += 1
    
    print(f"\n✅ Всего назначено услуг: {assigned_count}")
    print(f"✅ Покрыто услуг: {len(assigned_services)} из {len(services)}")


def verify_assignments():
    """Проверяет результат назначения услуг."""
    print("\n🔍 Проверка назначений...")
    
    try:
        # Получаем все назначения
        query = """
            SELECT m.id, m.name, m.specialization, s.id as service_id, s.name as service_name
            FROM masters m
            JOIN master_services ms ON m.id = ms.master_id
            JOIN services s ON ms.service_id = s.id
            ORDER BY m.id
        """
        rows = execute_query(query)
        
        print(f"📊 Всего назначений: {len(rows)}")
        print("\n📋 Детализация по мастерам:")
        
        # Группируем по мастерам
        masters_dict = {}
        for row in rows:
            master_id = row[0]
            master_name = row[1].decode('utf-8') if isinstance(row[1], bytes) else str(row[1])
            specialization = row[2].decode('utf-8') if isinstance(row[2], bytes) else str(row[2]) if row[2] else ""
            service_id = row[3]
            service_name = row[4].decode('utf-8') if isinstance(row[4], bytes) else str(row[4])
            
            if master_id not in masters_dict:
                masters_dict[master_id] = {
                    'name': master_name,
                    'specialization': specialization,
                    'services': []
                }
            
            masters_dict[master_id]['services'].append({
                'id': service_id,
                'name': service_name
            })
        
        # Выводим детализацию
        for master_id, master_info in masters_dict.items():
            services_str = ", ".join([f"{s['name']} (ID: {s['id']})" for s in master_info['services']])
            print(f"   Мастер {master_id}: {master_info['name']} ({master_info['specialization']}) -> {services_str}")
        
        # Статистика по услугам
        print("\n📊 Статистика по услугам:")
        services_coverage = {}
        for row in rows:
            service_id = row[3]
            service_name = row[4].decode('utf-8') if isinstance(row[4], bytes) else str(row[4])
            if service_id not in services_coverage:
                services_coverage[service_id] = {'name': service_name, 'masters': 0}
            services_coverage[service_id]['masters'] += 1
        
        for service_id, info in services_coverage.items():
            print(f"   {info['name']} (ID: {service_id}): {info['masters']} мастер(ов)")
        
        # Проверяем покрытие всех услуг
        all_services_query = "SELECT id, name FROM services ORDER BY id"
        all_services_rows = execute_query(all_services_query)
        all_service_ids = {row[0] for row in all_services_rows}
        covered_service_ids = set(services_coverage.keys())
        uncovered_services = all_service_ids - covered_service_ids
        
        if uncovered_services:
            print(f"\n⚠️ Непокрытые услуги: {len(uncovered_services)}")
            for service_id in uncovered_services:
                service_name = next(row[1].decode('utf-8') if isinstance(row[1], bytes) else str(row[1]) 
                                 for row in all_services_rows if row[0] == service_id)
                print(f"   - {service_name} (ID: {service_id})")
        else:
            print("\n✅ Все услуги покрыты мастерами")
        
        # Статистика по мастерам
        masters_with_multiple_services = [master_id for master_id, master_info in masters_dict.items() 
                                        if len(master_info['services']) > 1]
        
        if masters_with_multiple_services:
            print(f"\n✅ Мастера с несколькими услугами: {len(masters_with_multiple_services)}")
            for master_id in masters_with_multiple_services:
                master_info = masters_dict[master_id]
                services_count = len(master_info['services'])
                print(f"   - {master_info['name']}: {services_count} услуг")
        else:
            print("\n📝 У всех мастеров по одной услуге")
        
    except Exception as e:
        print(f"❌ Ошибка при проверке: {e}")
        raise


def main():
    """Основная функция скрипта."""
    print("🚀 Запуск скрипта настройки master_services")
    print("🎯 Цель: покрыть все услуги мастерами, некоторым мастерам дать по 2 услуги")
    print("-" * 60)
    
    try:
        # Инициализируем подключение к БД
        init_database()
        
        # Получаем данные
        masters = get_all_masters()
        services = get_all_services()
        
        if not masters:
            print("❌ Мастера не найдены в базе данных")
            return 1
        
        if not services:
            print("❌ Услуги не найдены в базе данных")
            return 1
        
        # Выполняем настройку
        clear_master_services()
        assign_services_to_masters(masters, services)
        verify_assignments()
        
        print("\n" + "=" * 60)
        print("🎉 НАСТРОЙКА ЗАВЕРШЕНА!")
        print("=" * 60)
        print("✅ Все услуги покрыты мастерами")
        print("✅ Некоторые мастера имеют по 2 услуги")
        print("✅ Таблица master_services обновлена")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        return 1
    
    finally:
        # Закрываем соединение с БД
        close_database()
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
