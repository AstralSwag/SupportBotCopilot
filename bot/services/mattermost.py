from mattermostdriver import Driver
from bot.config import settings
import aiohttp
import logging
import asyncio

logger = logging.getLogger(__name__)

class MattermostService:
    def __init__(self):
        self.client = Driver({
            'url': settings.MATTERMOST_URL,
            'token': settings.MATTERMOST_TOKEN,
            'scheme': 'https',
            'port': 443
        })
        self.team_id = settings.MATTERMOST_TEAM
        self.channel_id = settings.MATTERMOST_CHANNEL
        self.base_url = settings.MATTERMOST_URL
        self.token = settings.MATTERMOST_TOKEN
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
    async def create_thread(self, title: str, message: str) -> str:
        """Создает новую тему в Mattermost"""
        try:
            self.client.login()
            post = self.client.posts.create_post({
                'channel_id': self.channel_id,
                'message': f"### {title}\n{message}"
            })
            return post['id']
        except Exception as e:
            raise Exception(f"Failed to create Mattermost thread: {str(e)}")
        
    async def add_comment(self, thread_id: str, message: str):
        """Добавляет комментарий в существующую тему"""
        try:
            self.client.login()
            self.client.posts.create_post({
                'channel_id': self.channel_id,
                'message': message,
                'root_id': thread_id
            })
        except Exception as e:
            raise Exception(f"Failed to add comment to Mattermost thread: {str(e)}")

    async def get_post(self, post_id: str, max_retries: int = 5, delay: float = 2.0) -> dict:
        """Получает информацию о посте через API Mattermost с повторными попытками"""
        url = f"https://{self.base_url}/api/v4/posts/{post_id}"
        logger.info(f"Отправка запроса к Mattermost API: {url}")
        logger.info(f"Заголовки запроса: {self.headers}")
        
        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=self.headers) as response:
                        response_text = await response.text()
                        logger.info(f"Попытка {attempt + 1}/{max_retries}")
                        logger.info(f"Статус ответа: {response.status}")
                        logger.info(f"Тело ответа: {response_text}")
                        
                        if response.status == 200:
                            return await response.json()
                        elif response.status == 404 and attempt < max_retries - 1:
                            logger.info(f"Пост {post_id} еще не создан, ожидание {delay} секунд...")
                            await asyncio.sleep(delay)
                            continue
                        else:
                            logger.error(f"Ошибка при получении поста {post_id}: {response.status}")
                            return None
                            
            except Exception as e:
                logger.error(f"Ошибка при запросе к Mattermost API (попытка {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(delay)
                    continue
                return None
                
        logger.error(f"Не удалось получить пост {post_id} после {max_retries} попыток")
        return None

# Создаем экземпляр сервиса
mattermost_service = MattermostService()
