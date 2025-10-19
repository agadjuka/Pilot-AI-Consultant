from app.core.database import init_database
from app.repositories.master_schedule_repository import MasterScheduleRepository
import asyncio

async def check_time_format():
    init_database()
    from app.core.database import get_session
    repo = MasterScheduleRepository(get_session)
    
    # Получаем несколько записей для проверки формата
    schedules = await repo.get_all()
    print('Форматы времени в master_schedules:')
    for i, schedule in enumerate(schedules[:3]):
        print(f'Запись {i+1}: start_time="{schedule["start_time"]}", end_time="{schedule["end_time"]}"')

if __name__ == "__main__":
    asyncio.run(check_time_format())
