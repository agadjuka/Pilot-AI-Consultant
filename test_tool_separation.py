#!/usr/bin/env python3
"""
Тест для проверки правильного разделения инструментов между этапами планирования и синтеза.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.tool_definitions import read_only_tools, write_tools, read_only_tools_obj, write_tools_obj
from app.services.prompt_builder_service import PromptBuilderService

def test_tool_separation():
    """Тестирует разделение инструментов на read_only и write."""
    print("🔍 Тестирование разделения инструментов...")
    
    # Проверяем, что read_only_tools содержат только разведывательные инструменты
    read_only_names = [tool.name for tool in read_only_tools]
    print(f"📖 Read-only инструменты: {read_only_names}")
    
    expected_read_only = [
        'get_all_services',
        'get_masters_for_service', 
        'get_available_slots',
        'get_my_appointments',
        'get_full_history'
    ]
    
    for expected in expected_read_only:
        assert expected in read_only_names, f"❌ {expected} должен быть в read_only_tools"
    
    # Проверяем, что write_tools содержат только исполнительные инструменты
    write_names = [tool.name for tool in write_tools]
    print(f"✏️ Write инструменты: {write_names}")
    
    expected_write = [
        'create_appointment',
        'cancel_appointment_by_id',
        'reschedule_appointment_by_id',
        'call_manager'
    ]
    
    for expected in expected_write:
        assert expected in write_names, f"❌ {expected} должен быть в write_tools"
    
    # Проверяем, что create_appointment НЕ в read_only_tools
    assert 'create_appointment' not in read_only_names, "❌ create_appointment не должен быть в read_only_tools"
    
    # Проверяем, что get_all_services НЕ в write_tools
    assert 'get_all_services' not in write_names, "❌ get_all_services не должен быть в write_tools"
    
    print("✅ Разделение инструментов работает корректно!")

def test_prompt_builder():
    """Тестирует PromptBuilderService на правильное использование инструментов."""
    print("\n🔍 Тестирование PromptBuilderService...")
    
    prompt_builder = PromptBuilderService()
    
    # Тестируем промпт мышления
    thinking_prompt = prompt_builder.build_thinking_prompt(
        stage_name="greeting",
        history=[],
        user_message="Хочу записаться на маникюр"
    )
    
    # Проверяем, что в промпте мышления есть только read_only инструменты
    for tool_name in ['get_all_services', 'get_available_slots']:
        assert tool_name in thinking_prompt, f"❌ {tool_name} должен быть в промпте мышления"
    
    # Проверяем, что в промпте мышления НЕТ write инструментов
    for tool_name in ['create_appointment', 'cancel_appointment_by_id']:
        assert tool_name not in thinking_prompt, f"❌ {tool_name} НЕ должен быть в промпте мышления"
    
    print("✅ Промпт мышления использует только read_only инструменты!")
    
    # Тестируем промпт синтеза
    synthesis_prompt = prompt_builder.build_synthesis_prompt(
        stage_name="greeting",
        history=[],
        user_message="Хочу записаться на маникюр",
        tool_results="Результат get_all_services: Маникюр - 2000 руб, 60 мин"
    )
    
    # Проверяем, что в промпте синтеза есть write инструменты
    for tool_name in ['create_appointment', 'cancel_appointment_by_id']:
        assert tool_name in synthesis_prompt, f"❌ {tool_name} должен быть в промпте синтеза"
    
    print("✅ Промпт синтеза использует write инструменты!")

if __name__ == "__main__":
    try:
        test_tool_separation()
        test_prompt_builder()
        print("\n🎉 Все тесты прошли успешно!")
        print("✅ Разделение инструментов между этапами работает корректно!")
    except Exception as e:
        print(f"\n❌ Тест не прошел: {e}")
        sys.exit(1)
