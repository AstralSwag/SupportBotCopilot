from mattermostdriver import Driver
from ..config import settings

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
        
    async def create_thread(self, title: str, message: str) -> str:
        """Создает новую тему в Mattermost"""
        self.client.login()
        post = self.client.posts.create_post({
            'channel_id': self.channel_id,
            'message': f"### {title}\n{message}"
        })
        return post['id']
        
    async def add_comment(self, thread_id: str, message: str):
        """Добавляет комментарий в существующую тему"""
        self.client.login()
        self.client.posts.create_post({
            'channel_id': self.channel_id,
            'message': message,
            'root_id': thread_id
        })
