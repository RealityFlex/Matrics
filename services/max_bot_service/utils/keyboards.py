"""
Утилиты для создания inline-клавиатур
"""
from typing import List, Dict, Any, Optional

from services.max_bot_service import config


def open_app_button(text: str = "📱 Открыть Матрикс", start_param: str = "today") -> Optional[Dict[str, Any]]:
    """
    Кнопка открытия мини-приложения. По умолчанию — ссылка-диплинк
    https://max.ru/<бот>?startapp=<параметр> (проверенный формат MAX);
    при MAX_OPEN_APP_MODE=open_app — нативная кнопка open_app.
    """
    bot = config.MAX_BOT_USERNAME
    if config.MAX_OPEN_APP_MODE == "open_app" and bot:
        return {"type": "open_app", "text": text, "web_app": bot, "payload": start_param}
    if bot:
        return {"type": "link", "text": text, "url": f"https://max.ru/{bot}?startapp={start_param}"}
    if config.WEBAPP_URL:
        return {"type": "link", "text": text, "url": config.WEBAPP_URL}
    return None


def with_open_app_row(buttons: List[List[Dict[str, Any]]], text: str = "📱 Открыть Матрикс",
                      start_param: str = "today") -> List[List[Dict[str, Any]]]:
    button = open_app_button(text, start_param)
    return ([[button]] if button else []) + buttons


