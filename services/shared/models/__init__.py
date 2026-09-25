"""
Все модели базы данных
"""
from services.shared.models.user import User
from services.shared.models.character import Character, CharacterSnapshot
from services.shared.models.task import Task, TaskStatus, TaskPriority, Goal, GoalStatus, GoalTask
from services.shared.models.task_generation import TaskGeneration
from services.shared.models.habit import Habit, HabitLog, HabitFrequency
from services.shared.models.item import Item, UserItem, ItemRarity, ItemType, TradeRequest, TradeStatus
from services.shared.models.achievement import Achievement, UserAchievement
from services.shared.models.social import Clan, ClanMember, Friendship, StudentGroup, GroupMember, GroupInvitation, ClanRole, FriendshipStatus, GroupInvitationStatus, group_curators, Organization
from services.shared.models.event import Event, EventAttendance
from services.shared.models.lesson import Lesson, LessonAttendance, LessonMiss, LessonMissStatus, VerificationMethod, lesson_groups, LessonGroupGoal, SupportRequest
from services.shared.models.appearance import AppearanceSet, UserAppearanceUnlock, AppearanceKind, UnlockType
from services.shared.models.economy import ShopListing, Transaction, TransactionType
from services.shared.models.competition import Competition, CompetitionParticipant
from services.shared.models.minigame import GameRun, GameWeeklyPrize

__all__ = [
    "User",
    "Character", "CharacterSnapshot",
    "Task", "TaskStatus", "TaskPriority",
    "Goal", "GoalStatus", "GoalTask",
    "TaskGeneration",
    "Habit", "HabitLog", "HabitFrequency",
    "Item", "UserItem", "ItemRarity", "ItemType", "TradeRequest", "TradeStatus",
    "Achievement", "UserAchievement",
    "Clan", "ClanMember", "Friendship", "StudentGroup", "GroupMember", "GroupInvitation", "ClanRole", "FriendshipStatus", "GroupInvitationStatus", "group_curators", "Organization",
    "Event", "EventAttendance",
    "Lesson", "LessonAttendance", "LessonMiss", "LessonMissStatus", "VerificationMethod", "lesson_groups", "LessonGroupGoal", "SupportRequest",
    "AppearanceSet", "UserAppearanceUnlock", "AppearanceKind", "UnlockType",
    "ShopListing", "Transaction", "TransactionType",
    "Competition", "CompetitionParticipant",
    "GameRun", "GameWeeklyPrize",
]

