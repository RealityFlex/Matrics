"""
MAX Bot Service - Главный файл
Порт: 8020
"""
import asyncio
import logging
from fastapi import FastAPI, Depends
from contextlib import asynccontextmanager

from services.max_bot_service.config import MAX_BOT_TOKEN, LONG_POLLING_TIMEOUT
from services.max_bot_service.max_api_client import MaxApiClient
from services.max_bot_service.handlers.update_handler import UpdateHandler
from services.max_bot_service.utils.stats import stats
from services.max_bot_service.utils.settings import bot_settings
from services.max_bot_service.services.notification_service import NotificationService
from pydantic import BaseModel
from services.shared.auth import require_admin
from typing import Optional, List

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Глобальные объекты
max_api_client = None
update_handler = None
polling_task = None
notification_service = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    global max_api_client, update_handler, polling_task, notification_service
    
    # Инициализация
    logger.info("Инициализация MAX Bot Service...")
    max_api_client = MaxApiClient(MAX_BOT_TOKEN)
    update_handler = UpdateHandler(max_api_client)
    notification_service = NotificationService(max_api_client)
    
    # Регистрация команд бота
    try:
        bot_commands = [
            {"name": "start", "description": "Начать работу с ботом"},
            {"name": "checkin", "description": "Отметиться на паре: /checkin 1234"},
            {"name": "streak", "description": "Серия посещений и «дни без штрафа»"},
            {"name": "help", "description": "Справка по командам"},
            {"name": "profile", "description": "Ваш профиль и персонаж"},
            {"name": "tasks", "description": "Список ваших задач"},
            {"name": "newtask", "description": "Создать новую задачу"},
            {"name": "character", "description": "Информация о персонаже"},
            {"name": "stats", "description": "Ваша статистика"},
            {"name": "inventory", "description": "Ваш инвентарь"},
            {"name": "achievements", "description": "Ваши достижения"}
        ]
        await max_api_client.set_commands(bot_commands)
        logger.info("✅ Команды бота успешно зарегистрированы")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось зарегистрировать команды бота: {e}")
    
    # Запуск Long Polling в фоне
    async def start_polling():
        await update_handler.start_long_polling()
    
    polling_task = asyncio.create_task(start_polling())
    logger.info("MAX Bot Service запущен")
    
    yield
    
    # Остановка
    logger.info("Остановка MAX Bot Service...")
    if polling_task:
        polling_task.cancel()
        try:
            await polling_task
        except asyncio.CancelledError:
            pass
    logger.info("MAX Bot Service остановлен")


