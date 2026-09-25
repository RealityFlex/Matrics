"""
Утилиты для форматирования сообщений
"""
from typing import Dict, Any, List, Optional
from datetime import datetime


class MessageFormatter:
    """Форматирование сообщений для MAX Bot"""
    
    def format_profile(self, user: Dict[str, Any], character: Optional[Dict[str, Any]]) -> str:
        """Форматировать профиль пользователя"""
        text = f"""*👤 Ваш профиль*

*Пользователь:*
• ID: `{user.get('id')}`
• Имя: {user.get('username', 'Не указано')}
• Монеты: 💰 {user.get('coins', 0)}"""
        
        if character:
            rating = character.get('rating', 0)
            satisfaction = character.get('satisfaction', 50)
            intelligence_level = character.get('intelligence_level', 1)
            
            text += f"""

*Персонаж:*
• Имя: {character.get('name', 'Не указано')}
• Удовлетворение: {satisfaction}/100 {self._get_satisfaction_emoji(satisfaction)}
• Уровень интеллекта: {intelligence_level} 🧠
• Рейтинг: {rating:.1f} ⭐"""
        else:
            text += "\n\n*Персонаж:* Не создан"
        
        return text
    
    def format_character(self, character: Optional[Dict[str, Any]]) -> str:
        """Форматировать информацию о персонаже"""
        if not character:
            return "*🎮 Ваш персонаж*\n\nПерсонаж не создан. Обратитесь к администратору."
        
        name = character.get('name', 'Не указано')
        satisfaction = character.get('satisfaction', 50)
        intelligence_level = character.get('intelligence_level', 1)
        intelligence_points = character.get('intelligence_points', 0)
        bonus_points = character.get('bonus_points', 0)
        rating = character.get('rating', 0)
        
        # Вычисляем прогресс до следующего уровня
        points_needed = intelligence_level * 100
        progress = (intelligence_points / points_needed * 100) if points_needed > 0 else 0
        
        text = f"""*🎮 Ваш персонаж*

*Имя:* {name}

*Параметры:*
• Удовлетворение: {satisfaction}/100 {self._get_satisfaction_emoji(satisfaction)}
• Уровень интеллекта: {intelligence_level} 🧠
• Очки интеллекта: {intelligence_points}/{points_needed} ({progress:.1f}%)
• Бонусные очки: {bonus_points} ⭐

*Рейтинг:* {rating:.1f} ⭐"""

        extras = []
        if character.get("mood_label"):
            extras.append(f"• Настроение: {character['mood_label']}")
        if character.get("growth_stage_label"):
            extras.append(f"• Стадия роста: {character['growth_stage_label']}")
        look = (character.get("active_character_set") or {}).get("name")
        place = (character.get("active_environment_set") or {}).get("name")
        if look:
            extras.append(f"• Образ: {look}")
        if place:
            extras.append(f"• Локация: {place}")
        if extras:
            text += "\n\n*Сейчас:*\n" + "\n".join(extras)
        return text
    
    def format_tasks_list(self, tasks: List[Dict[str, Any]]) -> str:
        """Форматировать список задач"""
        if not tasks:
            return "*📋 Ваши задачи*\n\nЗадач пока нет. Создайте первую задачу!"
        
        text = f"*📋 Ваши задачи*\n\n*Всего задач: {len(tasks)}*\n\n"
        
        # Группируем по статусам
        todo_tasks = [t for t in tasks if t.get('status') == 'todo']
        in_progress_tasks = [t for t in tasks if t.get('status') == 'in_progress']
        completed_tasks = [t for t in tasks if t.get('status') == 'completed']
        
        if todo_tasks:
            text += f"*⏳ К выполнению ({len(todo_tasks)}):*\n"
            for task in todo_tasks[:5]:
                title = task.get('title', 'Без названия')
                priority = task.get('priority', 'medium')
                text += f"• {self._get_priority_emoji(priority)} {title}\n"
            text += "\n"
        
        if in_progress_tasks:
            text += f"*🔄 В процессе ({len(in_progress_tasks)}):*\n"
            for task in in_progress_tasks[:5]:
                title = task.get('title', 'Без названия')
                text += f"• {title}\n"
            text += "\n"
        
        if completed_tasks:
            text += f"*✅ Выполнено ({len(completed_tasks)}):*\n"
            for task in completed_tasks[:5]:
                title = task.get('title', 'Без названия')
                text += f"• {title}\n"
        
        if len(tasks) > 5:
            text += f"\n_Показано 5 из {len(tasks)} задач_"
        
        return text
    
    def format_task_detail(self, task: Dict[str, Any]) -> str:
        """Форматировать детали задачи"""
        title = task.get('title', 'Без названия')
        description = task.get('description', 'Нет описания')
        status = task.get('status', 'todo')
        priority = task.get('priority', 'medium')
        due_date = task.get('due_date')
        reward_coins = task.get('reward_coins', 0)
        reward_intelligence = task.get('reward_intelligence_points', 0)
        
        text = f"""*📋 Задача: {title}*

*Статус:* {self._get_status_text(status)}
*Приоритет:* {self._get_priority_text(priority)}

*Описание:*
{description}

*Награды за выполнение:*
• Монеты: 💰 {reward_coins}
• Очки интеллекта: 🧠 {reward_intelligence}"""
        
        if due_date:
            try:
                due = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
                text += f"\n\n*Срок выполнения:* {due.strftime('%d.%m.%Y %H:%M')}"
            except:
                pass
        
        return text
    
    def format_stats(self, stats: Dict[str, Any]) -> str:
        """Форматировать статистику"""
        total = stats.get('total', 0)
        completed = stats.get('completed', 0)
        in_progress = stats.get('in_progress', 0)
        todo = stats.get('todo', 0)
        completion_rate = stats.get('completion_rate', 0)
        
        by_priority = stats.get('by_priority', {})
        
        text = f"""*📊 Статистика*

*Задачи:*
• Всего: {total}
• Выполнено: ✅ {completed}
• В процессе: 🔄 {in_progress}
• К выполнению: ⏳ {todo}

*Процент выполнения:* {completion_rate}%

*По приоритетам:*
• 🔴 Срочные: {by_priority.get('urgent', 0)}
• 🟠 Высокие: {by_priority.get('high', 0)}
• 🟡 Средние: {by_priority.get('medium', 0)}
• 🟢 Низкие: {by_priority.get('low', 0)}"""
        
        return text
    
    def format_inventory(self, inventory: Dict[str, Any]) -> str:
        """Форматировать инвентарь"""
        items = inventory.get('items', [])
        
        if not items:
            return "*🎒 Ваш инвентарь*\n\nИнвентарь пуст."
        
        # Группируем предметы по item_id и суммируем quantity
        grouped_items = {}
        for item_data in items:
            if isinstance(item_data, dict):
                if 'item' in item_data:
                    # Формат UserItemResponse с вложенным item
                    item = item_data.get('item', {})
                    item_id = item.get('id') or item_data.get('item_id')
                    item_name = item.get('name', 'Неизвестный предмет')
                    quantity = item_data.get('quantity', 1)
                else:
                    # Прямой формат
                    item_id = item_data.get('item_id') or item_data.get('id')
                    item_name = item_data.get('name') or item_data.get('item_name', 'Неизвестный предмет')
                    quantity = item_data.get('quantity', 1)
                
                # Группируем по item_id
                if item_id:
                    if item_id not in grouped_items:
                        grouped_items[item_id] = {
                            'name': item_name,
                            'quantity': 0
                        }
                    grouped_items[item_id]['quantity'] += quantity
        
        # Преобразуем в список для сортировки
        grouped_list = list(grouped_items.values())
        total_items = len(grouped_list)
        
        text = f"*🎒 Ваш инвентарь*\n\n*Предметов: {total_items}*\n\n"
        
        # Выводим первые 10 сгруппированных предметов
        for item_info in grouped_list[:10]:
            text += f"• {item_info['name']} x{item_info['quantity']}\n"
        
        if total_items > 10:
            text += f"\n_Показано 10 из {total_items} предметов_"
        
        return text
    
    def format_achievements(self, achievements: Dict[str, Any]) -> str:
        """Форматировать достижения"""
        achievements_list = achievements.get('achievements', [])
        
        if not achievements_list:
            return "*🏆 Ваши достижения*\n\nДостижений пока нет."
        
        text = f"*🏆 Ваши достижения*\n\n*Всего: {len(achievements_list)}*\n\n"
        
        for achievement_data in achievements_list[:10]:
            # Может быть либо прямой объект, либо вложенный achievement
            if isinstance(achievement_data, dict):
                if 'achievement' in achievement_data:
                    # Формат UserAchievementResponse с вложенным achievement
                    achievement = achievement_data.get('achievement', {})
                    name = achievement.get('name', 'Неизвестное достижение')
                    description = achievement.get('description', '')
                    requirement_value = achievement.get('requirement_value', 0)
                    completed = achievement_data.get('completed', False)
                    completed_at = achievement_data.get('completed_at')
                    progress = achievement_data.get('progress', 0)
                else:
                    # Прямой формат
                    name = achievement_data.get('name', 'Неизвестное достижение')
                    description = achievement_data.get('description', '')
                    requirement_value = achievement_data.get('requirement_value', 0)
                    completed = achievement_data.get('completed', False)
                    completed_at = achievement_data.get('completed_at')
                    progress = achievement_data.get('progress', 0)
                
                # Достижение считается завершенным, если:
                # 1. completed=True
                # 2. есть completed_at
                # 3. прогресс >= requirement_value (защита от рассинхронизации данных)
                is_completed = completed or bool(completed_at) or (requirement_value > 0 and progress >= requirement_value)
                
                # Для завершенных достижений показываем галочку, для остальных - прогресс
                if is_completed:
                    status_icon = "✅"
                else:
                    # Вычисляем процент прогресса
                    if requirement_value > 0:
                        progress_percent = min(100, int((progress / requirement_value) * 100))
                        status_icon = f"⏳ {progress_percent}%"
                    else:
                        status_icon = f"⏳ {progress}"
                
                text += f"• {status_icon} *{name}*\n"
                if description:
                    text += f"  _{description}_\n"
        
        if len(achievements_list) > 10:
            text += f"\n_Показано 10 из {len(achievements_list)} достижений_"
        
        return text
    
    def _get_satisfaction_emoji(self, satisfaction: int) -> str:
        """Получить эмодзи для уровня удовлетворения"""
        if satisfaction >= 80:
            return "😄"
        elif satisfaction >= 60:
            return "🙂"
        elif satisfaction >= 40:
            return "😐"
        elif satisfaction >= 20:
            return "😕"
        else:
            return "😢"
    
    def _get_priority_emoji(self, priority: str) -> str:
        """Получить эмодзи для приоритета"""
        priority_map = {
            "urgent": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🟢"
        }
        return priority_map.get(priority, "🟡")
    
    def _get_priority_text(self, priority: str) -> str:
        """Получить текст приоритета"""
        priority_map = {
            "urgent": "🔴 Срочный",
            "high": "🟠 Высокий",
            "medium": "🟡 Средний",
            "low": "🟢 Низкий"
        }
        return priority_map.get(priority, "🟡 Средний")
    
    def _get_status_text(self, status: str) -> str:
        """Получить текст статуса"""
        status_map = {
            "todo": "⏳ К выполнению",
            "in_progress": "🔄 В процессе",
            "completed": "✅ Выполнено",
            "cancelled": "❌ Отменено"
        }
        return status_map.get(status, "⏳ К выполнению")
    
    def format_friend_request_notification(
        self,
        initiator_username: str,
        friendship_id: int
    ) -> str:
        """Форматировать уведомление о запросе дружбы"""
        return f"""👥 *Новый запрос дружбы*

{initiator_username} хочет добавить вас в друзья.

Выберите действие:"""
    
    def format_trade_request_notification(
        self,
        initiator_username: str,
        trade_id: int,
        initiator_item_name: Optional[str] = None,
        requested_item_name: Optional[str] = None,
        initiator_quantity: int = 1,
        requested_quantity: int = 1
    ) -> str:
        """Форматировать уведомление о предложении обмена"""
        text = f"""🤝 *Новое предложение обмена*

{initiator_username} предлагает обмен:
"""
        
        if initiator_item_name:
            text += f"• Отдает: {initiator_item_name} x{initiator_quantity}\n"
        else:
            text += f"• Отдает: подарок\n"
        
        if requested_item_name:
            text += f"• Просит: {requested_item_name} x{requested_quantity}\n"
        else:
            text += "• Просит: ничего (подарок)\n"
        
        text += "\nВыберите действие:"
        
        return text
    
    def format_shop_purchase_notification(
        self,
        buyer_username: str,
        item_name: str,
        quantity: int,
        total_price: int
    ) -> str:
        """Форматировать уведомление о покупке товара"""
        return f"""💰 *Ваш товар куплен!*

{buyer_username} купил(а) ваш товар:
• {item_name} x{quantity}
• Сумма: 💰 {total_price} монет

Средства зачислены на ваш счет."""
    
    def format_competition_created_notification(
        self,
        competition_name: str,
        competition_id: int,
        description: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None
    ) -> str:
        """Форматировать уведомление о создании нового соревнования"""
        text = f"""🏆 *Новое соревнование!*

*{competition_name}*

"""
        if description:
            text += f"{description}\n\n"
        
        if start_time:
            text += f"• Начало: {start_time}\n"
        if end_time:
            text += f"• Окончание: {end_time}\n"
        
        text += "\nПрисоединяйтесь к соревнованию!"
        
        return text
    
    def format_competition_finished_notification(
        self,
        competition_name: str,
        rank: Optional[int] = None,
        reward_coins: int = 0
    ) -> str:
        """Форматировать уведомление о завершении соревнования"""
        text = f"""🏆 *Соревнование завершено!*

*{competition_name}*

"""
        if rank:
            if rank == 1:
                text += "🥇 *1 место!* Поздравляем!\n\n"
            elif rank == 2:
                text += "🥈 *2 место!* Отличный результат!\n\n"
            elif rank == 3:
                text += "🥉 *3 место!* Хорошая работа!\n\n"
            else:
                text += f"*Место: {rank}*\n\n"
        else:
            text += "Соревнование завершено.\n\n"
        
        if reward_coins > 0:
            text += f"💰 *Награда: {reward_coins} монет*"
        else:
            text += "Спасибо за участие!"
        
        return text
    
    def format_challenge_request_notification(
        self,
        initiator_username: str,
        challenge_id: int,
        metric_type: Optional[str] = None,
        target_value: int = 0,
        deadline: Optional[str] = None,
        reward_coins: int = 0
    ) -> str:
        """Форматировать уведомление о запросе челленджа"""
        text = f"""🏆 *Новый челлендж!*

{initiator_username} бросил(а) вам вызов!

"""
        if metric_type:
            text += f"• Метрика: {metric_type}\n"
        if target_value:
            text += f"• Цель: {target_value}\n"
        if deadline:
            text += f"• Дедлайн: {deadline}\n"
        if reward_coins:
            text += f"• Награда: 💰 {reward_coins} монет\n"
        
        text += "\nВыберите действие:"
        
        return text

