/**
 * Утилиты для экспорта данных в PDF с поддержкой кириллицы
 */

export function exportUserToPDF(data, formatDate) {
  if (!data || !data.user) {
    throw new Error('Нет данных для экспорта');
  }

  const { jsPDF } = window.jspdf;
  if (!jsPDF) {
    throw new Error('Библиотека для генерации PDF не загружена');
  }

  const doc = new jsPDF();
  let yPos = 20;
  const pageWidth = doc.internal.pageSize.getWidth();
  const margin = 20;
  const maxWidth = pageWidth - 2 * margin;
  const lineHeight = 7;

  // Функция для безопасного добавления текста с кириллицей
  const addText = (text, x, y, options = {}) => {
    if (!text) return y;
    try {
      const fontSize = options.fontSize || doc.getFontSize();
      const fontStyle = options.fontStyle || 'normal';
      doc.setFontSize(fontSize);
      doc.setFont('helvetica', fontStyle);
      
      // jsPDF 2.x поддерживает UTF-8, но нужно правильно обрабатывать текст
      const textStr = String(text);
      const lines = doc.splitTextToSize(textStr, options.maxWidth || maxWidth);
      
      lines.forEach((line, idx) => {
        if (yPos > 280) {
          doc.addPage();
          yPos = 20;
        }
        // Используем прямой вызов text с UTF-8 строкой
        doc.text(line, x, yPos);
        yPos += lineHeight;
      });
      
      return yPos;
    } catch (e) {
      console.warn('Ошибка добавления текста:', e, text);
      // Fallback на латиницу если есть проблемы
      const safeText = String(text).replace(/[^\x00-\x7F]/g, '?');
      if (yPos > 280) {
        doc.addPage();
        yPos = 20;
      }
      doc.text(safeText.substring(0, 50), x, yPos);
      return yPos + lineHeight;
    }
  };

  // Заголовок
  yPos = addText('Статистика пользователя', margin, yPos, { fontSize: 20, fontStyle: 'bold' });
  yPos += 5;

  // Основная информация
  yPos = addText('Основная информация', margin, yPos, { fontSize: 14, fontStyle: 'bold' });
  yPos += 3;
  
  const userInfo = [
    `ID: ${data.user.id ?? '—'}`,
    `Username: ${data.user.username ?? '—'}`,
    `Email: ${data.user.email ?? '—'}`,
    `Монеты: ${data.user.coins ?? 0}`,
    `Дата создания: ${formatDate(data.user.created_at)}`
  ];
  userInfo.forEach(line => {
    yPos = addText(line, margin, yPos, { fontSize: 11 });
  });
  yPos += 5;

  // Персонаж
  if (data.character) {
    if (yPos > 280) {
      doc.addPage();
      yPos = 20;
    }
    yPos = addText('Персонаж', margin, yPos, { fontSize: 14, fontStyle: 'bold' });
    yPos += 3;
    
    const charInfo = [
      `Имя: ${data.character.name ?? '—'}`,
      `Уровень: ${data.character.level ?? 0}`,
      `Уровень интеллекта: ${data.character.intelligence_level ?? 0}`,
      `Очки интеллекта: ${data.character.intelligence_points ?? 0}`,
      `Рейтинг: ${data.character.rating ?? 0}`,
      `Удовлетворённость: ${data.character.satisfaction ?? 0}%`,
      `Бонусные очки: ${data.character.bonus_points ?? 0}`
    ];
    charInfo.forEach(line => {
      yPos = addText(line, margin, yPos, { fontSize: 11 });
    });
    yPos += 5;
  }

  // Статистика по привычкам
  if (data.habitStats) {
    if (yPos > 280) {
      doc.addPage();
      yPos = 20;
    }
    yPos = addText('Привычки', margin, yPos, { fontSize: 14, fontStyle: 'bold' });
    yPos += 3;
    
    const habitInfo = [
      `Всего привычек: ${data.habitStats.total_habits ?? 0}`,
      `Всего выполнений: ${data.habitStats.total_completions ?? 0}`
    ];
    if (data.habitStats.by_frequency) {
      habitInfo.push(`Ежедневные: ${data.habitStats.by_frequency.daily ?? 0}`);
      habitInfo.push(`Еженедельные: ${data.habitStats.by_frequency.weekly ?? 0}`);
      habitInfo.push(`Ежемесячные: ${data.habitStats.by_frequency.monthly ?? 0}`);
    }
    habitInfo.forEach(line => {
      yPos = addText(line, margin, yPos, { fontSize: 11 });
    });
    yPos += 5;
  }

  // Статистика по задачам
  if (data.taskStats) {
    if (yPos > 280) {
      doc.addPage();
      yPos = 20;
    }
    yPos = addText('Задачи', margin, yPos, { fontSize: 14, fontStyle: 'bold' });
    yPos += 3;
    
    const taskInfo = [
      `Всего задач: ${data.taskStats.total ?? 0}`,
      `Выполнено: ${data.taskStats.completed ?? 0}`,
      `В процессе: ${data.taskStats.in_progress ?? 0}`,
      `К выполнению: ${data.taskStats.todo ?? 0}`,
      `Отменено: ${data.taskStats.cancelled ?? 0}`,
      `Процент выполнения: ${data.taskStats.completion_rate ?? 0}%`
    ];
    taskInfo.forEach(line => {
      yPos = addText(line, margin, yPos, { fontSize: 11 });
    });
    yPos += 5;
  }

  // Статистика по событиям
  if (data.eventStats) {
    if (yPos > 280) {
      doc.addPage();
      yPos = 20;
    }
    yPos = addText('События', margin, yPos, { fontSize: 14, fontStyle: 'bold' });
    yPos += 3;
    
    const eventInfo = [
      `Зарегистрировано: ${data.eventStats.registered_events ?? 0}`,
      `Посещено: ${data.eventStats.attended_events ?? 0}`,
      `Процент посещаемости: ${data.eventStats.attendance_rate ?? 0}%`
    ];
    eventInfo.forEach(line => {
      yPos = addText(line, margin, yPos, { fontSize: 11 });
    });
    yPos += 5;
  }

  // Статистика по достижениям
  if (data.achievementStats) {
    if (yPos > 280) {
      doc.addPage();
      yPos = 20;
    }
    yPos = addText('Достижения', margin, yPos, { fontSize: 14, fontStyle: 'bold' });
    yPos += 3;
    
    const achievementInfo = [
      `Всего достижений: ${data.achievementStats.total_achievements ?? 0}`,
      `Завершено: ${data.achievementStats.completed ?? 0}`,
      `В процессе: ${data.achievementStats.in_progress ?? 0}`,
      `Процент завершения: ${data.achievementStats.completion_rate ?? 0}%`
    ];
    achievementInfo.forEach(line => {
      yPos = addText(line, margin, yPos, { fontSize: 11 });
    });
    yPos += 5;
  }

  // Статистика по соревнованиям
  if (data.competitionStats) {
    if (yPos > 280) {
      doc.addPage();
      yPos = 20;
    }
    yPos = addText('Соревнования', margin, yPos, { fontSize: 14, fontStyle: 'bold' });
    yPos += 3;
    
    const competitionInfo = [
      `Всего соревнований: ${data.competitionStats.total_competitions ?? 0}`,
      `Завершено: ${data.competitionStats.completed_competitions ?? 0}`,
      `1-е места: ${data.competitionStats.first_places ?? 0}`,
      `2-е места: ${data.competitionStats.second_places ?? 0}`,
      `3-е места: ${data.competitionStats.third_places ?? 0}`
    ];
    competitionInfo.forEach(line => {
      yPos = addText(line, margin, yPos, { fontSize: 11 });
    });
    yPos += 5;
  }

  // Инвентарь
  if (data.inventory && Array.isArray(data.inventory) && data.inventory.length > 0) {
    if (yPos > 250) {
      doc.addPage();
      yPos = 20;
    }
    yPos = addText('Инвентарь', margin, yPos, { fontSize: 14, fontStyle: 'bold' });
    yPos += 3;
    
    yPos = addText(`Всего предметов: ${data.inventory.length}`, margin, yPos, { fontSize: 11 });
    yPos += 5;
    
    // Заголовки таблицы
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(10);
    doc.text('Предмет', margin, yPos);
    doc.text('Кол-во', margin + 100, yPos);
    doc.text('Редкость', margin + 130, yPos);
    yPos += lineHeight;
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(9);
    
    const rarityLabels = {
      common: 'Обычный',
      uncommon: 'Необычный',
      rare: 'Редкий',
      epic: 'Эпический',
      legendary: 'Легендарный'
    };
    
    data.inventory.slice(0, 30).forEach((userItem) => {
      if (yPos > 280) {
        doc.addPage();
        yPos = 20;
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(10);
        doc.text('Предмет', margin, yPos);
        doc.text('Кол-во', margin + 100, yPos);
        doc.text('Редкость', margin + 130, yPos);
        yPos += lineHeight;
        doc.setFont('helvetica', 'normal');
        doc.setFontSize(9);
      }
      
      const item = userItem.item || userItem;
      const itemName = item?.name ?? userItem.item_name ?? 'Неизвестный предмет';
      const quantity = userItem.quantity ?? 0;
      const rarity = item?.rarity ?? userItem.rarity ?? 'common';
      const rarityLabel = rarityLabels[rarity] || rarity;
      
      const truncatedName = doc.splitTextToSize(itemName, 90);
      truncatedName.forEach((line, idx) => {
        doc.text(line, margin, yPos + (idx * lineHeight));
      });
      doc.text(String(quantity), margin + 100, yPos);
      doc.text(rarityLabel, margin + 130, yPos);
      yPos += lineHeight * truncatedName.length;
    });
    
    if (data.inventory.length > 30) {
      if (yPos > 280) {
        doc.addPage();
        yPos = 20;
      }
      doc.setFontSize(9);
      yPos = addText(`... и ещё ${data.inventory.length - 30} предметов`, margin, yPos, { fontSize: 9 });
    }
    yPos += 5;
  }

  // Футер с датой генерации
  const totalPages = doc.internal.pages.length - 1;
  for (let i = 1; i <= totalPages; i++) {
    doc.setPage(i);
    doc.setFontSize(8);
    doc.setTextColor(128, 128, 128);
    const footerText = `Сгенерировано: ${new Date().toLocaleString('ru-RU')} | Страница ${i} из ${totalPages}`;
    try {
      doc.text(footerText, margin, doc.internal.pageSize.getHeight() - 10);
    } catch (e) {
      // Fallback для футера
      doc.text(`Page ${i}/${totalPages}`, margin, doc.internal.pageSize.getHeight() - 10);
    }
  }

  // Сохранение файла
  const fileName = `user_stats_${data.user.id}_${data.user.username}_${new Date().toISOString().split('T')[0]}.pdf`;
  doc.save(fileName);
  
  return fileName;
}