# FastAPI приложение
app = FastAPI(
    title="MAX Bot Service",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def root():
    """Корневой эндпоинт"""
    return {"service": "MAX Bot Service", "version": "1.0.0"}


@app.get("/health")
async def health():
    """Health check"""
    return {"status": "healthy"}


@app.get("/updates", dependencies=[Depends(require_admin)])
async def get_updates():
    """Получение обновлений (для тестирования)"""
    if not max_api_client:
        return {"error": "Service not initialized"}
    
    try:
        updates = await max_api_client.get_updates(timeout=LONG_POLLING_TIMEOUT)
        return updates
    except Exception as e:
        logger.error(f"Error getting updates: {e}")
        return {"error": str(e)}


@app.get("/stats")
async def get_stats():
    """Получить статистику по сообщениям"""
    return stats.get_stats()


# Pydantic модели для настроек
class SettingsUpdate(BaseModel):
    enabled: bool


@app.get("/settings")
async def get_settings():
    """Получить настройки бота"""
    return bot_settings.get_settings()


@app.put("/settings", dependencies=[Depends(require_admin)])
async def update_settings(settings: SettingsUpdate):
    """Обновить настройки бота"""
    try:
        logger.info(f"Обновление настроек бота: enabled={settings.enabled}")
        bot_settings.update_settings({"enabled": settings.enabled})
        updated_settings = bot_settings.get_settings()
        logger.info(f"Настройки успешно обновлены: {updated_settings}")
        return {"message": "Настройки обновлены", "settings": updated_settings}
    except Exception as e:
        logger.error(f"Ошибка при обновлении настроек: {e}", exc_info=True)
        raise


# ===== УВЕДОМЛЕНИЯ =====

class FriendRequestNotification(BaseModel):
    recipient_user_id: int
    initiator_user_id: int
    friendship_id: int
    initiator_username: Optional[str] = None


class FriendRequestAcceptedNotification(BaseModel):
    initiator_user_id: int
    acceptor_username: Optional[str] = None


class TradeRequestNotification(BaseModel):
    recipient_user_id: int
    initiator_user_id: int
    trade_id: int
    initiator_username: Optional[str] = None
    initiator_item_name: Optional[str] = None
    requested_item_name: Optional[str] = None
    initiator_quantity: int = 1
    requested_quantity: int = 1


class TradeRequestAcceptedNotification(BaseModel):
    initiator_user_id: int
    acceptor_username: Optional[str] = None


class TradeRequestRejectedNotification(BaseModel):
    initiator_user_id: int
    rejector_username: Optional[str] = None


class ShopPurchaseNotification(BaseModel):
    seller_user_id: int
    buyer_username: Optional[str] = None
    item_name: Optional[str] = None
    quantity: int = 1
    total_price: int = 0


class CompetitionCreatedNotification(BaseModel):
    user_ids: List[int]
    competition_name: str
    competition_id: int
    description: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None


class CompetitionFinishedNotification(BaseModel):
    user_id: int
    competition_name: str
    rank: Optional[int] = None
    reward_coins: int = 0


class ChallengeRequestNotification(BaseModel):
    recipient_user_id: int
    initiator_user_id: int
    challenge_id: int
    initiator_username: Optional[str] = None
    metric_type: Optional[str] = None
    target_value: int = 0
    deadline: Optional[str] = None
    reward_coins: int = 0


class ChallengeAcceptedNotification(BaseModel):
    initiator_user_id: int
    acceptor_username: Optional[str] = None


class ChallengeRejectedNotification(BaseModel):
    initiator_user_id: int
    rejector_username: Optional[str] = None


class ChallengeCompletedNotification(BaseModel):
    winner_user_id: int
    loser_user_id: int
    challenge_id: int
    winner_name: Optional[str] = None
    loser_name: Optional[str] = None
    reward_coins: int = 0


class GroupInvitationNotification(BaseModel):
    recipient_user_id: int
    inviter_user_id: int
    group_id: int
    group_name: str
    inviter_username: Optional[str] = None
    invitation_id: int


class LowSatisfactionNotification(BaseModel):
    user_id: int
    satisfaction: int
    character_name: Optional[str] = None


class HabitActivatedNotification(BaseModel):
    user_id: int
    habit_name: str
    frequency: str


class DailyRewardUpdatedNotification(BaseModel):
    user_id: int


class AttendanceConfirmedNotification(BaseModel):
    user_id: int
    lesson_id: Optional[int] = None
    lesson_name: str
    rewards: Optional[dict] = None
    rewards_status: str = "granted"
    character: Optional[dict] = None
    streak: Optional[dict] = None
    unlocked_sets: Optional[List[dict]] = None


class LessonMissedNotification(BaseModel):
    user_id: int
    miss_id: int
    lesson_id: Optional[int] = None
    lesson_name: str
    deadline: Optional[str] = None
    freezes_available: int = 0
    penalty: int = 10


@app.post("/notifications/friend-request")
async def send_friend_request_notification(notification: FriendRequestNotification):
    """Отправить уведомление о запросе дружбы"""
    if not notification_service:
        return {"error": "Service not initialized"}
    
    success = await notification_service.send_friend_request_notification(
        recipient_user_id=notification.recipient_user_id,
        initiator_user_id=notification.initiator_user_id,
        friendship_id=notification.friendship_id,
        initiator_username=notification.initiator_username
    )
    return {"success": success}


@app.post("/notifications/friend-request-accepted")
async def send_friend_request_accepted_notification(notification: FriendRequestAcceptedNotification):
    """Отправить уведомление о принятии запроса дружбы"""
    if not notification_service:
        return {"error": "Service not initialized"}
    
    success = await notification_service.send_friend_request_accepted_notification(
        initiator_user_id=notification.initiator_user_id,
        acceptor_username=notification.acceptor_username
    )
    return {"success": success}


@app.post("/notifications/trade-request")
async def send_trade_request_notification(notification: TradeRequestNotification):
    """Отправить уведомление о предложении обмена"""
    if not notification_service:
        return {"error": "Service not initialized"}
    
    success = await notification_service.send_trade_request_notification(
        recipient_user_id=notification.recipient_user_id,
        initiator_user_id=notification.initiator_user_id,
        trade_id=notification.trade_id,
        initiator_username=notification.initiator_username,
        initiator_item_name=notification.initiator_item_name,
        requested_item_name=notification.requested_item_name,
        initiator_quantity=notification.initiator_quantity,
        requested_quantity=notification.requested_quantity
    )
    return {"success": success}


@app.post("/notifications/trade-request-accepted")
async def send_trade_request_accepted_notification(notification: TradeRequestAcceptedNotification):
    """Отправить уведомление о принятии предложения обмена"""
    if not notification_service:
        return {"error": "Service not initialized"}
    
    success = await notification_service.send_trade_request_accepted_notification(
        initiator_user_id=notification.initiator_user_id,
        acceptor_username=notification.acceptor_username
    )
    return {"success": success}


@app.post("/notifications/trade-request-rejected")
async def send_trade_request_rejected_notification(notification: TradeRequestRejectedNotification):
    """Отправить уведомление об отклонении предложения обмена"""
    if not notification_service:
        return {"error": "Service not initialized"}
    
    success = await notification_service.send_trade_request_rejected_notification(
        initiator_user_id=notification.initiator_user_id,
        rejector_username=notification.rejector_username
    )
    return {"success": success}


@app.post("/notifications/shop-purchase")
async def send_shop_purchase_notification(notification: ShopPurchaseNotification):
    """Отправить уведомление о покупке товара"""
    if not notification_service:
        return {"error": "Service not initialized"}
    
    success = await notification_service.send_shop_purchase_notification(
        seller_user_id=notification.seller_user_id,
        buyer_username=notification.buyer_username,
        item_name=notification.item_name,
        quantity=notification.quantity,
        total_price=notification.total_price
    )
    return {"success": success}


@app.post("/notifications/competition-created")
async def send_competition_created_notification(notification: CompetitionCreatedNotification):
    """Отправить уведомление о создании нового соревнования"""
    if not notification_service:
        return {"error": "Service not initialized"}
    
    sent_count = await notification_service.send_competition_created_notification(
        user_ids=notification.user_ids,
        competition_name=notification.competition_name,
        competition_id=notification.competition_id,
        description=notification.description,
        start_time=notification.start_time,
        end_time=notification.end_time
    )
    return {"sent_count": sent_count}


@app.post("/notifications/competition-finished")
async def send_competition_finished_notification(notification: CompetitionFinishedNotification):
    """Отправить уведомление о завершении соревнования"""
    if not notification_service:
        return {"error": "Service not initialized"}
    
    success = await notification_service.send_competition_finished_notification(
        user_id=notification.user_id,
        competition_name=notification.competition_name,
        rank=notification.rank,
        reward_coins=notification.reward_coins
    )
    return {"success": success}


@app.post("/notifications/challenge-request")
async def send_challenge_request_notification(notification: ChallengeRequestNotification):
    """Отправить уведомление о запросе челленджа"""
    if not notification_service:
        return {"error": "Service not initialized"}
    
    success = await notification_service.send_challenge_request_notification(
        recipient_user_id=notification.recipient_user_id,
        initiator_user_id=notification.initiator_user_id,
        challenge_id=notification.challenge_id,
        initiator_username=notification.initiator_username,
        metric_type=notification.metric_type,
        target_value=notification.target_value,
        deadline=notification.deadline,
        reward_coins=notification.reward_coins
    )
    return {"success": success}


@app.post("/notifications/challenge-accepted")
async def send_challenge_accepted_notification(notification: ChallengeAcceptedNotification):
    """Отправить уведомление о принятии челленджа"""
    if not notification_service:
        return {"error": "Service not initialized"}
    
    success = await notification_service.send_challenge_accepted_notification(
        initiator_user_id=notification.initiator_user_id,
        acceptor_username=notification.acceptor_username
    )
    return {"success": success}


@app.post("/notifications/challenge-rejected")
async def send_challenge_rejected_notification(notification: ChallengeRejectedNotification):
    """Отправить уведомление об отклонении челленджа"""
    if not notification_service:
        return {"error": "Service not initialized"}
    
    success = await notification_service.send_challenge_rejected_notification(
        initiator_user_id=notification.initiator_user_id,
        rejector_username=notification.rejector_username
    )
    return {"success": success}


@app.post("/notifications/challenge-completed")
async def send_challenge_completed_notification(notification: ChallengeCompletedNotification):
    """Отправить уведомление о завершении челленджа"""
    if not notification_service:
        return {"error": "Service not initialized"}
    
    success = await notification_service.send_challenge_completed_notification(
        winner_user_id=notification.winner_user_id,
        loser_user_id=notification.loser_user_id,
        challenge_id=notification.challenge_id,
        winner_name=notification.winner_name,
        loser_name=notification.loser_name,
        reward_coins=notification.reward_coins
    )
    return {"success": success}


@app.post("/notifications/group-invitation")
async def send_group_invitation_notification(notification: GroupInvitationNotification):
    """Отправить уведомление о приглашении в группу"""
    if not notification_service:
        return {"error": "Service not initialized"}
    
    success = await notification_service.send_group_invitation_notification(
        recipient_user_id=notification.recipient_user_id,
        inviter_user_id=notification.inviter_user_id,
        group_id=notification.group_id,
        group_name=notification.group_name,
        invitation_id=notification.invitation_id,
        inviter_username=notification.inviter_username
    )
    return {"success": success}


@app.post("/notifications/low-satisfaction")
async def send_low_satisfaction_notification(notification: LowSatisfactionNotification):
    """Отправить уведомление о низкой удовлетворённости персонажа"""
    if not notification_service:
        return {"error": "Service not initialized"}
    
    success = await notification_service.send_low_satisfaction_notification(
        user_id=notification.user_id,
        satisfaction=notification.satisfaction,
        character_name=notification.character_name
    )
    return {"success": success}


@app.post("/notifications/habit-activated")
async def send_habit_activated_notification(notification: HabitActivatedNotification):
    """Отправить уведомление об активации привычки"""
    if not notification_service:
        return {"error": "Service not initialized"}
    
    success = await notification_service.send_habit_activated_notification(
        user_id=notification.user_id,
        habit_name=notification.habit_name,
        frequency=notification.frequency
    )
    return {"success": success}


@app.post("/notifications/daily-reward-updated")
async def send_daily_reward_updated_notification(notification: DailyRewardUpdatedNotification):
    """Отправить уведомление об обновлении ежедневного приза"""
    if not notification_service:
        return {"error": "Service not initialized"}
    
    success = await notification_service.send_daily_reward_updated_notification(
        user_id=notification.user_id
    )
    return {"success": success}



@app.post("/notifications/attendance-confirmed")
async def send_attendance_confirmed_notification(notification: AttendanceConfirmedNotification):
    """Уведомление об отметке на занятии (основной сценарий)"""
    if not notification_service:
        return {"error": "Service not initialized"}
    success = await notification_service.send_attendance_confirmed_notification(
        user_id=notification.user_id,
        lesson_name=notification.lesson_name,
        rewards=notification.rewards,
        rewards_status=notification.rewards_status,
        character=notification.character,
        streak=notification.streak,
        unlocked_sets=notification.unlocked_sets,
    )
    return {"success": success}


@app.post("/notifications/lesson-missed")
async def send_lesson_missed_notification(notification: LessonMissedNotification):
    """Уведомление о пропуске занятия с кнопкой «день без штрафа»"""
    if not notification_service:
        return {"error": "Service not initialized"}
    success = await notification_service.send_lesson_missed_notification(
        user_id=notification.user_id,
        miss_id=notification.miss_id,
        lesson_name=notification.lesson_name,
        freezes_available=notification.freezes_available,
        penalty=notification.penalty,
    )
    return {"success": success}



class GroupGoalNotification(BaseModel):
    chat_id: int
    group_name: str
    lesson_name: str
    attended: int
    expected: int
    percent: int
    bonus: dict = {}


class GameWeeklyResultsNotification(BaseModel):
    group_name: str
    chat_id: Optional[int] = None
    winners: List[dict] = []


class GroupSummaryNotification(BaseModel):
    chat_id: int
    group_name: str
    lesson_name: str
    attended: int
    expected: int
    percent: int
    target_percent: int = 80
    achieved: bool = False
    top_streaks: List[dict] = []


class GroupReminderNotification(BaseModel):
    chat_id: int
    group_name: str
    lesson_name: str
    location: Optional[str] = None
    minutes: int = 10
    target_percent: int = 80


class LessonReminderNotification(BaseModel):
    user_id: int
    lesson_name: str
    location: Optional[str] = None
    minutes: int = 10


class SupportRequestNotification(BaseModel):
    curator_user_ids: List[int]
    student_user_id: int
    student_name: str
    groups: List[str] = []
    message: Optional[str] = None


class UserOnlyNotification(BaseModel):
    user_id: int


class CuratorNudgeNotification(BaseModel):
    user_id: int
    curator_name: Optional[str] = None


class CuratorDigestNotification(BaseModel):
    curator_user_id: int
    groups: List[dict] = []


def _ready():
    return notification_service is not None


@app.post("/notifications/group-goal")
async def notify_group_goal(n: GroupGoalNotification):
    """Командная цель пары достигнута — сообщение в чат группы"""
    if not _ready():
        return {"error": "Service not initialized"}
    return {"success": await notification_service.send_group_goal(**n.model_dump())}


@app.post("/notifications/game-weekly-results")
async def notify_game_weekly_results(n: GameWeeklyResultsNotification):
    """Итоги недели мини-игры — призёрам и в чат группы"""
    if not _ready():
        return {"error": "Service not initialized"}
    return {"success": await notification_service.send_game_weekly_results(**n.model_dump())}


@app.post("/notifications/group-lesson-summary")
async def notify_group_summary(n: GroupSummaryNotification):
    """Итоги пары — в чат группы"""
    if not _ready():
        return {"error": "Service not initialized"}
    return {"success": await notification_service.send_group_lesson_summary(**n.model_dump())}


@app.post("/notifications/group-lesson-reminder")
async def notify_group_reminder(n: GroupReminderNotification):
    """Напоминание о паре — в чат группы"""
    if not _ready():
        return {"error": "Service not initialized"}
    return {"success": await notification_service.send_group_lesson_reminder(**n.model_dump())}


@app.post("/notifications/lesson-reminder")
async def notify_lesson_reminder(n: LessonReminderNotification):
    """Напоминание о паре — студенту"""
    if not _ready():
        return {"error": "Service not initialized"}
    return {"success": await notification_service.send_lesson_reminder(**n.model_dump())}


@app.post("/notifications/support-request")
async def notify_support_request(n: SupportRequestNotification):
    """Студент просит поддержки — кураторам группы"""
    if not _ready():
        return {"error": "Service not initialized"}
    return {"success": await notification_service.send_support_request(**n.model_dump())}


@app.post("/notifications/help-offer")
async def notify_help_offer(n: UserOnlyNotification):
    """Мягкое предложение поддержки при сигналах риска"""
    if not _ready():
        return {"error": "Service not initialized"}
    return {"success": await notification_service.send_help_offer(n.user_id)}


@app.post("/notifications/curator-nudge")
async def notify_curator_nudge(n: CuratorNudgeNotification):
    """«Написать студенту» из кабинета куратора"""
    if not _ready():
        return {"error": "Service not initialized"}
    return {"success": await notification_service.send_curator_nudge(n.user_id, n.curator_name)}


@app.post("/notifications/curator-digest")
async def notify_curator_digest(n: CuratorDigestNotification):
    """Еженедельная сводка куратору"""
    if not _ready():
        return {"error": "Service not initialized"}
    return {"success": await notification_service.send_curator_digest(n.curator_user_id, n.groups)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8020)

