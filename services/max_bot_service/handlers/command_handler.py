"""
Обработчик команд бота
"""
import logging
import time
from typing import Dict, Any, Optional
from services.max_bot_service.max_api_client import MaxApiClient
from services.max_bot_service.services.user_service import UserService
from services.max_bot_service.services.character_service import CharacterService
from services.max_bot_service.services.task_service import TaskService
from services.max_bot_service.utils.keyboards import KeyboardBuilder
from services.max_bot_service.utils.formatters import MessageFormatter
from services.max_bot_service.utils.stats import stats
from services.max_bot_service.handlers.attendance_handler import AttendanceHandler
from services.max_bot_service.handlers.group_handler import GroupChatHandler
from services.shared.utils import ServiceClient

logger = logging.getLogger(__name__)


class CommandHandler:
    """Обработчик команд бота"""
    
    def __init__(self, api_client: MaxApiClient):
        self.api_client = api_client
        self.user_service = UserService()
        self.character_service = CharacterService()
        self.task_service = TaskService()
        self.keyboard_builder = KeyboardBuilder()
        self.formatter = MessageFormatter()
        # Храним состояние пользователей, ожидающих ввода названия задачи
        # Формат: {user_id: timestamp последнего сообщения о создании задачи}
        self.users_awaiting_task_title: Dict[int, float] = {}
        # Защита от множественного создания задач: храним последнее время создания задачи
        # Формат: {user_id: timestamp последнего создания задачи}
        self.last_task_creation: Dict[int, float] = {}
        # Минимальный интервал между созданиями задач (2 секунды)
        self.task_creation_cooldown = 2.0
        # Отметка на занятиях, серия посещений, «дни без штрафа»
        self.attendance = AttendanceHandler(api_client, self.user_service, self.keyboard_builder)
        # Групповой чат учебной группы
        self.group = GroupChatHandler(api_client)
    
    async def handle_command(
        self,
        user_id: int,
        text: str,
        update: Dict[str, Any],
        max_user_name: Optional[str] = None
    ):
        """
        Обработать команду
        
        Args:
            user_id: ID пользователя MAX
            text: Текст команды (например, "/start")
            update: Полный объект обновления
        """
        # Парсим команду
        parts = text.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        logger.info(f"Команда от пользователя {user_id}: {command} {args}")
        
        # Обработка команд
        if command == "/start":
            # Диплинк с QR-кода занятия: /start att-<id>-<код>
            if args and await self.attendance.handle_start_payload(user_id, args, max_user_name=max_user_name):
                return
            await self.handle_start(user_id, update=update)
        elif command == "/checkin":
            await self.attendance.handle_checkin_command(user_id, args, max_user_name=max_user_name)
        elif command == "/streak":
            await self.attendance.handle_streak(user_id, max_user_name=max_user_name)
        elif command == "/help":
            await self.handle_help(user_id)
        elif command == "/profile":
            await self.handle_profile(user_id, max_user_name=max_user_name)
        elif command == "/tasks":
            await self.handle_tasks(user_id, max_user_name=max_user_name)
        elif command == "/newtask" or command == "/createtask":
            await self.handle_create_task(user_id, args, max_user_name=max_user_name)
        elif command == "/character":
            await self.handle_character(user_id, max_user_name=max_user_name)
        elif command == "/stats":
            await self.handle_stats(user_id, max_user_name=max_user_name)
        elif command == "/inventory":
            await self.handle_inventory(user_id, max_user_name=max_user_name)
        elif command == "/achievements":
            await self.handle_achievements(user_id, max_user_name=max_user_name)
        else:
            await self.api_client.send_message(
                user_id=user_id,
                text="Неизвестная команда. Введите /help для списка доступных команд.",
                format="markdown"
            )
    
    async def handle_callback(
        self,
        user_id: int,
        payload: str,
        callback_id: str,
        update: Dict[str, Any]
    ):
        """
        Обработать callback от кнопки
        
        Args:
            user_id: ID пользователя MAX
            payload: Данные из кнопки
            callback_id: ID callback для ответа
            update: Полный объект обновления
        """
        logger.info(f"Callback от пользователя {user_id}: {payload}")
        
        # Извлекаем имя пользователя из callback, если доступно
        max_user_name = None
        callback_obj = update.get("callback", {})
        user = callback_obj.get("user", {})
        max_user_name = user.get("name") or user.get("username") or user.get("first_name")
        
        # Парсим payload (формат: "action:param" или "action")
        parts = payload.split(":", 1)
        action = parts[0]
        param = parts[1] if len(parts) > 1 else None
        
        try:
            if action == "checkin_help":
                await self.attendance.send_help(user_id, callback_id)
                return
            if action == "streak":
                await self.attendance.handle_streak(user_id, callback_id, max_user_name=max_user_name)
                return
            if action == "streak_freeze":
                if param:
                    await self.attendance.handle_freeze(user_id, int(param), callback_id, max_user_name=max_user_name)
                return
            if action == "help_request":
                await self.attendance.handle_help_request(user_id, callback_id, max_user_name=max_user_name)
                return
            if action == "help_ok":
                await self.api_client.answer_callback(callback_id=callback_id,
                                                      notification="Рады, что всё в порядке! Персонаж ждёт тебя на паре 💪")
                return
            if action == "menu":
                # При открытии меню также можем создать персонажа, если его нет
                # Создаем пользователя и персонажа, если нужно
                user = await self.user_service.get_or_create_user(user_id, max_user_name=max_user_name)
                user_id_internal = user.get("id") if isinstance(user, dict) else user.id
                await self.character_service.get_character(user_id_internal, max_user_id=user_id, max_user_name=max_user_name)
                
                await self.handle_menu(user_id, callback_id, update=update)
            elif action == "profile":
                await self.handle_profile(user_id, callback_id, max_user_name=max_user_name)
            elif action == "tasks":
                await self.handle_tasks(user_id, callback_id, max_user_name=max_user_name)
            elif action == "character":
                await self.handle_character(user_id, callback_id, max_user_name=max_user_name)
            elif action == "stats":
                await self.handle_stats(user_id, callback_id, max_user_name=max_user_name)
            elif action == "inventory":
                await self.handle_inventory(user_id, callback_id, max_user_name=max_user_name)
            elif action == "achievements":
                await self.handle_achievements(user_id, callback_id, max_user_name=max_user_name)
            elif action == "task_complete":
                if param:
                    await self.handle_task_complete(user_id, int(param), callback_id)
            elif action == "task_view":
                if param:
                    await self.handle_task_view(user_id, int(param), callback_id)
            elif action == "task_create":
                await self.handle_task_create_prompt(user_id, callback_id, max_user_name=max_user_name)
            elif action == "task_create_confirm":
                if param:
                    await self.handle_task_create_confirm(user_id, param, callback_id, max_user_name=max_user_name)
            elif action == "friend_accept":
                if param:
                    await self.handle_friend_request_action(user_id, int(param), "accept", callback_id, update=update, max_user_name=max_user_name)
            elif action == "friend_reject":
                if param:
                    await self.handle_friend_request_action(user_id, int(param), "reject", callback_id, update=update, max_user_name=max_user_name)
            elif action == "trade_accept":
                if param:
                    await self.handle_trade_request_action(user_id, int(param), "accept", callback_id, update=update, max_user_name=max_user_name)
            elif action == "trade_reject":
                if param:
                    await self.handle_trade_request_action(user_id, int(param), "reject", callback_id, update=update, max_user_name=max_user_name)
            elif action == "competition_join":
                if param:
                    await self.handle_competition_join(user_id, int(param), callback_id, update=update, max_user_name=max_user_name)
            elif action == "competition_decline":
                if param:
                    await self.handle_competition_decline(user_id, int(param), callback_id, update=update, max_user_name=max_user_name)
            elif action == "challenge_accept":
                if param:
                    await self.handle_challenge_action(user_id, int(param), "accept", callback_id, update=update, max_user_name=max_user_name)
            elif action == "challenge_reject":
                if param:
                    await self.handle_challenge_action(user_id, int(param), "reject", callback_id, update=update, max_user_name=max_user_name)
            elif action == "group_invitation_accept":
                if param:
                    await self.handle_group_invitation_action(user_id, int(param), "accept", callback_id, update=update, max_user_name=max_user_name)
            elif action == "group_invitation_reject":
                if param:
                    await self.handle_group_invitation_action(user_id, int(param), "reject", callback_id, update=update, max_user_name=max_user_name)
            else:
                await self.api_client.answer_callback(
                    callback_id=callback_id,
                    notification="Неизвестное действие"
                )
        except Exception as e:
            logger.error(f"Ошибка обработки callback: {e}")
            await self.api_client.answer_callback(
                callback_id=callback_id,
                notification="Произошла ошибка при обработке запроса"
            )
    
    async def handle_bot_started(self, update: Dict[str, Any]):
        """
        Событие bot_started: пользователь открыл чат с ботом, в т.ч. по диплинку
        https://max.ru/<бот>?start=<payload>. Payload с QR-кода занятия сразу отмечает посещение.
        """
        user = update.get("user") or {}
        user_id = user.get("user_id") or user.get("id")
        if not user_id:
            logger.warning("bot_started без пользователя: %s", update)
            return
        max_user_name = user.get("name") or user.get("username") or user.get("first_name")
        payload = update.get("payload")
        if payload and await self.attendance.handle_start_payload(user_id, payload, max_user_name=max_user_name):
            return
        await self.handle_start(user_id, update={"message": {"sender": user}})

    async def handle_start(self, user_id: int, callback_id: Optional[str] = None, update: Optional[Dict[str, Any]] = None):
        """Обработка команды /start"""
        # Получаем имя пользователя из update, если доступно
        max_user_name = None
        if update:
            message = update.get("message", {})
            sender = message.get("sender", {})
            max_user_name = sender.get("name") or sender.get("username") or sender.get("first_name")
        
        # Получаем или создаем пользователя с именем из MAX
        user = await self.user_service.get_or_create_user(user_id, max_user_name=max_user_name)
        user_id_internal = user.get("id") if isinstance(user, dict) else user.id
        
        # Проверяем, новый ли это пользователь (по отсутствию last_daily_reward_at)
        is_new_user = user.get("last_daily_reward_at") is None if isinstance(user, dict) else user.last_daily_reward_at is None
        
        # Создаем персонажа автоматически (get_character создаст его, если его нет)
        character = await self.character_service.get_character(user_id_internal, max_user_id=user_id, max_user_name=max_user_name)
        
        character_text = ""
        if character:
            character_name = character.get('name', 'Персонаж')
            character_text = f"\nВаш *{character_name}* готов к приключениям! 🎮"
        else:
            character_text = "\n⚠️ Не удалось создать персонажа. Попробуйте позже или обратитесь к администратору."
        
        text = f"""*🌟 Добро пожаловать в Матрикс!*

Твой персонаж растёт, когда ты ходишь на пары и учишься.

*Главное:*
✅ Отметься на паре — отсканируй QR с экрана преподавателя или отправь код: `/checkin 1234`
🎁 Получи монеты, интеллект и настроение персонажа
🔥 Держи серию посещений — открывай новые образы и локации
🧊 Пропустил? Можно взять «день без штрафа» (2 раза в месяц)
{character_text}

Открой мини-приложение кнопкой ниже. Справка — /help"""
        
        keyboard = self.keyboard_builder.build_main_menu()
        
        # Сначала отправляем приветственное сообщение
        if callback_id:
            await self.api_client.answer_callback(
                callback_id=callback_id,
                message={
                    "text": text,
                    "attachments": [keyboard],
                    "format": "markdown"
                }
            )
        else:
            await self.api_client.send_message(
                user_id=user_id,
                text=text,
                attachments=[keyboard],
                format="markdown"
            )
        
        # Затем отправляем уведомление о ежедневном подарке
        # Для нового пользователя - всегда отправляем
        # Для существующего - проверяем доступность подарка и отправляем только если доступен
        try:
            if is_new_user:
                # Новый пользователь - всегда отправляем уведомление
                bot_service = ServiceClient("max_bot")
                await bot_service.post("/notifications/daily-reward-updated", json={
                    "user_id": user_id_internal
                })
                await bot_service.close()
                logger.info(f"✅ Отправлено уведомление о ежедневном подарке новому пользователю {user_id_internal} (max_user_id={user_id})")
            else:
                # Существующий пользователь - проверяем доступность подарка
                user_service_client = ServiceClient("user")
                try:
                    reward_status = await user_service_client.get(f"/users/{user_id_internal}/daily-reward")
                    # Если подарок доступен (success: true), отправляем уведомление
                    if reward_status and reward_status.get("success", False):
                        bot_service = ServiceClient("max_bot")
                        await bot_service.post("/notifications/daily-reward-updated", json={
                            "user_id": user_id_internal
                        })
                        await bot_service.close()
                        logger.info(f"✅ Отправлено уведомление о ежедневном подарке пользователю {user_id_internal} (max_user_id={user_id}) - подарок доступен")
                    else:
                        logger.debug(f"Подарок недоступен для пользователя {user_id_internal}, уведомление не отправляется")
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось проверить доступность подарка для пользователя {user_id_internal}: {e}")
                finally:
                    await user_service_client.close()
        except Exception as e:
            logger.warning(f"⚠️ Не удалось отправить уведомление о ежедневном подарке пользователю {user_id_internal}: {e}")
    
    async def handle_help(self, user_id: int):
        """Обработка команды /help"""
        text = """*Справка по командам бота* 📖

*Посещаемость:*
/checkin 1234 - Отметиться на текущей паре кодом с экрана
/streak - Серия посещений и «дни без штрафа»

*Основные команды:*
/start - Начать работу с ботом
/profile - Ваш профиль и персонаж
/tasks - Список задач
/newtask [название] - Создать новую задачу
/character - Информация о персонаже
/stats - Статистика и прогресс
/inventory - Ваш инвентарь
/achievements - Достижения
/help - Эта справка

*Навигация:*
Используйте кнопки под сообщениями для быстрого доступа к функциям.

*Примеры:*
`/newtask Купить молоко` - создать задачу"""
        
        keyboard = self.keyboard_builder.build_main_menu()
        
        await self.api_client.send_message(
            user_id=user_id,
            text=text,
            attachments=[keyboard],
            format="markdown"
        )
    
    async def handle_menu(self, user_id: int, callback_id: str, update: Optional[Dict[str, Any]] = None):
        """Показать главное меню"""
        text = "*Главное меню* 🎮\n\nВыберите раздел:"
        keyboard = self.keyboard_builder.build_main_menu()
        
        await self.api_client.answer_callback(
            callback_id=callback_id,
            message={
                "text": text,
                "attachments": [keyboard],
                "format": "markdown"
            }
        )
    
    async def handle_profile(self, user_id: int, callback_id: Optional[str] = None, max_user_name: Optional[str] = None):
        """Показать профиль пользователя"""
        try:
            user = await self.user_service.get_or_create_user(user_id, max_user_name=max_user_name)
            user_id_internal = user.get("id") if isinstance(user, dict) else user.id
            character = await self.character_service.get_character(user_id_internal, max_user_id=user_id)
            
            text = self.formatter.format_profile(user, character)
            keyboard = self.keyboard_builder.build_profile_menu()
            
            if callback_id:
                await self.api_client.answer_callback(
                    callback_id=callback_id,
                    message={
                        "text": text,
                        "attachments": [keyboard],
                        "format": "markdown"
                    }
                )
            else:
                await self.api_client.send_message(
                    user_id=user_id,
                    text=text,
                    attachments=[keyboard],
                    format="markdown"
                )
        except Exception as e:
            logger.error(f"Ошибка получения профиля: {e}", exc_info=True)
            error_text = "Произошла ошибка при получении профиля. Попробуйте позже."
            if callback_id:
                await self.api_client.answer_callback(
                    callback_id=callback_id,
                    notification=error_text
                )
            else:
                await self.api_client.send_message(
                    user_id=user_id,
                    text=error_text
                )
    
    async def handle_tasks(self, user_id: int, callback_id: Optional[str] = None, max_user_name: Optional[str] = None):
        """Показать список задач"""
        try:
            user = await self.user_service.get_or_create_user(user_id, max_user_name=max_user_name)
            user_id_internal = user.get("id") if isinstance(user, dict) else user.id
            tasks = await self.task_service.get_user_tasks(user_id_internal)
            
            text = self.formatter.format_tasks_list(tasks)
            keyboard = self.keyboard_builder.build_tasks_menu(tasks)
            
            if callback_id:
                await self.api_client.answer_callback(
                    callback_id=callback_id,
                    message={
                        "text": text,
                        "attachments": [keyboard],
                        "format": "markdown"
                    }
                )
            else:
                await self.api_client.send_message(
                    user_id=user_id,
                    text=text,
                    attachments=[keyboard],
                    format="markdown"
                )
        except Exception as e:
            logger.error(f"Ошибка получения задач: {e}")
            error_text = "Произошла ошибка при получении задач. Попробуйте позже."
            if callback_id:
                await self.api_client.answer_callback(
                    callback_id=callback_id,
                    notification=error_text
                )
            else:
                await self.api_client.send_message(
                    user_id=user_id,
                    text=error_text
                )
    
    async def handle_character(self, user_id: int, callback_id: Optional[str] = None, max_user_name: Optional[str] = None):
        """Показать информацию о персонаже"""
        try:
            user = await self.user_service.get_or_create_user(user_id, max_user_name=max_user_name)
            user_id_internal = user.get("id") if isinstance(user, dict) else user.id
            character = await self.character_service.get_character(user_id_internal, max_user_id=user_id)
            
            text = self.formatter.format_character(character)
            keyboard = self.keyboard_builder.build_character_menu()
            
            if callback_id:
                await self.api_client.answer_callback(
                    callback_id=callback_id,
                    message={
                        "text": text,
                        "attachments": [keyboard],
                        "format": "markdown"
                    }
                )
            else:
                await self.api_client.send_message(
                    user_id=user_id,
                    text=text,
                    attachments=[keyboard],
                    format="markdown"
                )
        except Exception as e:
            logger.error(f"Ошибка получения персонажа: {e}")
            error_text = "Произошла ошибка при получении информации о персонаже. Попробуйте позже."
            if callback_id:
                await self.api_client.answer_callback(
                    callback_id=callback_id,
                    notification=error_text
                )
            else:
                await self.api_client.send_message(
                    user_id=user_id,
                    text=error_text
                )
    
    async def handle_stats(self, user_id: int, callback_id: Optional[str] = None, max_user_name: Optional[str] = None):
        """Показать статистику"""
        try:
            user = await self.user_service.get_or_create_user(user_id, max_user_name=max_user_name)
            user_id_internal = user.get("id") if isinstance(user, dict) else user.id
            stats = await self.task_service.get_task_statistics(user_id_internal)
            
            text = self.formatter.format_stats(stats)
            keyboard = self.keyboard_builder.build_stats_menu()
            
            if callback_id:
                await self.api_client.answer_callback(
                    callback_id=callback_id,
                    message={
                        "text": text,
                        "attachments": [keyboard],
                        "format": "markdown"
                    }
                )
            else:
                await self.api_client.send_message(
                    user_id=user_id,
                    text=text,
                    attachments=[keyboard],
                    format="markdown"
                )
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            error_text = "Произошла ошибка при получении статистики. Попробуйте позже."
            if callback_id:
                await self.api_client.answer_callback(
                    callback_id=callback_id,
                    notification=error_text
                )
            else:
                await self.api_client.send_message(
                    user_id=user_id,
                    text=error_text
                )
    
    async def handle_inventory(self, user_id: int, callback_id: Optional[str] = None, max_user_name: Optional[str] = None):
        """Показать инвентарь"""
        try:
            user = await self.user_service.get_or_create_user(user_id, max_user_name=max_user_name)
            user_id_internal = user.get("id") if isinstance(user, dict) else user.id
            inventory = await self.user_service.get_inventory(user_id_internal)
            
            text = self.formatter.format_inventory(inventory)
            keyboard = self.keyboard_builder.build_inventory_menu()
            
            if callback_id:
                await self.api_client.answer_callback(
                    callback_id=callback_id,
                    message={
                        "text": text,
                        "attachments": [keyboard],
                        "format": "markdown"
                    }
                )
            else:
                await self.api_client.send_message(
                    user_id=user_id,
                    text=text,
                    attachments=[keyboard],
                    format="markdown"
                )
        except Exception as e:
            logger.error(f"Ошибка получения инвентаря: {e}")
            error_text = "Произошла ошибка при получении инвентаря. Попробуйте позже."
            if callback_id:
                await self.api_client.answer_callback(
                    callback_id=callback_id,
                    notification=error_text
                )
            else:
                await self.api_client.send_message(
                    user_id=user_id,
                    text=error_text
                )
    
    async def handle_achievements(self, user_id: int, callback_id: Optional[str] = None, max_user_name: Optional[str] = None):
        """Показать достижения"""
        try:
            user = await self.user_service.get_or_create_user(user_id, max_user_name=max_user_name)
            user_id_internal = user.get("id") if isinstance(user, dict) else user.id
            achievements = await self.user_service.get_achievements(user_id_internal)
            
            text = self.formatter.format_achievements(achievements)
            keyboard = self.keyboard_builder.build_achievements_menu()
            
            if callback_id:
                await self.api_client.answer_callback(
                    callback_id=callback_id,
                    message={
                        "text": text,
                        "attachments": [keyboard],
                        "format": "markdown"
                    }
                )
            else:
                await self.api_client.send_message(
                    user_id=user_id,
                    text=text,
                    attachments=[keyboard],
                    format="markdown"
                )
        except Exception as e:
            logger.error(f"Ошибка получения достижений: {e}")
            error_text = "Произошла ошибка при получении достижений. Попробуйте позже."
            if callback_id:
                await self.api_client.answer_callback(
                    callback_id=callback_id,
                    notification=error_text
                )
            else:
                await self.api_client.send_message(
                    user_id=user_id,
                    text=error_text
                )
    
    async def handle_task_complete(self, user_id: int, task_id: int, callback_id: str):
        """Завершить задачу"""
        try:
            user = await self.user_service.get_or_create_user(user_id)
            user_id_internal = user.get("id") if isinstance(user, dict) else user.id
            result = await self.task_service.complete_task(task_id, user_id_internal)
            
            await self.api_client.answer_callback(
                callback_id=callback_id,
                notification="✅ Задача выполнена! Награды получены."
            )
            
            # Обновляем список задач
            await self.handle_tasks(user_id, callback_id=None)
        except Exception as e:
            logger.error(f"Ошибка завершения задачи: {e}")
            await self.api_client.answer_callback(
                callback_id=callback_id,
                notification="❌ Ошибка при завершении задачи"
            )
    
    async def handle_task_view(self, user_id: int, task_id: int, callback_id: str):
        """Показать детали задачи"""
        try:
            task = await self.task_service.get_task(task_id)
            text = self.formatter.format_task_detail(task)
            keyboard = self.keyboard_builder.build_task_detail_menu(task_id)
            
            await self.api_client.answer_callback(
                callback_id=callback_id,
                message={
                    "text": text,
                    "attachments": [keyboard],
                    "format": "markdown"
                }
            )
        except Exception as e:
            logger.error(f"Ошибка получения задачи: {e}")
            await self.api_client.answer_callback(
                callback_id=callback_id,
                notification="❌ Ошибка при получении задачи"
            )
    
    async def handle_create_task(self, user_id: int, args: str, max_user_name: Optional[str] = None):
        """Создать задачу из команды"""
        try:
            # Rate limiting: проверяем, не слишком ли часто пользователь создает задачи
            current_time = time.time()
            if user_id in self.last_task_creation:
                time_since_last = current_time - self.last_task_creation[user_id]
                if time_since_last < self.task_creation_cooldown:
                    logger.warning(f"Пользователь {user_id} слишком часто создает задачи (прошло {time_since_last:.2f} сек)")
                    await self.api_client.send_message(
                        user_id=user_id,
                        text="⏳ Пожалуйста, подождите немного перед созданием новой задачи.",
                        format="markdown"
                    )
                    return
            
            # Обновляем время последнего создания задачи
            self.last_task_creation[user_id] = current_time
            
            user = await self.user_service.get_or_create_user(user_id, max_user_name=max_user_name)
            user_id_internal = user.get("id") if isinstance(user, dict) else user.id
            
            if not args or not args.strip():
                await self.api_client.send_message(
                    user_id=user_id,
                    text="❌ Укажите название задачи.\n\n*Пример:* `/newtask Купить молоко`",
                    format="markdown"
                )
                return
            
            title = args.strip()
            if len(title) > 200:
                title = title[:197] + "..."
            
            task = await self.task_service.create_task(
                user_id=user_id_internal,
                title=title,
                description=None,
                priority="medium"
            )
            
            reward_coins = task.get('reward_coins', 0)
            reward_intelligence = task.get('reward_intelligence_points', 0)
            
            text = f"""✅ *Задача создана!*

*Название:* {title}
*ID:* {task.get('id', 'N/A')}

💰 *Награда:* {reward_coins} монет
🧠 *Очки интеллекта:* {reward_intelligence}

Используйте /tasks для просмотра всех задач."""
            
            keyboard = self.keyboard_builder.build_task_created_menu()
            
            await self.api_client.send_message(
                user_id=user_id,
                text=text,
                attachments=[keyboard],
                format="markdown"
            )
        except Exception as e:
            logger.error(f"Ошибка создания задачи: {e}")
            await self.api_client.send_message(
                user_id=user_id,
                text="❌ Ошибка при создании задачи. Попробуйте позже.",
                format="markdown"
            )
    
    async def handle_task_create_prompt(self, user_id: int, callback_id: str, max_user_name: Optional[str] = None):
        """Показать подсказку для создания задачи"""
        # Rate limiting: проверяем, не слишком ли часто пользователь запрашивает создание задачи
        current_time = time.time()
        if user_id in self.last_task_creation:
            time_since_last = current_time - self.last_task_creation[user_id]
            if time_since_last < self.task_creation_cooldown:
                logger.warning(f"Пользователь {user_id} слишком часто запрашивает создание задачи (прошло {time_since_last:.2f} сек)")
                await self.api_client.answer_callback(
                    callback_id=callback_id,
                    notification="⏳ Пожалуйста, подождите немного перед созданием новой задачи"
                )
                return
        
        # Сохраняем состояние пользователя - ожидает ввода названия задачи
        self.users_awaiting_task_title[user_id] = current_time
        logger.info(f"Установлено состояние ожидания задачи для пользователя {user_id} в {self.users_awaiting_task_title[user_id]}")
        
        text = """➕ *Создание новой задачи*

Введите название задачи в ответ на это сообщение.

*Примеры:*
• Купить молоко
• Выучить Python
• Сделать зарядку

Или используйте команду:
`/newtask Название задачи`"""
        
        keyboard = {
            "type": "inline_keyboard",
            "payload": {
                "buttons": [
                    [
                        {
                            "type": "callback",
                            "text": "📋 К списку задач",
                            "payload": "tasks"
                        },
                        {
                            "type": "callback",
                            "text": "🏠 Главное меню",
                            "payload": "menu"
                        }
                    ]
                ]
            }
        }
        
        await self.api_client.answer_callback(
            callback_id=callback_id,
            message={
                "text": text,
                "attachments": [keyboard],
                "format": "markdown"
            }
        )
    
    async def handle_task_create_confirm(self, user_id: int, task_title: str, callback_id: str, max_user_name: Optional[str] = None):
        """Создать задачу из callback (если название передано)"""
        try:
            # Rate limiting: проверяем, не слишком ли часто пользователь создает задачи
            current_time = time.time()
            if user_id in self.last_task_creation:
                time_since_last = current_time - self.last_task_creation[user_id]
                if time_since_last < self.task_creation_cooldown:
                    logger.warning(f"Пользователь {user_id} слишком часто создает задачи (прошло {time_since_last:.2f} сек)")
                    await self.api_client.answer_callback(
                        callback_id=callback_id,
                        notification="⏳ Пожалуйста, подождите немного перед созданием новой задачи"
                    )
                    return
            
            # Обновляем время последнего создания задачи
            self.last_task_creation[user_id] = current_time
            
            user = await self.user_service.get_or_create_user(user_id, max_user_name=max_user_name)
            user_id_internal = user.get("id") if isinstance(user, dict) else user.id
            
            if not task_title or not task_title.strip():
                await self.api_client.answer_callback(
                    callback_id=callback_id,
                    notification="❌ Укажите название задачи"
                )
                return
            
            title = task_title.strip()
            if len(title) > 200:
                title = title[:197] + "..."
            
            task = await self.task_service.create_task(
                user_id=user_id_internal,
                title=title,
                description=None,
                priority="medium"
            )
            
            reward_coins = task.get('reward_coins', 0)
            reward_intelligence = task.get('reward_intelligence_points', 0)
            
            text = f"""✅ *Задача создана!*

*Название:* {title}
*ID:* {task.get('id', 'N/A')}

💰 *Награда:* {reward_coins} монет
🧠 *Очки интеллекта:* {reward_intelligence}"""
            
            keyboard = self.keyboard_builder.build_task_created_menu()
            
            await self.api_client.answer_callback(
                callback_id=callback_id,
                message={
                    "text": text,
                    "attachments": [keyboard],
                    "format": "markdown"
                }
            )
            
            # Обновляем список задач
            await self.handle_tasks(user_id, callback_id=None, max_user_name=max_user_name)
        except Exception as e:
            logger.error(f"Ошибка создания задачи: {e}")
            await self.api_client.answer_callback(
                callback_id=callback_id,
                notification="❌ Ошибка при создании задачи"
            )
    
    async def handle_task_create_from_reply(
        self,
        user_id: int,
        text: str,
        update: Dict[str, Any],
        max_user_name: Optional[str] = None
    ):
        """Создать задачу из ответа на сообщение о создании задачи"""
        try:
            logger.info(f"Обработка создания задачи из ответа для пользователя {user_id}, текст: {text}")
            
            message = update.get("message", {})
            body = message.get("body", {})
            
            # Проверяем наличие link (ответ на сообщение)
            link = body.get("link")
            if not link:
                link = message.get("link")
            
            # Логируем структуру link для отладки
            logger.debug(f"Структура link объекта: {link}")
            logger.debug(f"Полная структура body: {body}")
            logger.debug(f"Полная структура message: {message}")
            
            replied_message_id = None
            if link:
                # Согласно документации MAX API, message ID находится в поле 'mid'
                # Упрощаем логику - используем только стандартные поля
                replied_message_id = link.get("mid") or link.get("message_id")
                logger.info(f"Извлеченный replied_message_id: {replied_message_id} из link: {link}")
                if not replied_message_id:
                    logger.warning(f"Не удалось извлечь message_id из link. Структура link: {link}")
            
            logger.info(f"Обработка ответа для создания задачи - Пользователь: {user_id}, Ответ на: {replied_message_id}")
            logger.info(f"Текущее состояние users_awaiting_task_title: {list(self.users_awaiting_task_title.keys())}")
            
            # Более надежный способ определения, нужно ли создавать задачу
            should_create_task = False
            
            # Проверка 1: Пользователь в состоянии ожидания создания задачи
            user_in_state = user_id in self.users_awaiting_task_title
            logger.info(f"Проверка 1: Пользователь {user_id} в состоянии ожидания? {user_in_state}")
            
            if user_in_state:
                elapsed_time = time.time() - self.users_awaiting_task_title[user_id]
                logger.info(f"Время с момента установки состояния: {elapsed_time:.1f} секунд")
                if elapsed_time <= 300:  # 5 минут таймаут
                    should_create_task = True
                    logger.info(f"✓ Создание задачи: пользователь в состоянии ожидания (прошло {elapsed_time:.1f} секунд)")
                else:
                    del self.users_awaiting_task_title[user_id]
                    logger.info(f"✗ Время ожидания истекло для пользователя {user_id} ({elapsed_time:.1f} секунд)")
            
            # Проверка 2: Это ответ на сообщение бота о создании задачи
            if not should_create_task and replied_message_id:
                logger.info(f"Проверка 2: Пытаемся получить исходное сообщение {replied_message_id}")
                try:
                    original_message = await self.api_client.get_message(str(replied_message_id))
                    if original_message:
                        original_sender = original_message.get("sender", {})
                        original_text = original_message.get("body", {}).get("text", "")
                        
                        # Проверяем, что исходное сообщение от бота и содержит ключевые слова о создании задачи
                        if original_sender.get("is_bot", False):
                            task_keywords = ["создан", "задач", "назван", "введите", "ответ", "новой", "задачу", "➕", "Создание"]
                            if any(keyword in original_text.lower() for keyword in task_keywords):
                                should_create_task = True
                                logger.info("✓ Создание задачи: ответ на сообщение бота о создании задачи")
                            else:
                                logger.info(f"✗ Исходное сообщение от бота, но не содержит ключевых слов")
                        else:
                            logger.info(f"✗ Исходное сообщение не от бота")
                    else:
                        logger.warning(f"Получен пустой ответ при запросе сообщения {replied_message_id}")
                except Exception as e:
                    logger.warning(f"Не удалось получить исходное сообщение {replied_message_id}: {e}")
            
            # Проверка 3: Fallback - если пользователь недавно запрашивал создание задачи
            if not should_create_task:
                user_in_state_fallback = user_id in self.users_awaiting_task_title
                logger.info(f"Проверка 3 (Fallback): Пользователь {user_id} в состоянии ожидания? {user_in_state_fallback}")
                if user_in_state_fallback:
                    should_create_task = True
                    logger.info("✓ Создание задачи: fallback на состояние пользователя")
            
            logger.info(f"Итоговое решение: should_create_task = {should_create_task}")
            
            if not should_create_task:
                logger.info(f"✗ Не создаем задачу: user_awaiting_task={user_id in self.users_awaiting_task_title}, replied_message_id={replied_message_id}")
                return False
            
            if not text or not text.strip():
                return False
            
            # Проверяем, не является ли это командой
            if text.strip().startswith("/"):
                return False
            
            logger.info(f"Создание задачи из ответа пользователя {user_id}: {text}")
            
            # Rate limiting: проверяем, не слишком ли часто пользователь создает задачи
            current_time = time.time()
            if user_id in self.last_task_creation:
                time_since_last = current_time - self.last_task_creation[user_id]
                if time_since_last < self.task_creation_cooldown:
                    logger.warning(f"Пользователь {user_id} слишком часто создает задачи (прошло {time_since_last:.2f} сек)")
                    return False
            
            # Обновляем время последнего создания задачи
            self.last_task_creation[user_id] = current_time
            
            # Получаем или создаем пользователя
            logger.debug(f"Получение/создание пользователя {user_id}")
            user = await self.user_service.get_or_create_user(user_id, max_user_name=max_user_name)
            user_id_internal = user.get("id") if isinstance(user, dict) else user.id
            logger.info(f"Внутренний ID пользователя: {user_id_internal}")
            
            title = text.strip()
            if len(title) > 200:
                title = title[:197] + "..."
                logger.debug(f"Название задачи обрезано до 200 символов")
            
            logger.info(f"Создание задачи с названием: {title}")
            task = await self.task_service.create_task(
                user_id=user_id_internal,
                title=title,
                description=None,
                priority="medium"
            )
            reward_coins = task.get('reward_coins', 0)
            reward_intelligence = task.get('reward_intelligence_points', 0)
            logger.info(f"Задача успешно создана: ID={task.get('id', 'N/A')}, награда: {reward_coins} монет, {reward_intelligence} очков интеллекта")
            
            text_response = f"""✅ *Задача создана!*

*Название:* {title}
*ID:* {task.get('id', 'N/A')}

💰 *Награда:* {reward_coins} монет
🧠 *Очки интеллекта:* {reward_intelligence}"""
            
            keyboard = self.keyboard_builder.build_task_created_menu()
            
            logger.debug(f"Отправка сообщения пользователю {user_id} о создании задачи")
            await self.api_client.send_message(
                user_id=user_id,
                text=text_response,
                attachments=[keyboard],
                format="markdown"
            )
            
            logger.info(f"Задача успешно создана из ответа пользователя {user_id}, сообщение отправлено")
            
            # Удаляем состояние пользователя после успешного создания задачи
            if user_id in self.users_awaiting_task_title:
                del self.users_awaiting_task_title[user_id]
                logger.debug(f"Состояние ожидания задачи удалено для пользователя {user_id}")
            
            return True
        except Exception as e:
            logger.error(f"Ошибка создания задачи из ответа для пользователя {user_id}: {e}", exc_info=True)
            # Удаляем состояние пользователя при ошибке, чтобы не блокировать дальнейшие попытки
            if user_id in self.users_awaiting_task_title:
                logger.warning(f"Удаление состояния ожидания задачи для пользователя {user_id} из-за ошибки")
                del self.users_awaiting_task_title[user_id]
            return False
    
    async def handle_friend_request_action(
        self,
        user_id: int,
        friendship_id: int,
        action: str,
        callback_id: str,
        update: Optional[Dict[str, Any]] = None,
        max_user_name: Optional[str] = None
    ):
        """Обработать действие с запросом дружбы (принять/отклонить)"""
        try:
            # Получаем message_id из callback для обновления сообщения
            message_id = None
            original_text = ""
            if update:
                # message находится на верхнем уровне update, а не в callback
                message = update.get("message", {})
                
                if message:
                    # message_id находится в body.mid (не в message.id!)
                    body = message.get("body", {})
                    message_id = body.get("mid")  # mid - это message ID в MAX API
                    
                    # Получаем оригинальный текст
                    original_text = body.get("text", "")
                    
                    logger.info(f"Извлеченный message_id: {message_id}, original_text: {original_text[:50] if original_text else 'None'}...")
                else:
                    logger.warning(f"Message не найден в update: {update}")
                    message_id = None
                    original_text = ""
            
            # Получаем внутренний user_id
            user = await self.user_service.get_or_create_user(user_id, max_user_name=max_user_name)
            user_id_internal = user.get("id") if isinstance(user, dict) else user.id
            
            logger.info(f"Обработка {action} для friendship_id={friendship_id}, user_id (max)={user_id}, user_id_internal={user_id_internal}")
            
            social_service = ServiceClient("social")
            
            if action == "accept":
                # Принимаем запрос дружбы
                try:
                    logger.info(f"Отправка POST запроса на /friendships/{friendship_id}/accept")
                    result = await social_service.post(f"/friendships/{friendship_id}/accept")
                    logger.info(f"Ответ от social_service: {result}")
                    await social_service.close()
                    
                    # Обновляем сообщение с результатом и убираем кнопки (удаляем интерактивные элементы)
                    result_text = f"{original_text}\n\n✅ *Запрос дружбы принят!*"
                    if message_id:
                        logger.info(f"Обновление сообщения {message_id} после принятия запроса дружбы")
                        try:
                            await self.api_client.edit_message(
                                message_id=str(message_id),
                                text=result_text,
                                format="markdown",
                                attachments=[]  # Убираем все кнопки - пустой список удаляет все вложения
                            )
                            logger.info(f"Сообщение {message_id} успешно обновлено")
                        except Exception as edit_error:
                            logger.error(f"Ошибка при обновлении сообщения {message_id}: {edit_error}", exc_info=True)
                    else:
                        logger.warning(f"Не удалось получить message_id для обновления сообщения. Update: {update}")
                    await self.api_client.answer_callback(
                        callback_id=callback_id,
                        notification="✅ Запрос дружбы принят!"
                    )
                except Exception as e:
                    await social_service.close()
                    error_message = str(e)
                    logger.error(f"Ошибка при принятии запроса дружбы friendship_id={friendship_id}: {e}", exc_info=True)
                    
                    # Формируем понятное сообщение об ошибке
                    if "404" in error_message or "не найден" in error_message.lower():
                        error_text = "❌ *Запрос дружбы не найден или уже удален*"
                        notification_text = "❌ Запрос не найден"
                    elif "400" in error_message or "уже обработан" in error_message.lower():
                        error_text = "❌ *Запрос дружбы уже обработан*"
                        notification_text = "❌ Запрос уже обработан"
                    else:
                        error_text = f"❌ *Ошибка при принятии запроса дружбы*\n\n{error_message[:100]}"
                        notification_text = "❌ Ошибка при принятии запроса"
                    
                    result_text = f"{original_text}\n\n{error_text}"
                    if message_id:
                        try:
                            await self.api_client.edit_message(
                                message_id=str(message_id),
                                text=result_text,
                                format="markdown"
                            )
                        except Exception as edit_error:
                            logger.error(f"Ошибка при обновлении сообщения об ошибке: {edit_error}", exc_info=True)
                    await self.api_client.answer_callback(
                        callback_id=callback_id,
                        notification=notification_text
                    )
            elif action == "reject":
                # Отклоняем запрос дружбы
                try:
                    result = await social_service.delete(f"/friendships/{friendship_id}")
                    await social_service.close()
                    
                    # Обновляем сообщение с результатом и убираем кнопки (удаляем интерактивные элементы)
                    result_text = f"{original_text}\n\n❌ *Запрос дружбы отклонен*"
                    if message_id:
                        await self.api_client.edit_message(
                            message_id=str(message_id),
                            text=result_text,
                            format="markdown",
                            attachments=[]  # Убираем все кнопки
                        )
                    await self.api_client.answer_callback(
                        callback_id=callback_id,
                        notification="❌ Запрос дружбы отклонен"
                    )
                except Exception as e:
                    await social_service.close()
                    logger.error(f"Ошибка при отклонении запроса дружбы: {e}")
                    result_text = f"{original_text}\n\n❌ *Ошибка при отклонении запроса дружбы*"
                    if message_id:
                        await self.api_client.edit_message(
                            message_id=str(message_id),
                            text=result_text,
                            format="markdown"
                        )
                    await self.api_client.answer_callback(
                        callback_id=callback_id,
                        notification="❌ Ошибка при отклонении запроса дружбы"
                    )
        except Exception as e:
            logger.error(f"Ошибка обработки действия с запросом дружбы: {e}", exc_info=True)
            await self.api_client.answer_callback(
                callback_id=callback_id,
                notification="❌ Произошла ошибка"
            )
    
    async def handle_group_invitation_action(
        self,
        user_id: int,
        invitation_id: int,
        action: str,
        callback_id: str,
        update: Optional[Dict[str, Any]] = None,
        max_user_name: Optional[str] = None
    ):
        """Обработать действие с приглашением в группу (принять/отклонить)"""
        try:
            # Получаем message_id из callback для обновления сообщения
            message_id = None
            original_text = ""
            if update:
                message = update.get("message", {})
                if message:
                    body = message.get("body", {})
                    message_id = body.get("mid")
                    original_text = body.get("text", "")
                else:
                    logger.warning(f"Message не найден в update: {update}")
                    message_id = None
                    original_text = ""
            
            logger.info(f"Обработка {action} для invitation_id={invitation_id}, user_id (max)={user_id}")
            
            social_service = ServiceClient("social")
            
            if action == "accept":
                # Принимаем приглашение в группу
                try:
                    logger.info(f"Отправка POST запроса на /groups/invitations/{invitation_id}/accept")
                    result = await social_service.post(f"/groups/invitations/{invitation_id}/accept")
                    logger.info(f"Ответ от social_service: {result}")
                    await social_service.close()
                    
                    # Проверяем успешность операции
                    if result and result.get("success"):
                        # Обновляем сообщение с результатом и убираем кнопки
                        result_text = f"{original_text}\n\n✅ *Приглашение в группу принято!*"
                        if message_id:
                            logger.info(f"Обновление сообщения {message_id} после принятия приглашения")
                            try:
                                await self.api_client.edit_message(
                                    message_id=str(message_id),
                                    text=result_text,
                                    format="markdown",
                                    attachments=[]  # Убираем все кнопки
                                )
                                logger.info(f"Сообщение {message_id} успешно обновлено")
                            except Exception as edit_error:
                                logger.error(f"Ошибка при обновлении сообщения {message_id}: {edit_error}", exc_info=True)
                                # Даже если не удалось обновить сообщение, отправляем уведомление
                        await self.api_client.answer_callback(
                            callback_id=callback_id,
                            notification="✅ Приглашение в группу принято!"
                        )
                    else:
                        # Если success=False или ответ неожиданный
                        logger.warning(f"Неожиданный ответ от API: {result}")
                        result_text = f"{original_text}\n\n✅ *Приглашение в группу принято!*"
                        if message_id:
                            try:
                                await self.api_client.edit_message(
                                    message_id=str(message_id),
                                    text=result_text,
                                    format="markdown",
                                    attachments=[]
                                )
                            except Exception as edit_error:
                                logger.error(f"Ошибка при обновлении сообщения {message_id}: {edit_error}", exc_info=True)
                        await self.api_client.answer_callback(
                            callback_id=callback_id,
                            notification="✅ Приглашение в группу принято!"
                        )
                except Exception as e:
                    await social_service.close()
                    error_message = str(e)
                    logger.error(f"Ошибка при принятии приглашения invitation_id={invitation_id}: {e}", exc_info=True)
                    
                    # Проверяем, возможно операция все же выполнилась (пользователь добавился)
                    # В этом случае показываем успех, а не ошибку
                    if "уже в группе" in error_message.lower() or "уже обработано" in error_message.lower():
                        # Пользователь уже в группе - это успех
                        result_text = f"{original_text}\n\n✅ *Вы уже в группе!*"
                        if message_id:
                            try:
                                await self.api_client.edit_message(
                                    message_id=str(message_id),
                                    text=result_text,
                                    format="markdown",
                                    attachments=[]
                                )
                            except Exception as edit_error:
                                logger.error(f"Ошибка при обновлении сообщения {message_id}: {edit_error}", exc_info=True)
                        await self.api_client.answer_callback(
                            callback_id=callback_id,
                            notification="✅ Вы уже в группе!"
                        )
                    else:
                        # Формируем понятное сообщение об ошибке
                        if "404" in error_message or "не найден" in error_message.lower():
                            error_text = "❌ *Приглашение не найдено или уже удалено*"
                            notification_text = "❌ Приглашение не найдено"
                        elif "400" in error_message:
                            error_text = "❌ *Приглашение уже обработано*"
                            notification_text = "❌ Приглашение уже обработано"
                        else:
                            # Если это не критичная ошибка, показываем успех
                            # (возможно, операция выполнилась, но ответ не обработался)
                            error_text = "✅ *Приглашение в группу принято!*"
                            notification_text = "✅ Приглашение принято!"
                            logger.warning(f"Неизвестная ошибка, но предполагаем успех: {error_message}")
                        
                        result_text = f"{original_text}\n\n{error_text}"
                        if message_id:
                            try:
                                await self.api_client.edit_message(
                                    message_id=str(message_id),
                                    text=result_text,
                                    format="markdown",
                                    attachments=[]
                                )
                            except Exception as edit_error:
                                logger.error(f"Ошибка при обновлении сообщения {message_id}: {edit_error}", exc_info=True)
                        await self.api_client.answer_callback(
                            callback_id=callback_id,
                            notification=notification_text
                        )
            elif action == "reject":
                # Отклоняем приглашение в группу
                try:
                    logger.info(f"Отправка POST запроса на /groups/invitations/{invitation_id}/reject")
                    result = await social_service.post(f"/groups/invitations/{invitation_id}/reject")
                    logger.info(f"Ответ от social_service: {result}")
                    await social_service.close()
                    
                    # Обновляем сообщение с результатом и убираем кнопки
                    result_text = f"{original_text}\n\n❌ *Приглашение в группу отклонено*"
                    if message_id:
                        await self.api_client.edit_message(
                            message_id=str(message_id),
                            text=result_text,
                            format="markdown",
                            attachments=[]  # Убираем все кнопки
                        )
                    await self.api_client.answer_callback(
                        callback_id=callback_id,
                        notification="❌ Приглашение в группу отклонено"
                    )
                except Exception as e:
                    await social_service.close()
                    logger.error(f"Ошибка при отклонении приглашения: {e}")
                    result_text = f"{original_text}\n\n❌ *Ошибка при отклонении приглашения*"
                    if message_id:
                        await self.api_client.edit_message(
                            message_id=str(message_id),
                            text=result_text,
                            format="markdown"
                        )
                    await self.api_client.answer_callback(
                        callback_id=callback_id,
                        notification="❌ Ошибка при отклонении приглашения"
                    )
        except Exception as e:
            logger.error(f"Ошибка обработки действия с приглашением в группу: {e}", exc_info=True)
            await self.api_client.answer_callback(
                callback_id=callback_id,
                notification="❌ Произошла ошибка"
            )
    
    async def handle_trade_request_action(
        self,
        user_id: int,
        trade_id: int,
        action: str,
        callback_id: str,
        update: Optional[Dict[str, Any]] = None,
        max_user_name: Optional[str] = None
    ):
        """Обработать действие с предложением обмена (принять/отклонить)"""
        try:
            # Получаем message_id из callback для обновления сообщения
            message_id = None
            original_text = ""
            if update:
                # message находится на верхнем уровне update, а не в callback
                message = update.get("message", {})
                
                if message:
                    # message_id находится в body.mid (не в message.id!)
                    body = message.get("body", {})
                    message_id = body.get("mid")  # mid - это message ID в MAX API
                    
                    # Получаем оригинальный текст
                    original_text = body.get("text", "")
                else:
                    logger.warning(f"Message не найден в update: {update}")
                    message_id = None
                    original_text = ""
            
            # Получаем внутренний user_id
            user = await self.user_service.get_or_create_user(user_id, max_user_name=max_user_name)
            user_id_internal = user.get("id") if isinstance(user, dict) else user.id
            
            inventory_service = ServiceClient("inventory")
            
            if action == "accept":
                # Принимаем предложение обмена
                try:
                    result = await inventory_service.post(f"/trades/{trade_id}/accept")
                    await inventory_service.close()
                    
                    # Обновляем сообщение с результатом и убираем кнопки (удаляем интерактивные элементы)
                    result_text = f"{original_text}\n\n✅ *Обмен принят! Предметы обменяны.*"
                    if message_id:
                        await self.api_client.edit_message(
                            message_id=str(message_id),
                            text=result_text,
                            format="markdown",
                            attachments=[]  # Убираем все кнопки
                        )
                    await self.api_client.answer_callback(
                        callback_id=callback_id,
                        notification="✅ Обмен принят! Предметы обменяны."
                    )
                except Exception as e:
                    await inventory_service.close()
                    logger.error(f"Ошибка при принятии обмена: {e}")
                    result_text = f"{original_text}\n\n❌ *Ошибка при принятии обмена*"
                    if message_id:
                        await self.api_client.edit_message(
                            message_id=str(message_id),
                            text=result_text,
                            format="markdown"
                        )
                    await self.api_client.answer_callback(
                        callback_id=callback_id,
                        notification="❌ Ошибка при принятии обмена"
                    )
            elif action == "reject":
                # Отклоняем предложение обмена
                try:
                    result = await inventory_service.post(f"/trades/{trade_id}/reject")
                    await inventory_service.close()
                    
                    # Обновляем сообщение с результатом и убираем кнопки (удаляем интерактивные элементы)
                    result_text = f"{original_text}\n\n❌ *Обмен отклонен*"
                    if message_id:
                        await self.api_client.edit_message(
                            message_id=str(message_id),
                            text=result_text,
                            format="markdown",
                            attachments=[]  # Убираем все кнопки
                        )
                    await self.api_client.answer_callback(
                        callback_id=callback_id,
                        notification="❌ Обмен отклонен"
                    )
                except Exception as e:
                    await inventory_service.close()
                    logger.error(f"Ошибка при отклонении обмена: {e}")
                    result_text = f"{original_text}\n\n❌ *Ошибка при отклонении обмена*"
                    if message_id:
                        await self.api_client.edit_message(
                            message_id=str(message_id),
                            text=result_text,
                            format="markdown"
                        )
                    await self.api_client.answer_callback(
                        callback_id=callback_id,
                        notification="❌ Ошибка при отклонении обмена"
                    )
        except Exception as e:
            logger.error(f"Ошибка обработки действия с обменом: {e}", exc_info=True)
            await self.api_client.answer_callback(
                callback_id=callback_id,
                notification="❌ Произошла ошибка"
            )
    
    async def handle_competition_join(
        self,
        user_id: int,
        competition_id: int,
        callback_id: str,
        update: Optional[Dict[str, Any]] = None,
        max_user_name: Optional[str] = None
    ):
        """Обработать присоединение к соревнованию"""
        try:
            # Получаем message_id из callback для обновления сообщения
            message_id = None
            original_text = ""
            if update:
                # message находится на верхнем уровне update, а не в callback
                message = update.get("message", {})
                
                if message:
                    # message_id находится в body.mid (не в message.id!)
                    body = message.get("body", {})
                    message_id = body.get("mid")  # mid - это message ID в MAX API
                    
                    # Получаем оригинальный текст
                    original_text = body.get("text", "")
                else:
                    logger.warning(f"Message не найден в update: {update}")
                    message_id = None
                    original_text = ""
            
            # Получаем внутренний user_id
            logger.info(f"Получение/создание пользователя max_id={user_id}, max_user_name={max_user_name}")
            user = await self.user_service.get_or_create_user(user_id, max_user_name=max_user_name)
            user_id_internal = user.get("id") if isinstance(user, dict) else user.id
            logger.info(f"Получен внутренний user_id={user_id_internal} для max_id={user_id}")
            
            competition_service = ServiceClient("competition")
            
            try:
                logger.info(f"Попытка присоединения пользователя {user_id_internal} (max_id: {user_id}) к соревнованию {competition_id}")
                result = await competition_service.post(f"/competitions/{competition_id}/join", params={"user_id": user_id_internal})
                
                logger.info(f"Успешное присоединение пользователя {user_id_internal} (max_id: {user_id}) к соревнованию {competition_id}. Результат: {result}")
                
                # Получить информацию о соревновании для более детального сообщения
                competition_info = None
                try:
                    competition_info = await competition_service.get(f"/competitions/{competition_id}")
                except Exception as e:
                    logger.warning(f"Не удалось получить информацию о соревновании: {e}")
                finally:
                    await competition_service.close()
                
                # Обновляем сообщение с результатом и убираем кнопки
                if competition_info and competition_info.get('target_value'):
                    metric_labels = {
                        'tasks_completed': 'выполненных задач',
                        'habits_completed': 'записей в дневнике',
                        'coins_balance': 'монет',
                        'intelligence_points': 'очков интеллекта'
                    }
                    metric_label = metric_labels.get(competition_info.get('metric_type', ''), competition_info.get('metric_type', ''))
                    result_text = f"{original_text}\n\n✅ *Вы присоединились к соревнованию!*\n\n🎯 *Цель:* {competition_info.get('target_value')} {metric_label}\n\nУдачи в соревновании!"
                else:
                    result_text = f"{original_text}\n\n✅ *Вы присоединились к соревнованию!*\n\nУдачи в соревновании!"
                if message_id:
                    try:
                        await self.api_client.edit_message(
                            message_id=str(message_id),
                            text=result_text,
                            attachments=[],  # Убираем все кнопки
                            format="markdown"
                        )
                        logger.info(f"Сообщение {message_id} успешно обновлено")
                    except Exception as edit_error:
                        logger.error(f"Ошибка обновления сообщения {message_id}: {edit_error}", exc_info=True)
                
                try:
                    await self.api_client.answer_callback(
                        callback_id=callback_id,
                        notification="✅ Вы присоединились к соревнованию!"
                    )
                    logger.info(f"Callback {callback_id} успешно обработан")
                except Exception as callback_error:
                    logger.error(f"Ошибка ответа на callback {callback_id}: {callback_error}", exc_info=True)
            except Exception as e:
                await competition_service.close()
                logger.error(f"Ошибка при присоединении к соревнованию: {e}", exc_info=True)
                error_msg = str(e)
                if "уже участвует" in error_msg:
                    result_text = f"{original_text}\n\n⚠️ *Вы уже участвуете в этом соревновании*"
                else:
                    result_text = f"{original_text}\n\n❌ *Ошибка при присоединении к соревнованию*"
                
                if message_id:
                    await self.api_client.edit_message(
                        message_id=message_id,
                        text=result_text,
                        format="markdown"
                    )
                await self.api_client.answer_callback(
                    callback_id=callback_id,
                    notification="❌ Не удалось присоединиться к соревнованию"
                )
        except Exception as e:
            logger.error(f"Ошибка обработки присоединения к соревнованию: {e}", exc_info=True)
            await self.api_client.answer_callback(
                callback_id=callback_id,
                notification="❌ Произошла ошибка"
            )
    
    async def handle_competition_decline(
        self,
        user_id: int,
        competition_id: int,
        callback_id: str,
        update: Optional[Dict[str, Any]] = None,
        max_user_name: Optional[str] = None
    ):
        """Обработать отказ от участия в соревновании"""
        try:
            # Получаем message_id из callback для обновления сообщения
            message_id = None
            original_text = ""
            if update:
                message = update.get("message", {})
                if message:
                    body = message.get("body", {})
                    message_id = body.get("mid")
                    original_text = body.get("text", "")
            
            # Получаем внутренний user_id
            user = await self.user_service.get_or_create_user(user_id, max_user_name=max_user_name)
            user_id_internal = user.get("id") if isinstance(user, dict) else user.id
            
            competition_service = ServiceClient("competition")
            
            try:
                result = await competition_service.post(f"/competitions/{competition_id}/decline", params={"user_id": user_id_internal})
                await competition_service.close()
                
                # Обновляем сообщение с результатом и убираем кнопки
                result_text = f"{original_text}\n\n❌ *Вы отказались от участия в соревновании*"
                if message_id:
                    await self.api_client.edit_message(
                        message_id=str(message_id),
                        text=result_text,
                        attachments=[],  # Убираем все кнопки
                        format="markdown"
                    )
                await self.api_client.answer_callback(
                    callback_id=callback_id,
                    notification="❌ Вы отказались от участия в соревновании"
                )
            except Exception as e:
                await competition_service.close()
                logger.error(f"Ошибка при отказе от соревнования: {e}")
                error_msg = str(e)
                if "уже отказался" in error_msg:
                    result_text = f"{original_text}\n\n⚠️ *Вы уже отказались от этого соревнования*"
                else:
                    result_text = f"{original_text}\n\n❌ *Ошибка при отказе от соревнования*"
                
                if message_id:
                    await self.api_client.edit_message(
                        message_id=message_id,
                        text=result_text,
                        format="markdown"
                    )
                await self.api_client.answer_callback(
                    callback_id=callback_id,
                    notification="❌ Не удалось отказаться от соревнования"
                )
        except Exception as e:
            logger.error(f"Ошибка обработки отказа от соревнования: {e}", exc_info=True)
            await self.api_client.answer_callback(
                callback_id=callback_id,
                notification="❌ Произошла ошибка"
            )
    
    async def handle_challenge_action(
        self,
        user_id: int,
        challenge_id: int,
        action: str,
        callback_id: str,
        update: Optional[Dict[str, Any]] = None,
        max_user_name: Optional[str] = None
    ):
        """Обработать действие с челленджем (принять/отклонить)"""
        try:
            # Получаем message_id из callback для обновления сообщения
            message_id = None
            original_text = ""
            if update:
                # message находится на верхнем уровне update, а не в callback
                message = update.get("message", {})
                
                if message:
                    # message_id находится в body.mid (не в message.id!)
                    body = message.get("body", {})
                    message_id = body.get("mid")  # mid - это message ID в MAX API
                    
                    # Получаем оригинальный текст
                    original_text = body.get("text", "")
                else:
                    logger.warning(f"Message не найден в update: {update}")
                    message_id = None
                    original_text = ""
            
            # Получаем внутренний user_id
            user = await self.user_service.get_or_create_user(user_id, max_user_name=max_user_name)
            user_id_internal = user.get("id") if isinstance(user, dict) else user.id
            
            competition_service = ServiceClient("competition")
            
            if action == "accept":
                # Принимаем челлендж
                try:
                    result = await competition_service.post(
                        f"/challenges/{challenge_id}/accept",
                        json={"user_id": user_id_internal}
                    )
                    await competition_service.close()
                    
                    # Обновляем сообщение с результатом и убираем кнопки
                    result_text = f"{original_text}\n\n✅ *Челлендж принят!*"
                    if message_id:
                        await self.api_client.edit_message(
                            message_id=str(message_id),
                            text=result_text,
                            format="markdown",
                            attachments=[]  # Убираем все кнопки
                        )
                    await self.api_client.answer_callback(
                        callback_id=callback_id,
                        notification="✅ Челлендж принят!"
                    )
                except Exception as e:
                    await competition_service.close()
                    logger.error(f"Ошибка при принятии челленджа: {e}")
                    result_text = f"{original_text}\n\n❌ *Ошибка при принятии челленджа*"
                    if message_id:
                        await self.api_client.edit_message(
                            message_id=str(message_id),
                            text=result_text,
                            format="markdown",
                            attachments=[]  # Убираем все кнопки
                        )
                    await self.api_client.answer_callback(
                        callback_id=callback_id,
                        notification="❌ Ошибка при принятии челленджа"
                    )
            elif action == "reject":
                # Отклоняем челлендж
                try:
                    result = await competition_service.post(
                        f"/challenges/{challenge_id}/decline",
                        json={"user_id": user_id_internal}
                    )
                    await competition_service.close()
                    
                    # Обновляем сообщение с результатом и убираем кнопки
                    result_text = f"{original_text}\n\n❌ *Челлендж отклонен*"
                    if message_id:
                        await self.api_client.edit_message(
                            message_id=str(message_id),
                            text=result_text,
                            format="markdown",
                            attachments=[]  # Убираем все кнопки
                        )
                    await self.api_client.answer_callback(
                        callback_id=callback_id,
                        notification="❌ Челлендж отклонен"
                    )
                except Exception as e:
                    await competition_service.close()
                    logger.error(f"Ошибка при отклонении челленджа: {e}")
                    result_text = f"{original_text}\n\n❌ *Ошибка при отклонении челленджа*"
                    if message_id:
                        await self.api_client.edit_message(
                            message_id=str(message_id),
                            text=result_text,
                            format="markdown",
                            attachments=[]  # Убираем все кнопки
                        )
                    await self.api_client.answer_callback(
                        callback_id=callback_id,
                        notification="❌ Ошибка при отклонении челленджа"
                    )
        except Exception as e:
            logger.error(f"Ошибка обработки действия с челленджем: {e}", exc_info=True)
            await self.api_client.answer_callback(
                callback_id=callback_id,
                notification="❌ Произошла ошибка"
            )

