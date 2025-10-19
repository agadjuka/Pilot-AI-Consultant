import ydb
import os
from dotenv import load_dotenv

def test_ydb_connection():
    """
    Тестирует базовое подключение к Yandex Database (YDB)
    используя учетные данные из .env файла.
    """
    print("🚀 Запускаем тест подключения к YDB...")
    
    # 1. Загружаем переменные окружения
    load_dotenv()
    endpoint = os.getenv("YDB_ENDPOINT")
    database = os.getenv("YDB_DATABASE")
    service_account_key_file = os.getenv("YC_SERVICE_ACCOUNT_KEY_FILE")
    
    if not endpoint or not database:
        print("❌ Ошибка: Переменные YDB_ENDPOINT и/или YDB_DATABASE не найдены в .env файле.")
        return

    if not service_account_key_file:
        print("❌ Ошибка: Переменная YC_SERVICE_ACCOUNT_KEY_FILE не найдена в .env файле.")
        return

    print(f"Подключаемся к эндпоинту: {endpoint}")
    print(f"База данных: {database}")
    print(f"Ключ сервисного аккаунта: {service_account_key_file}")

    # Проверяем существование файла ключа
    # Сначала проверяем относительный путь, затем в корне проекта
    key_file_path = service_account_key_file
    if not os.path.exists(key_file_path):
        # Пробуем найти файл в корне проекта (на уровень выше scripts/)
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        key_file_path = os.path.join(project_root, service_account_key_file)
        
        if not os.path.exists(key_file_path):
            print(f"❌ Ошибка: Файл ключа {service_account_key_file} не найден.")
            print(f"   Проверялись пути:")
            print(f"   - {os.path.abspath(service_account_key_file)}")
            print(f"   - {key_file_path}")
            return
    
    print(f"Найден файл ключа: {os.path.abspath(key_file_path)}")

    try:
        # 2. Создаем драйвер с аутентификацией через ключ сервисного аккаунта
        driver_config = ydb.DriverConfig(
            endpoint=endpoint,
            database=database,
            credentials=ydb.iam.ServiceAccountCredentials.from_file(key_file_path),
        )
        
        with ydb.Driver(driver_config) as driver:
            driver.wait(timeout=5, fail_fast=True)
            print("✅ УСПЕХ! Подключение к YDB установлено.")
            
            # (Опционально) Можно выполнить простейший YQL-запрос, но wait() уже достаточно
            # with ydb.SessionPool(driver) as pool:
            #     def execute_query(session):
            #         return session.transaction().execute("SELECT 1;", commit_tx=True)
            #     result = pool.retry_operation_sync(execute_query)
            #     print(f"✅ Результат тестового запроса: {result[0].rows[0][0]}")

    except Exception as e:
        print(f"❌ ОШИБКА ПОДКЛЮЧЕНИЯ:")
        print(e)
        print("\n---")
        print("💡 Возможные решения:")
        print("1. Проверьте права: Убедитесь, что сервисный аккаунт из файла ключа имеет роль `ydb.viewer` или `ydb.editor` на эту базу данных.")
        print("2. Проверьте файл ключа: Убедитесь, что файл `key.json` содержит валидный ключ сервисного аккаунта.")
        print("3. Проверьте сеть: Убедитесь, что ваш брандмауэр/VPN не блокирует исходящие соединения на порт 2135 для адреса `ydb.serverless.yandexcloud.net`.")
        print("4. Проверьте .env: Убедитесь, что YDB_ENDPOINT, YDB_DATABASE и YC_SERVICE_ACCOUNT_KEY_FILE скопированы из консоли Yandex Cloud без ошибок.")

if __name__ == "__main__":
    test_ydb_connection()
