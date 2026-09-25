"""
Сервис для отправки уведомлений в чат-боте
"""
import logging
from typing import Optional, Dict, Any, List
from services.max_bot_service.max_api_client import MaxApiClient
from services.max_bot_service.utils.user_mapping import get_max_user_id
from services.max_bot_service.utils.keyboards import KeyboardBuilder
from services.max_bot_service.utils.formatters import MessageFormatter

logger = logging.getLogger(__name__)


class NotificationService:
    """Сервис для отправки уведомлений в чат-боте"""
    
    def __init__(self, api_client: MaxApiClient):
        self.api_client = api_client
        self.keyboard_builder = KeyboardBuilder()
        self.formatter = MessageFormatter()
    
    async def send_friend_request_notification(
        self,
        recipient_user_id: int,
        initiator_user_id: int,
        friendship_id: int,
        initiator_username: Optional[str] = None
    ) -> bool:
        """
        Отправить уведомление о запросе дружбы
        
        Args:
            recipient_user_id: Внутренний ID получателя запроса
            initiator_user_id: Внутренний ID инициатора запроса
            friendship_id: ID запроса дружбы
            initiator_username: Имя инициатора (опционально)
            
        Returns:
            True если уведомление отправлено, False в противном случае
        """
        try:
            max_user_id = await get_max_user_id(recipient_user_id)
            if not max_user_id:
                logger.debug(f"Пользователь {recipient_user_id} не зарегистрирован в MAX боте")
                return False
            
            # Получаем имя инициатора, если не указано
            if not initiator_username:
                from services.shared.utils import ServiceClient
                user_service = ServiceClient("user")
                try:
                    initiator = await user_service.get(f"/users/{initiator_user_id}")
                    initiator_username = initiator.get("username", "Пользователь")
                except:
                    initiator_username = "Пользователь"
                finally:
                    await user_service.close()
            
            text = self.formatter.format_friend_request_notification(
                initiator_username=initiator_username,
                friendship_id=friendship_id
            )
            
            keyboard = self.keyboard_builder.build_friend_request_keyboard(friendship_id)
            
            await self.api_client.send_message(
                user_id=max_user_id,
                text=text,
                attachments=[keyboard],
                format="markdown"
            )
            
            logger.info(f"Уведомление о запросе дружбы отправлено пользователю {recipient_user_id} (max_user_id={max_user_id})")
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления о запросе дружбы: {e}", exc_info=True)
            return False
    
    async def send_friend_request_accepted_notification(
        self,
        initiator_user_id: int,
        acceptor_username: Optional[str] = None
    ) -> bool:
        """
        Отправить уведомление о принятии запроса дружбы
        
        Args:
            initiator_user_id: Внутренний ID инициатора запроса
            acceptor_username: Имя принявшего запрос (опционально)
            
        Returns:
            True если уведомление отправлено, False в противном случае
        """
        try:
            max_user_id = await get_max_user_id(initiator_user_id)
            if not max_user_id:
                logger.debug(f"Пользователь {initiator_user_id} не зарегистрирован в MAX боте")
                return False
            
            if not acceptor_username:
                acceptor_username = "Пользователь"
            
            text = f"✅ *Запрос дружбы принят!*\n\n{acceptor_username} принял(а) ваш запрос на дружбу. 👥"
            
            keyboard = self.keyboard_builder.build_main_menu()
            
            await self.api_client.send_message(
                user_id=max_user_id,
                text=text,
                attachments=[keyboard],
                format="markdown"
            )
            
            logger.info(f"Уведомление о принятии запроса дружбы отправлено пользователю {initiator_user_id} (max_user_id={max_user_id})")
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления о принятии запроса дружбы: {e}", exc_info=True)
            return False
    
    async def send_trade_request_notification(
        self,
        recipient_user_id: int,
        initiator_user_id: int,
        trade_id: int,
        initiator_username: Optional[str] = None,
        initiator_item_name: Optional[str] = None,
        requested_item_name: Optional[str] = None,
        initiator_quantity: int = 1,
        requested_quantity: int = 1
    ) -> bool:
        """
        Отправить уведомление о предложении обмена
        
        Args:
            recipient_user_id: Внутренний ID получателя предложения
            initiator_user_id: Внутренний ID инициатора обмена
            trade_id: ID запроса на обмен
            initiator_username: Имя инициатора (опционально)
            initiator_item_name: Название предмета инициатора (опционально)
            requested_item_name: Название запрашиваемого предмета (опционально)
            initiator_quantity: Количество предметов инициатора
            requested_quantity: Количество запрашиваемых предметов
            
        Returns:
            True если уведомление отправлено, False в противном случае
        """
        try:
            max_user_id = await get_max_user_id(recipient_user_id)
            if not max_user_id:
                logger.debug(f"Пользователь {recipient_user_id} не зарегистрирован в MAX боте")
                return False
            
            # Получаем информацию об инициаторе и предметах, если не указано
            if not initiator_username:
                from services.shared.utils import ServiceClient
                user_service = ServiceClient("user")
                try:
                    initiator = await user_service.get(f"/users/{initiator_user_id}")
                    initiator_username = initiator.get("username", "Пользователь")
                except:
                    initiator_username = "Пользователь"
                finally:
                    await user_service.close()
            
            text = self.formatter.format_trade_request_notification(
                initiator_username=initiator_username,
                trade_id=trade_id,
                initiator_item_name=initiator_item_name,
                requested_item_name=requested_item_name,
                initiator_quantity=initiator_quantity,
                requested_quantity=requested_quantity
            )
            
            keyboard = self.keyboard_builder.build_trade_request_keyboard(trade_id)
            
            await self.api_client.send_message(
                user_id=max_user_id,
                text=text,
                attachments=[keyboard],
                format="markdown"
            )
            
            logger.info(f"Уведомление о предложении обмена отправлено пользователю {recipient_user_id} (max_user_id={max_user_id})")
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления о предложении обмена: {e}", exc_info=True)
            return False
    
    async def send_trade_request_accepted_notification(
        self,
        initiator_user_id: int,
        acceptor_username: Optional[str] = None
    ) -> bool:
        """
        Отправить уведомление о принятии предложения обмена
        
        Args:
            initiator_user_id: Внутренний ID инициатора обмена
            acceptor_username: Имя принявшего предложение (опционально)
            
        Returns:
            True если уведомление отправлено, False в противном случае
        """
        try:
            max_user_id = await get_max_user_id(initiator_user_id)
            if not max_user_id:
                logger.debug(f"Пользователь {initiator_user_id} не зарегистрирован в MAX боте")
                return False
            
            if not acceptor_username:
                acceptor_username = "Пользователь"
            
            text = f"✅ *Обмен принят!*\n\n{acceptor_username} принял(а) ваше предложение обмена. 🤝"
            
            keyboard = self.keyboard_builder.build_main_menu()
            
            await self.api_client.send_message(
                user_id=max_user_id,
                text=text,
                attachments=[keyboard],
                format="markdown"
            )
            
            logger.info(f"Уведомление о принятии обмена отправлено пользователю {initiator_user_id} (max_user_id={max_user_id})")
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления о принятии обмена: {e}", exc_info=True)
            return False
    
    async def send_trade_request_rejected_notification(
        self,
        initiator_user_id: int,
        rejector_username: Optional[str] = None
    ) -> bool:
        """
        Отправить уведомление об отклонении предложения обмена
        
        Args:
            initiator_user_id: Внутренний ID инициатора обмена
            rejector_username: Имя отклонившего предложение (опционально)
            
        Returns:
            True если уведомление отправлено, False в противном случае
        """
        try:
            max_user_id = await get_max_user_id(initiator_user_id)
            if not max_user_id:
                logger.debug(f"Пользователь {initiator_user_id} не зарегистрирован в MAX боте")
                return False
            
            if not rejector_username:
                rejector_username = "Пользователь"
            
            text = f"❌ *Обмен отклонен*\n\n{rejector_username} отклонил(а) ваше предложение обмена."
            
            keyboard = self.keyboard_builder.build_main_menu()
            
            await self.api_client.send_message(
                user_id=max_user_id,
                text=text,
                attachments=[keyboard],
                format="markdown"
            )
            
            logger.info(f"Уведомление об отклонении обмена отправлено пользователю {initiator_user_id} (max_user_id={max_user_id})")
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления об отклонении обмена: {e}", exc_info=True)
            return False
    
    async def send_shop_purchase_notification(
        self,
        seller_user_id: int,
        buyer_username: Optional[str] = None,
        item_name: Optional[str] = None,
        quantity: int = 1,
        total_price: int = 0
    ) -> bool:
        """
        Отправить уведомление о покупке товара продавцу
        
        Args:
            seller_user_id: Внутренний ID продавца
            buyer_username: Имя покупателя (опционально)
            item_name: Название проданного предмета (опционально)
            quantity: Количество проданных предметов
            total_price: Общая стоимость покупки
            
        Returns:
            True если уведомление отправлено, False в противном случае
        """
        try:
            max_user_id = await get_max_user_id(seller_user_id)
            if not max_user_id:
                logger.debug(f"Пользователь {seller_user_id} не зарегистрирован в MAX боте")
                return False
            
            if not buyer_username:
                buyer_username = "Пользователь"
            
            if not item_name:
                item_name = "предмет"
            
            text = self.formatter.format_shop_purchase_notification(
                buyer_username=buyer_username,
                item_name=item_name,
                quantity=quantity,
                total_price=total_price
            )
            
            keyboard = self.keyboard_builder.build_main_menu()
            
            await self.api_client.send_message(
                user_id=max_user_id,
                text=text,
                attachments=[keyboard],
                format="markdown"
            )
            
            logger.info(f"Уведомление о покупке товара отправлено продавцу {seller_user_id} (max_user_id={max_user_id})")
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления о покупке товара: {e}", exc_info=True)
            return False
    
    async def send_competition_created_notification(
        self,
        user_ids: List[int],
        competition_name: str,
        competition_id: int,
        description: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None
    ) -> int:
        """
        Отправить уведомление о создании нового соревнования
        
        Args:
            user_ids: Список внутренних ID пользователей для уведомления
            competition_name: Название соревнования
            competition_id: ID соревнования
            description: Описание соревнования (опционально)
            start_time: Время начала (опционально)
            end_time: Время окончания (опционально)
            
        Returns:
            Количество успешно отправленных уведомлений
        """
        sent_count = 0
        for user_id in user_ids:
            try:
                max_user_id = await get_max_user_id(user_id)
                if not max_user_id:
                    continue
                
                text = self.formatter.format_competition_created_notification(
                    competition_name=competition_name,
                    competition_id=competition_id,
                    description=description,
                    start_time=start_time,
                    end_time=end_time
                )
                
                keyboard = self.keyboard_builder.build_competition_keyboard(competition_id)
                
                await self.api_client.send_message(
                    user_id=max_user_id,
                    text=text,
                    attachments=[keyboard],
                    format="markdown"
                )
                sent_count += 1
            except Exception as e:
                logger.warning(f"Не удалось отправить уведомление о соревновании пользователю {user_id}: {e}")
        
        logger.info(f"Отправлено {sent_count} уведомлений о создании соревнования {competition_id}")
        return sent_count
    
    async def send_competition_finished_notification(
        self,
        user_id: int,
        competition_name: str,
        rank: Optional[int] = None,
        reward_coins: int = 0
    ) -> bool:
        """
        Отправить уведомление о завершении соревнования и результатах
        
        Args:
            user_id: Внутренний ID пользователя
            competition_name: Название соревнования
            rank: Место пользователя (опционально)
            reward_coins: Количество полученных монет
            
        Returns:
            True если уведомление отправлено, False в противном случае
        """
        try:
            max_user_id = await get_max_user_id(user_id)
            if not max_user_id:
                logger.debug(f"Пользователь {user_id} не зарегистрирован в MAX боте")
                return False
            
            text = self.formatter.format_competition_finished_notification(
                competition_name=competition_name,
                rank=rank,
                reward_coins=reward_coins
            )
            
            keyboard = self.keyboard_builder.build_main_menu()
            
            await self.api_client.send_message(
                user_id=max_user_id,
                text=text,
                attachments=[keyboard],
                format="markdown"
            )
            
            logger.info(f"Уведомление о завершении соревнования отправлено пользователю {user_id} (max_user_id={max_user_id})")
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления о завершении соревнования: {e}", exc_info=True)
            return False
    
    async def send_challenge_request_notification(
        self,
        recipient_user_id: int,
        initiator_user_id: int,
        challenge_id: int,
        initiator_username: Optional[str] = None,
        metric_type: Optional[str] = None,
        target_value: int = 0,
        deadline: Optional[str] = None,
        reward_coins: int = 0
    ) -> bool:
        """
        Отправить уведомление о запросе челленджа
        
        Args:
            recipient_user_id: Внутренний ID получателя запроса
            initiator_user_id: Внутренний ID инициатора челленджа
            challenge_id: ID челленджа
            initiator_username: Имя инициатора (опционально)
            metric_type: Тип метрики (опционально)
            target_value: Целевое значение
            deadline: Дедлайн (опционально)
            reward_coins: Награда в монетах
            
        Returns:
            True если уведомление отправлено, False в противном случае
        """
        try:
            max_user_id = await get_max_user_id(recipient_user_id)
            if not max_user_id:
                logger.debug(f"Пользователь {recipient_user_id} не зарегистрирован в MAX боте")
                return False
            
            # Получаем имя инициатора, если не указано
            if not initiator_username:
                from services.shared.utils import ServiceClient
                user_service = ServiceClient("user")
                try:
                    initiator = await user_service.get(f"/users/{initiator_user_id}")
                    initiator_username = initiator.get("username", "Пользователь")
                except:
                    initiator_username = "Пользователь"
                finally:
                    await user_service.close()
            
            text = self.formatter.format_challenge_request_notification(
                initiator_username=initiator_username,
                challenge_id=challenge_id,
                metric_type=metric_type,
                target_value=target_value,
                deadline=deadline,
                reward_coins=reward_coins
            )
            
            keyboard = self.keyboard_builder.build_challenge_request_keyboard(challenge_id)
            
            await self.api_client.send_message(
                user_id=max_user_id,
                text=text,
                attachments=[keyboard],
                format="markdown"
            )
            
            logger.info(f"Уведомление о запросе челленджа отправлено пользователю {recipient_user_id} (max_user_id={max_user_id})")
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления о запросе челленджа: {e}", exc_info=True)
            return False
    
    async def send_challenge_accepted_notification(
        self,
        initiator_user_id: int,
        acceptor_username: Optional[str] = None
    ) -> bool:
        """
        Отправить уведомление о принятии челленджа
        
        Args:
            initiator_user_id: Внутренний ID инициатора челленджа
            acceptor_username: Имя принявшего челлендж (опционально)
            
        Returns:
            True если уведомление отправлено, False в противном случае
        """
        try:
            max_user_id = await get_max_user_id(initiator_user_id)
            if not max_user_id:
                logger.debug(f"Пользователь {initiator_user_id} не зарегистрирован в MAX боте")
                return False
            
            if not acceptor_username:
                acceptor_username = "Пользователь"
            
            text = f"✅ *Челлендж принят!*\n\n{acceptor_username} принял(а) ваш челлендж. 🏆"
            
            keyboard = self.keyboard_builder.build_main_menu()
            
            await self.api_client.send_message(
                user_id=max_user_id,
                text=text,
                attachments=[keyboard],
                format="markdown"
            )
            
            logger.info(f"Уведомление о принятии челленджа отправлено пользователю {initiator_user_id} (max_user_id={max_user_id})")
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления о принятии челленджа: {e}", exc_info=True)
            return False
    
    async def send_challenge_rejected_notification(
        self,
        initiator_user_id: int,
        rejector_username: Optional[str] = None
    ) -> bool:
        """
        Отправить уведомление об отклонении челленджа
        
        Args:
            initiator_user_id: Внутренний ID инициатора челленджа
            rejector_username: Имя отклонившего челлендж (опционально)
            
        Returns:
            True если уведомление отправлено, False в противном случае
        """
        try:
            max_user_id = await get_max_user_id(initiator_user_id)
            if not max_user_id:
                logger.debug(f"Пользователь {initiator_user_id} не зарегистрирован в MAX боте")
                return False
            
            if not rejector_username:
                rejector_username = "Пользователь"
            
            text = f"❌ *Челлендж отклонен*\n\n{rejector_username} отклонил(а) ваш челлендж."
            
            keyboard = self.keyboard_builder.build_main_menu()
            
            await self.api_client.send_message(
                user_id=max_user_id,
                text=text,
                attachments=[keyboard],
                format="markdown"
            )
            
            logger.info(f"Уведомление об отклонении челленджа отправлено пользователю {initiator_user_id} (max_user_id={max_user_id})")
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления об отклонении челленджа: {e}", exc_info=True)
            return False
    
    async def send_challenge_completed_notification(
        self,
        winner_user_id: int,
        loser_user_id: int,
        challenge_id: int,
        winner_name: Optional[str] = None,
        loser_name: Optional[str] = None,
        reward_coins: int = 0
    ) -> bool:
        """
        Отправить уведомление о завершении челленджа
        
        Args:
            winner_user_id: Внутренний ID победителя
            loser_user_id: Внутренний ID проигравшего
            challenge_id: ID челленджа
            winner_name: Имя победителя (опционально)
            loser_name: Имя проигравшего (опционально)
            reward_coins: Награда в монетах
            
        Returns:
            True если уведомления отправлены, False в противном случае
        """
        try:
            # Отправляем уведомление победителю
            winner_max_user_id = await get_max_user_id(winner_user_id)
            if winner_max_user_id:
                if not winner_name:
                    from services.shared.utils import ServiceClient
                    user_service = ServiceClient("user")
                    try:
                        winner = await user_service.get(f"/users/{winner_user_id}")
                        winner_name = winner.get("username", "Победитель")
                    except:
                        winner_name = "Победитель"
                    finally:
                        await user_service.close()
                
                text = f"""🏆 *Челлендж завершен!*

Вы победили! 🎉

"""
                if loser_name:
                    text += f"Ваш оппонент: {loser_name}\n"
                if reward_coins > 0:
                    text += f"\n💰 *Награда: {reward_coins} монет*"
                
                keyboard = self.keyboard_builder.build_main_menu()
                
                await self.api_client.send_message(
                    user_id=winner_max_user_id,
                    text=text,
                    attachments=[keyboard],
                    format="markdown"
                )
                logger.info(f"Уведомление о победе в челлендже отправлено пользователю {winner_user_id} (max_user_id={winner_max_user_id})")
            
            # Отправляем уведомление проигравшему
            loser_max_user_id = await get_max_user_id(loser_user_id)
            if loser_max_user_id:
                if not loser_name:
                    from services.shared.utils import ServiceClient
                    user_service = ServiceClient("user")
                    try:
                        loser = await user_service.get(f"/users/{loser_user_id}")
                        loser_name = loser.get("username", "Оппонент")
                    except:
                        loser_name = "Оппонент"
                    finally:
                        await user_service.close()
                
                text = f"""🏆 *Челлендж завершен*

Челлендж завершен. К сожалению, вы не победили.

"""
                if winner_name:
                    text += f"Победитель: {winner_name}\n"
                text += "\nНе расстраивайтесь, попробуйте еще раз! 💪"
                
                keyboard = self.keyboard_builder.build_main_menu()
                
                await self.api_client.send_message(
                    user_id=loser_max_user_id,
                    text=text,
                    attachments=[keyboard],
                    format="markdown"
                )
                logger.info(f"Уведомление о завершении челленджа отправлено пользователю {loser_user_id} (max_user_id={loser_max_user_id})")
            
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления о завершении челленджа: {e}", exc_info=True)
            return False
    
    async def send_group_invitation_notification(
        self,
        recipient_user_id: int,
        inviter_user_id: int,
        group_id: int,
        group_name: str,
        invitation_id: int,
        inviter_username: Optional[str] = None
    ) -> bool:
        """
        Отправить уведомление о приглашении в группу
        
        Args:
            recipient_user_id: Внутренний ID получателя приглашения
            inviter_user_id: Внутренний ID приглашающего пользователя
            group_id: ID группы
            group_name: Название группы
            inviter_username: Имя приглашающего (опционально)
            
        Returns:
            True если уведомление отправлено, False в противном случае
        """
        try:
            max_user_id = await get_max_user_id(recipient_user_id)
            if not max_user_id:
                logger.debug(f"Пользователь {recipient_user_id} не зарегистрирован в MAX боте")
                return False
            
            if not inviter_username:
                from services.shared.utils import ServiceClient
                user_service = ServiceClient("user")
                try:
                    inviter = await user_service.get(f"/users/{inviter_user_id}")
                    inviter_username = inviter.get("username", "Пользователь")
                except:
                    inviter_username = "Пользователь"
                finally:
                    await user_service.close()
            
            text = f"""👥 *Приглашение в группу*

{inviter_username} пригласил(а) вас в группу *{group_name}*.

Выберите действие:"""
            
            keyboard = self.keyboard_builder.build_group_invitation_keyboard(invitation_id)
            
            await self.api_client.send_message(
                user_id=max_user_id,
                text=text,
                attachments=[keyboard],
                format="markdown"
            )
            
            logger.info(f"Уведомление о приглашении в группу отправлено пользователю {recipient_user_id} (max_user_id={max_user_id})")
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления о приглашении в группу: {e}", exc_info=True)
            return False
    
    async def send_low_satisfaction_notification(
        self,
        user_id: int,
        satisfaction: int,
        character_name: Optional[str] = None
    ) -> bool:
        """
        Отправить уведомление о низкой удовлетворённости персонажа
        
        Args:
            user_id: Внутренний ID пользователя
            satisfaction: Текущий уровень удовлетворённости (0-100)
            character_name: Имя персонажа (опционально)
            
        Returns:
            True если уведомление отправлено, False в противном случае
        """
        try:
            max_user_id = await get_max_user_id(user_id)
            if not max_user_id:
                logger.debug(f"Пользователь {user_id} не зарегистрирован в MAX боте")
                return False
            
            if not character_name:
                character_name = "ваш персонаж"
            
            text = f"""⚠️ *Низкая удовлетворённость!*

{character_name} чувствует себя плохо! 😟

Текущая удовлетворённость: *{satisfaction}%*

Выполняйте задачи, привычки и цели, чтобы повысить удовлетворённость персонажа! 💪"""
            
            keyboard = self.keyboard_builder.build_low_satisfaction_keyboard()
            
            await self.api_client.send_message(
                user_id=max_user_id,
                text=text,
                attachments=[keyboard],
                format="markdown"
            )
            
            logger.info(f"Уведомление о низкой удовлетворённости отправлено пользователю {user_id} (max_user_id={max_user_id}, satisfaction={satisfaction}%)")
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления о низкой удовлетворённости: {e}", exc_info=True)
            return False
    
    async def send_habit_activated_notification(
        self,
        user_id: int,
        habit_name: str,
        frequency: str
    ) -> bool:
        """
        Отправить уведомление об активации привычки (начале нового периода)
        
        Args:
            user_id: Внутренний ID пользователя
            habit_name: Название привычки
            frequency: Частота привычки (daily, weekly, monthly)
            
        Returns:
            True если уведомление отправлено, False в противном случае
        """
        try:
            max_user_id = await get_max_user_id(user_id)
            if not max_user_id:
                logger.debug(f"Пользователь {user_id} не зарегистрирован в MAX боте")
                return False
            
            # Определяем текст в зависимости от частоты
            frequency_labels = {
                "daily": "день",
                "weekly": "неделя",
                "monthly": "месяц"
            }
            period_label = frequency_labels.get(frequency.lower(), "период")
            
            text = f"""🌿 *Привычка активирована!*

Начался новый {period_label} для привычки *{habit_name}*.

Не забудьте выполнить её! 💪"""
            
            keyboard = self.keyboard_builder.build_habit_activated_keyboard()
            
            await self.api_client.send_message(
                user_id=max_user_id,
                text=text,
                attachments=[keyboard],
                format="markdown"
            )
            
            logger.info(f"Уведомление об активации привычки отправлено пользователю {user_id} (max_user_id={max_user_id}, habit={habit_name}, frequency={frequency})")
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления об активации привычки: {e}", exc_info=True)
            return False
    
    async def send_daily_reward_updated_notification(
        self,
        user_id: int
    ) -> bool:
        """
        Отправить уведомление об обновлении ежедневного приза
        
        Args:
            user_id: Внутренний ID пользователя
            
        Returns:
            True если уведомление отправлено, False в противном случае
        """
        try:
            max_user_id = await get_max_user_id(user_id)
            if not max_user_id:
                logger.debug(f"Пользователь {user_id} не зарегистрирован в MAX боте")
                return False
            
            text = f"""🎁 *Ежедневный приз обновился!*

Новый день - новый шанс получить награду!

Заберите свой ежедневный подарок (10 монет) прямо сейчас! 💰

💡 *Напоминание:* В инвентаре можно получить новый предмет! 🎒"""
            
            keyboard = self.keyboard_builder.build_daily_reward_keyboard()
            
            await self.api_client.send_message(
                user_id=max_user_id,
                text=text,
                attachments=[keyboard],
                format="markdown"
            )
            
            logger.info(f"Уведомление об обновлении ежедневного приза отправлено пользователю {user_id} (max_user_id={max_user_id})")
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления об обновлении ежедневного приза: {e}", exc_info=True)
            return False


    # ---------- Посещаемость (основной сценарий) ----------

    async def send_attendance_confirmed_notification(
        self,
        user_id: int,
        lesson_name: str,
        rewards: Optional[Dict[str, Any]] = None,
        rewards_status: str = "granted",
        character: Optional[Dict[str, Any]] = None,
        streak: Optional[Dict[str, Any]] = None,
        unlocked_sets: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        """Уведомление об отметке на занятии: награды, настроение персонажа, серия"""
        from services.shared.character_mood import mood_emoji

        try:
            max_user_id = await get_max_user_id(user_id)
            if not max_user_id:
                logger.debug(f"Пользователь {user_id} не зарегистрирован в MAX боте")
                return False

            rewards = rewards or {}
            lines = [f"✅ *Посещение отмечено: {lesson_name}*", ""]
            if rewards_status == "granted":
                lines.append(
                    f"Награда: +{rewards.get('coins', 0)} 🪙  +{rewards.get('intelligence_points', 0)} 🧠  "
                    f"+{rewards.get('satisfaction', 0)} 😊"
                )
            else:
                lines.append("Награды будут начислены чуть позже.")

            if character:
                mood = character.get("mood")
                before, after = character.get("satisfaction_before"), character.get("satisfaction")
                if mood:
                    label = character.get("mood_label") or ""
                    change = f" ({before} → {after})" if before is not None and after is not None else ""
                    lines.append(f"Персонаж {label} {mood_emoji(mood)}{change}")
                if character.get("level_up"):
                    lines.append(f"🎉 Новый уровень интеллекта: {character.get('intelligence_level')}!")

            if streak and streak.get("current"):
                lines.append(f"🔥 Серия посещений: {streak['current']}")
            for item in unlocked_sets or []:
                lines.append(f"🎁 Открыт новый сет: *{item.get('name')}*")

            await self.api_client.send_message(
                user_id=max_user_id,
                text="\n".join(lines),
                attachments=[self.keyboard_builder.build_attendance_keyboard()],
                format="markdown",
            )
            logger.info(f"Уведомление об отметке отправлено пользователю {user_id} (max_user_id={max_user_id})")
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления об отметке: {e}", exc_info=True)
            return False

    async def send_lesson_missed_notification(
        self,
        user_id: int,
        miss_id: int,
        lesson_name: str,
        freezes_available: int,
        penalty: int,
    ) -> bool:
        """Уведомление о пропуске с предложением «дня без штрафа»"""
        try:
            max_user_id = await get_max_user_id(user_id)
            if not max_user_id:
                return False
            if freezes_available > 0:
                text = (f"😔 *Пропуск: {lesson_name}*\n\n"
                        f"Персонаж загрустит (−{penalty} к настроению), а серия посещений прервётся.\n\n"
                        f"Бывает всякое — можно взять *день без штрафа*: осталось {freezes_available}.")
            else:
                text = (f"😔 *Пропуск: {lesson_name}*\n\n"
                        f"«Дни без штрафа» на этот месяц закончились: персонаж получит −{penalty} к настроению.\n"
                        f"Следующая пара вернёт всё на место 💪")
            await self.api_client.send_message(
                user_id=max_user_id,
                text=text,
                attachments=[self.keyboard_builder.build_lesson_missed_keyboard(miss_id, freezes_available)],
                format="markdown",
            )
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления о пропуске: {e}", exc_info=True)
            return False


    # ---------- Группа, куратор, поддержка ----------

    async def _to_chat(self, chat_id: int, text: str, keyboard: Optional[Dict[str, Any]] = None) -> bool:
        try:
            await self.api_client.send_message(chat_id=chat_id, text=text,
                                               attachments=[keyboard] if keyboard else None, format="markdown")
            return True
        except Exception as e:
            logger.error(f"Сообщение в чат {chat_id} не отправлено: {e}")
            return False

    async def _to_user(self, user_id: int, text: str, keyboard: Optional[Dict[str, Any]] = None) -> bool:
        try:
            max_user_id = await get_max_user_id(user_id)
            if not max_user_id:
                return False
            await self.api_client.send_message(user_id=max_user_id, text=text,
                                               attachments=[keyboard] if keyboard else None, format="markdown")
            return True
        except Exception as e:
            logger.error(f"Сообщение пользователю {user_id} не отправлено: {e}")
            return False

    def _chat_app_keyboard(self, text: str, start_param: str) -> Optional[Dict[str, Any]]:
        from services.max_bot_service.utils.keyboards import open_app_button
        button = open_app_button(text, start_param)
        return {"type": "inline_keyboard", "payload": {"buttons": [[button]]}} if button else None

    async def send_group_goal(self, chat_id: int, group_name: str, lesson_name: str, attended: int,
                              expected: int, percent: int, bonus: Dict[str, Any]) -> bool:
        text = (f"🔥 *{group_name} закрыла командную цель!*\n\n"
                f"На паре «{lesson_name}» уже {attended} из {expected} ({percent}%).\n"
                f"Каждый отметившийся получает бонус: +{bonus.get('coins', 0)} 🪙 +{bonus.get('satisfaction', 0)} 😊\n"
                f"Кто ещё не отметился — успейте, бонус достанется и вам!")
        return await self._to_chat(chat_id, text, self._chat_app_keyboard("✅ Отметиться", "checkin"))

    async def send_game_weekly_results(self, group_name: str, winners: List[Dict[str, Any]],
                                       chat_id: Optional[int] = None) -> bool:
        """Итоги недели мини-игры: личные сообщения призёрам и пост в чат группы"""
        places = {1: "1 место", 2: "2 место", 3: "3 место"}
        sent = []
        for w in winners:
            text = (f"*{places.get(w['place'], str(w['place']) + ' место')}* в «Забеге до пары» за прошлую неделю "
                    f"в группе {group_name}!\n\nРекорд: {w['score']} очков. Приз: +{w['coins']} монет уже на счету.")
            sent.append(await self._to_user(w["user_id"], text, self._chat_app_keyboard("Защитить титул", "game")))
        if chat_id:
            lines = [f"*Итоги «Забега до пары» — {group_name}*", ""]
            lines += [f"{w['place']}. {w['name']} — {w['score']} очков (+{w['coins']} монет)" for w in winners]
            lines += ["", "Новая неделя — новый рейтинг. Кто заберёт первое место?"]
            sent.append(await self._to_chat(chat_id, "\n".join(lines), self._chat_app_keyboard("Играть", "game")))
        return any(sent)

    async def send_group_lesson_summary(self, chat_id: int, group_name: str, lesson_name: str, attended: int,
                                        expected: int, percent: int, target_percent: int, achieved: bool,
                                        top_streaks: List[Dict[str, Any]]) -> bool:
        lines = [f"📊 *Итоги пары «{lesson_name}»* — {group_name}", "",
                 f"Отметились: {attended} из {expected} ({percent}%)",
                 "🎯 Командная цель выполнена!" if achieved else f"🎯 До командной цели не хватило: нужно {target_percent}%"]
        if top_streaks:
            lines.append("")
            lines.append("🏅 Лучшие серии: " + ", ".join(f"{s['name']} — {s['streak']}" for s in top_streaks))
        return await self._to_chat(chat_id, "\n".join(lines))

    async def send_group_lesson_reminder(self, chat_id: int, group_name: str, lesson_name: str,
                                         location: Optional[str], minutes: int, target_percent: int) -> bool:
        where = f", {location}" if location else ""
        text = (f"⏰ Через {minutes} мин — *{lesson_name}*{where}.\n"
                f"Цель группы: {target_percent}% отметок — тогда всем отметившимся бонус 🎁")
        return await self._to_chat(chat_id, text, self._chat_app_keyboard("✅ Отметиться", "checkin"))

    async def send_lesson_reminder(self, user_id: int, lesson_name: str, location: Optional[str], minutes: int) -> bool:
        where = f" · {location}" if location else ""
        text = (f"⏰ *Через {minutes} мин: {lesson_name}*{where}\n\n"
                f"Отметься по QR с экрана преподавателя — персонаж ждёт награду 😊")
        return await self._to_user(user_id, text, self.keyboard_builder.build_reminder_keyboard())

    async def send_support_request(self, curator_user_ids: List[int], student_user_id: int, student_name: str,
                                   groups: List[str], message: Optional[str]) -> bool:
        text = (f"🤝 *{student_name}* ({', '.join(groups) or 'без группы'}) просит поддержки."
                + (f"\n\n«{message}»" if message else "")
                + "\n\nСвяжитесь со студентом. Если ситуация сложная — подключите психолога или тьютора вуза.")
        sent = [await self._to_user(cid, text, self.keyboard_builder.build_curator_keyboard()) for cid in curator_user_ids]
        return any(sent)

    async def send_help_offer(self, user_id: int) -> bool:
        text = ("💬 Кажется, последние дни выдались непростыми — персонаж немного грустит.\n\n"
                "Если нужна помощь с учёбой или просто хочется поговорить — куратор группы на связи. "
                "Это нормально — просить поддержку.")
        return await self._to_user(user_id, text, self.keyboard_builder.build_help_keyboard())

    async def send_curator_nudge(self, user_id: int, curator_name: Optional[str]) -> bool:
        who = f"Куратор {curator_name}" if curator_name else "Куратор группы"
        text = (f"👋 {who} интересуется, как у тебя дела.\n\n"
                "Если что-то мешает ходить на пары или нужна помощь — нажми кнопку ниже, куратор свяжется с тобой.")
        return await self._to_user(user_id, text, self.keyboard_builder.build_help_keyboard())

    async def send_curator_digest(self, curator_user_id: int, groups: List[Dict[str, Any]]) -> bool:
        lines = ["📋 *Сводка по вашим группам за неделю*", ""]
        for group in groups:
            rate = group.get("attendance_rate")
            lines.append(f"*{group['group_name']}* — посещаемость {round(rate * 100)}%" if rate is not None
                         else f"*{group['group_name']}* — пар за неделю не было")
            for student in group.get("at_risk", []):
                lines.append(f"  ⚠️ {student['username']}")
            lines.append("")
        lines.append("Откройте кабинет куратора, чтобы написать студентам.")
        return await self._to_user(curator_user_id, "\n".join(lines), self.keyboard_builder.build_curator_keyboard())