/**
 * Экспорт статистики всех пользователей в отдельные PDF файлы
 */
export async function exportAllUsersToPDF(users, adminApi) {
  if (!users || !Array.isArray(users) || users.length === 0) {
    throw new Error('Нет пользователей для экспорта');
  }

  const { jsPDF } = window.jspdf;
  if (!jsPDF) {
    throw new Error('Библиотека для генерации PDF не загружена');
  }

  const formatDate = (dateString) => {
    if (!dateString) return '—';
    try {
      const date = new Date(dateString);
      if (isNaN(date.getTime())) return '—';
      return date.toLocaleString('ru-RU', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      });
    } catch (e) {
      return String(dateString);
    }
  };

  // Загружаем данные для каждого пользователя
  for (let i = 0; i < users.length; i++) {
    const user = users[i];
    try {
      // Показываем прогресс
      console.log(`Экспорт пользователя ${i + 1}/${users.length}: ${user.username} (ID: ${user.id})`);

      // Загружаем все данные пользователя
      const [
        userData,
        character,
        habitStats,
        taskStats,
        eventStats,
        achievementStats,
        competitionStats,
        inventory,
        achievements,
        tasks,
        habits,
        goals
      ] = await Promise.allSettled([
        adminApi.getUser(user.id),
        adminApi.getUserCharacter(user.id).catch(() => null),
        adminApi.getUserHabitStats(user.id).catch(() => null),
        adminApi.getUserTaskStats(user.id).catch(() => null),
        adminApi.getUserEventStats(user.id).catch(() => null),
        adminApi.getUserAchievementStats(user.id).catch(() => null),
        adminApi.getUserCompetitionStats(user.id).catch(() => null),
        adminApi.getUserInventory(user.id).catch(() => null),
        adminApi.getUserAchievements(user.id).catch(() => null),
        adminApi.getUserTasks(user.id).catch(() => null),
        adminApi.getUserHabits(user.id).catch(() => null),
        adminApi.getUserGoals(user.id).catch(() => null)
      ]);

      const data = {
        user: userData.status === 'fulfilled' ? userData.value : user,
        character: character.status === 'fulfilled' ? character.value : null,
        habitStats: habitStats.status === 'fulfilled' ? habitStats.value : null,
        taskStats: taskStats.status === 'fulfilled' ? taskStats.value : null,
        eventStats: eventStats.status === 'fulfilled' ? eventStats.value : null,
        achievementStats: achievementStats.status === 'fulfilled' ? achievementStats.value : null,
        competitionStats: competitionStats.status === 'fulfilled' ? competitionStats.value : null,
        inventory: inventory.status === 'fulfilled' ? inventory.value : null,
        achievements: achievements.status === 'fulfilled' ? achievements.value : null,
        tasks: tasks.status === 'fulfilled' ? tasks.value : null,
        habits: habits.status === 'fulfilled' ? habits.value : null,
        goals: goals.status === 'fulfilled' ? goals.value : null
      };

      // Генерируем PDF
      exportUserToPDF(data, formatDate);

      // Небольшая задержка между файлами, чтобы браузер успел обработать
      if (i < users.length - 1) {
        await new Promise(resolve => setTimeout(resolve, 500));
      }
    } catch (error) {
      console.error(`Ошибка экспорта пользователя ${user.id} (${user.username}):`, error);
      // Продолжаем экспорт остальных пользователей
    }
  }
}

