import aiohttp
from ..config import settings

class PlaneService:
    def __init__(self):
        self.base_url = settings.PLANE_API_URL
        self.headers = {
            "Authorization": f"Bearer {settings.PLANE_API_TOKEN}",
            "Content-Type": "application/json"
        }
        self.workspace_id = settings.PLANE_WORKSPACE_ID
        self.project_id = settings.PLANE_PROJECT_ID

    async def create_ticket(self, title: str, description: str) -> str:
        """Создает новый тикет в Plane.so"""
        async with aiohttp.ClientSession() as session:
            url = f"{self.base_url}/api/workspaces/{self.workspace_id}/projects/{self.project_id}/issues"
            data = {
                "name": title,
                "description": description,
                "state": "backlog"  # или другой начальный статус
            }
            async with session.post(url, json=data, headers=self.headers) as response:
                result = await response.json()
                return result["id"]

    async def update_ticket(self, ticket_id: str, comment: str):
        """Добавляет комментарий к существующему тикету"""
        async with aiohttp.ClientSession() as session:
            url = f"{self.base_url}/api/workspaces/{self.workspace_id}/projects/{self.project_id}/issues/{ticket_id}/comments"
            data = {
                "comment_html": comment
            }
            async with session.post(url, json=data, headers=self.headers) as response:
                await response.json()

    async def get_user_tickets(self, user_id: int) -> list:
        """Получает список тикетов пользователя"""
        async with aiohttp.ClientSession() as session:
            url = f"{self.base_url}/api/workspaces/{self.workspace_id}/projects/{self.project_id}/issues"
            params = {
                "subscriber_id": user_id,
                "state": ["backlog", "in_progress"]  # или другие статусы
            }
            async with session.get(url, params=params, headers=self.headers) as response:
                return await response.json()