class KeyboardBuilder:
    """Построитель inline-клавиатур для MAX Bot"""

    def build_attendance_keyboard(self) -> Dict[str, Any]:
        """Клавиатура под уведомлением об отметке на занятии"""
        return {
            "type": "inline_keyboard",
            "payload": {
                "buttons": with_open_app_row([
                    [
                        {"type": "callback", "text": "🔥 Моя серия", "payload": "streak"},
                        {"type": "callback", "text": "🎮 Персонаж", "payload": "character"},
                    ],
                ], text="🎉 Посмотреть на персонажа"),
            },
        }

    def build_lesson_missed_keyboard(self, miss_id: int, freezes_available: int) -> Dict[str, Any]:
        """Клавиатура уведомления о пропуске: «день без штрафа»"""
        rows: List[List[Dict[str, Any]]] = []
        if freezes_available > 0:
            rows.append([{"type": "callback", "text": "🧊 Взять день без штрафа", "payload": f"streak_freeze:{miss_id}"}])
        rows.append([{"type": "callback", "text": "🔥 Моя серия", "payload": "streak"}])
        return {"type": "inline_keyboard", "payload": {"buttons": with_open_app_row(rows)}}

    def build_curator_keyboard(self) -> Dict[str, Any]:
        """Куратору: открыть кабинет «Мои группы» в мини-приложении"""
        return {"type": "inline_keyboard", "payload": {"buttons": with_open_app_row(
            [[{"type": "callback", "text": "🏠 Главное меню", "payload": "menu"}]],
            text="🎓 Открыть кабинет куратора", start_param="curator")}}

    def build_help_keyboard(self) -> Dict[str, Any]:
        """Мягкое предложение поддержки: связаться с куратором или ответить, что всё хорошо"""
        return {"type": "inline_keyboard", "payload": {"buttons": [
            [{"type": "callback", "text": "🤝 Написать куратору", "payload": "help_request"}],
            [{"type": "callback", "text": "👌 Всё хорошо", "payload": "help_ok"}],
        ]}}

    def build_reminder_keyboard(self) -> Dict[str, Any]:
        """Напоминание о паре: сразу открыть отметку"""
        return {"type": "inline_keyboard", "payload": {"buttons": with_open_app_row(
            [[{"type": "callback", "text": "🔥 Моя серия", "payload": "streak"}]],
            text="✅ Открыть и отметиться", start_param="checkin")}}

    def build_checkin_keyboard(self) -> Dict[str, Any]:
        """Подсказка, как отметиться"""
        return {
            "type": "inline_keyboard",
            "payload": {
                "buttons": with_open_app_row([
                    [{"type": "callback", "text": "🏠 Главное меню", "payload": "menu"}],
                ], text="📷 Отметиться через приложение", start_param="checkin"),
            },
        }
    
    def build_main_menu(self) -> Dict[str, Any]:
        """Создать главное меню"""
        return {
            "type": "inline_keyboard",
            "payload": {
                "buttons": with_open_app_row([
                    [
                        {
                            "type": "callback",
                            "text": "✅ Отметиться на паре",
                            "payload": "checkin_help"
                        },
                        {
                            "type": "callback",
                            "text": "🔥 Серия",
                            "payload": "streak"
                        }
                    ],
                    [
                        {
                            "type": "callback",
                            "text": "👤 Профиль",
                            "payload": "profile"
                        },
                        {
                            "type": "callback",
                            "text": "📋 Задачи",
                            "payload": "tasks"
                        }
                    ],
                    [
                        {
                            "type": "callback",
                            "text": "🎮 Персонаж",
                            "payload": "character"
                        },
                        {
                            "type": "callback",
                            "text": "📊 Статистика",
                            "payload": "stats"
                        }
                    ],
                    [
                        {
                            "type": "callback",
                            "text": "🎒 Инвентарь",
                            "payload": "inventory"
                        },
                        {
                            "type": "callback",
                            "text": "🏆 Достижения",
                            "payload": "achievements"
                        }
                    ],
                    [
                        {
                            "type": "callback",
                            "text": "🏠 Главное меню",
                            "payload": "menu"
                        }
                    ]
                ])
            }
        }
    
    def build_profile_menu(self) -> Dict[str, Any]:
        """Создать меню профиля"""
        return {
            "type": "inline_keyboard",
            "payload": {
                "buttons": [
                    [
                        {
                            "type": "callback",
                            "text": "📋 Задачи",
                            "payload": "tasks"
                        },
                        {
                            "type": "callback",
                            "text": "🎮 Персонаж",
                            "payload": "character"
                        }
                    ],
                    [
                        {
                            "type": "callback",
                            "text": "🏠 Главное меню",
                            "payload": "menu"
                        }
                    ]
                ]
            }
        }
    
    def build_tasks_menu(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Создать меню задач"""
        buttons = []
        
        # Фильтруем только невыполненные задачи
        active_tasks = [task for task in tasks if task.get("status", "todo") != "completed"]
        
        # Добавляем кнопки для каждой невыполненной задачи (максимум 5)
        for task in active_tasks[:5]:
            task_id = task.get("id")
            title = task.get("title", "Без названия")
            
            # Обрезаем длинные названия
            if len(title) > 25:
                title = title[:22] + "..."
            
            buttons.append([
                {
                    "type": "callback",
                    "text": f"⏳ {title}",
                    "payload": f"task_view:{task_id}"
                }
            ])
        
        # Кнопки управления
        buttons.append([
            {
                "type": "callback",
                "text": "➕ Создать задачу",
                "payload": "task_create"
            }
        ])
        buttons.append([
            {
                "type": "callback",
                "text": "🏠 Главное меню",
                "payload": "menu"
            }
        ])
        
        return {
            "type": "inline_keyboard",
            "payload": {
                "buttons": buttons
            }
        }
    
    def build_task_created_menu(self) -> Dict[str, Any]:
        """Создать меню после создания задачи"""
        return {
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
    
    def build_task_detail_menu(self, task_id: int) -> Dict[str, Any]:
        """Создать меню деталей задачи"""
        return {
            "type": "inline_keyboard",
            "payload": {
                "buttons": [
                    [
                        {
                            "type": "callback",
                            "text": "✅ Выполнить",
                            "payload": f"task_complete:{task_id}"
                        }
                    ],
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
    
    def build_character_menu(self) -> Dict[str, Any]:
        """Создать меню персонажа"""
        return {
            "type": "inline_keyboard",
            "payload": {
                "buttons": [
                    [
                        {
                            "type": "callback",
                            "text": "📋 Задачи",
                            "payload": "tasks"
                        },
                        {
                            "type": "callback",
                            "text": "📊 Статистика",
                            "payload": "stats"
                        }
                    ],
                    [
                        {
                            "type": "callback",
                            "text": "🏠 Главное меню",
                            "payload": "menu"
                        }
                    ]
                ]
            }
        }
    
    def build_stats_menu(self) -> Dict[str, Any]:
        """Создать меню статистики"""
        return {
            "type": "inline_keyboard",
            "payload": {
                "buttons": [
                    [
                        {
                            "type": "callback",
                            "text": "📋 Задачи",
                            "payload": "tasks"
                        },
                        {
                            "type": "callback",
                            "text": "🎮 Персонаж",
                            "payload": "character"
                        }
                    ],
                    [
                        {
                            "type": "callback",
                            "text": "🏠 Главное меню",
                            "payload": "menu"
                        }
                    ]
                ]
            }
        }
    
    def build_inventory_menu(self) -> Dict[str, Any]:
        """Создать меню инвентаря"""
        return {
            "type": "inline_keyboard",
            "payload": {
                "buttons": [
                    [
                        {
                            "type": "callback",
                            "text": "🏠 Главное меню",
                            "payload": "menu"
                        }
                    ]
                ]
            }
        }
    
    def build_achievements_menu(self) -> Dict[str, Any]:
        """Создать меню достижений"""
        return {
            "type": "inline_keyboard",
            "payload": {
                "buttons": [
                    [
                        {
                            "type": "callback",
                            "text": "🏠 Главное меню",
                            "payload": "menu"
                        }
                    ]
                ]
            }
        }
    
    def build_friend_request_keyboard(self, friendship_id: int) -> Dict[str, Any]:
        """Создать клавиатуру для запроса дружбы"""
        return {
            "type": "inline_keyboard",
            "payload": {
                "buttons": [
                    [
                        {
                            "type": "callback",
                            "text": "✅ Принять",
                            "payload": f"friend_accept:{friendship_id}"
                        },
                        {
                            "type": "callback",
                            "text": "❌ Отклонить",
                            "payload": f"friend_reject:{friendship_id}"
                        }
                    ],
                    [
                        {
                            "type": "callback",
                            "text": "🏠 Главное меню",
                            "payload": "menu"
                        }
                    ]
                ]
            }
        }
    
    def build_trade_request_keyboard(self, trade_id: int) -> Dict[str, Any]:
        """Создать клавиатуру для предложения обмена"""
        return {
            "type": "inline_keyboard",
            "payload": {
                "buttons": [
                    [
                        {
                            "type": "callback",
                            "text": "✅ Принять",
                            "payload": f"trade_accept:{trade_id}"
                        },
                        {
                            "type": "callback",
                            "text": "❌ Отклонить",
                            "payload": f"trade_reject:{trade_id}"
                        }
                    ],
                    [
                        {
                            "type": "callback",
                            "text": "🏠 Главное меню",
                            "payload": "menu"
                        }
                    ]
                ]
            }
        }
    
    def build_competition_keyboard(self, competition_id: int) -> Dict[str, Any]:
        """Создать клавиатуру для соревнования"""
        return {
            "type": "inline_keyboard",
            "payload": {
                "buttons": [
                    [
                        {
                            "type": "callback",
                            "text": "✅ Присоединиться",
                            "payload": f"competition_join:{competition_id}"
                        },
                        {
                            "type": "callback",
                            "text": "❌ Отказаться",
                            "payload": f"competition_decline:{competition_id}"
                        }
                    ],
                    [
                        {
                            "type": "callback",
                            "text": "🏠 Главное меню",
                            "payload": "menu"
                        }
                    ]
                ]
            }
        }
    
    def build_challenge_request_keyboard(self, challenge_id: int) -> Dict[str, Any]:
        """Создать клавиатуру для запроса челленджа"""
        return {
            "type": "inline_keyboard",
            "payload": {
                "buttons": [
                    [
                        {
                            "type": "callback",
                            "text": "✅ Принять",
                            "payload": f"challenge_accept:{challenge_id}"
                        },
                        {
                            "type": "callback",
                            "text": "❌ Отклонить",
                            "payload": f"challenge_reject:{challenge_id}"
                        }
                    ],
                    [
                        {
                            "type": "callback",
                            "text": "🏠 Главное меню",
                            "payload": "menu"
                        }
                    ]
                ]
            }
        }

    def build_group_invitation_keyboard(self, invitation_id: int) -> Dict[str, Any]:
        """Создать клавиатуру для приглашения в группу"""
        return {
            "type": "inline_keyboard",
            "payload": {
                "buttons": [
                    [
                        {
                            "type": "callback",
                            "text": "✅ Принять",
                            "payload": f"group_invitation_accept:{invitation_id}"
                        },
                        {
                            "type": "callback",
                            "text": "❌ Отклонить",
                            "payload": f"group_invitation_reject:{invitation_id}"
                        }
                    ],
                    [
                        {
                            "type": "callback",
                            "text": "🏠 Главное меню",
                            "payload": "menu"
                        }
                    ]
                ]
            }
        }
    
    def build_low_satisfaction_keyboard(self) -> Dict[str, Any]:
        """Создать клавиатуру для уведомления о низкой удовлетворённости"""
        return {
            "type": "inline_keyboard",
            "payload": {
                "buttons": [
                    [
                        {
                            "type": "callback",
                            "text": "📋 Задачи",
                            "payload": "tasks"
                        },
                        {
                            "type": "callback",
                            "text": "🎮 Персонаж",
                            "payload": "character"
                        }
                    ],
                    [
                        {
                            "type": "callback",
                            "text": "🏠 Главное меню",
                            "payload": "menu"
                        }
                    ]
                ]
            }
        }
    
    def build_habit_activated_keyboard(self) -> Dict[str, Any]:
        """Создать клавиатуру для уведомления об активации привычки"""
        return {
            "type": "inline_keyboard",
            "payload": {
                "buttons": [
                    [
                        {
                            "type": "callback",
                            "text": "📋 Задачи",
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
    
    def build_daily_reward_keyboard(self) -> Dict[str, Any]:
        """Создать клавиатуру для уведомления о ежедневном подарке"""
        return {
            "type": "inline_keyboard",
            "payload": {
                "buttons": [
                    [
                        {
                            "type": "callback",
                            "text": "🎮 Персонаж",
                            "payload": "character"
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