"""
Сервис для работы с задачами
"""
import logging
from typing import List, Optional, Dict, Any
from services.shared.utils import ServiceClient

logger = logging.getLogger(__name__)


class TaskService:
    """Сервис для работы с задачами"""
    
    def __init__(self):
        self.service_client = ServiceClient("task")
    
    async def get_user_tasks(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Получить задачи пользователя
        
        Args:
            user_id: ID пользователя
        
        Returns:
            Список задач
        """
        try:
            tasks = await self.service_client.get(f"/tasks/user/{user_id}")
            if isinstance(tasks, list):
                return tasks
            return []
        except Exception as e:
            logger.error(f"Ошибка получения задач: {e}")
            return []
    
    async def get_task(self, task_id: int) -> Dict[str, Any]:
        """Получить задачу по ID"""
        return await self.service_client.get(f"/tasks/{task_id}")
    
    async def create_task(
        self,
        user_id: int,
        title: str,
        description: Optional[str] = None,
        priority: str = "medium"
    ) -> Dict[str, Any]:
        """Создать задачу"""
        return await self.service_client.post(
            "/tasks/",
            params={"user_id": user_id},
            json={
                "title": title,
                "description": description,
                "priority": priority
            }
        )
    
    async def complete_task(self, task_id: int, user_id: int) -> Dict[str, Any]:
        """
        Завершить задачу
        
        Args:
            task_id: ID задачи
            user_id: ID пользователя (для проверки прав)
        
        Returns:
            Результат выполнения
        """
        # Сначала проверяем, что задача принадлежит пользователю
        task = await self.get_task(task_id)
        if task.get("user_id") != user_id:
            raise ValueError("Задача не принадлежит пользователю")
        
        return await self.service_client.post(f"/tasks/{task_id}/complete")
    
    async def get_task_statistics(self, user_id: int) -> Dict[str, Any]:
        """Получить статистику по задачам"""
        try:
            return await self.service_client.get(f"/tasks/stats/{user_id}")
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return {
                "user_id": user_id,
                "total": 0,
                "completed": 0,
                "in_progress": 0,
                "todo": 0,
                "completion_rate": 0
            }
    
    async def close(self):
        """Закрыть соединение"""
        await self.service_client.close()

