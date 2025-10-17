import boto3
import logging
from typing import Optional
from botocore.exceptions import ClientError, NoCredentialsError
from app.core.config import settings

logger = logging.getLogger(__name__)


class S3LoggerService:
    """
    Сервис для загрузки логов трассировки в S3-совместимое хранилище (Yandex Object Storage).
    """
    
    def __init__(self):
        """
        Инициализирует S3-клиент с настройками из конфигурации.
        """
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.S3_ACCESS_KEY_ID,
                aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
                endpoint_url=settings.S3_ENDPOINT_URL
            )
            self.bucket_name = settings.S3_BUCKET_NAME
            
            logger.info(f"✅ S3LoggerService инициализирован для bucket: {self.bucket_name}")
            
        except NoCredentialsError:
            logger.error("❌ Не удалось найти учетные данные S3")
            raise
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации S3LoggerService: {e}")
            raise
    
    def upload_log(self, file_content: str, file_name: str) -> bool:
        """
        Загружает содержимое лога в S3-хранилище.
        
        Args:
            file_content: Содержимое лога в виде строки
            file_name: Имя файла для сохранения в S3
            
        Returns:
            bool: True если загрузка успешна, False в противном случае
        """
        try:
            # Загружаем содержимое в S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=file_name,
                Body=file_content.encode('utf-8'),
                ContentType='text/markdown'
            )
            
            logger.info(f"✅ Лог успешно загружен в S3: {file_name}")
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"❌ Ошибка S3 при загрузке {file_name}: {error_code} - {e}")
            return False
            
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка при загрузке {file_name}: {e}")
            return False
    
    def test_connection(self) -> bool:
        """
        Тестирует подключение к S3-хранилищу.
        
        Returns:
            bool: True если подключение успешно, False в противном случае
        """
        try:
            # Пытаемся получить информацию о bucket
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"✅ Подключение к S3 bucket '{self.bucket_name}' успешно")
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"❌ Ошибка подключения к S3 bucket '{self.bucket_name}': {error_code}")
            return False
            
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка при тестировании S3: {e}")
            return False
