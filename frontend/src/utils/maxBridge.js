/**
 * Обёртки над MAX Bridge (window.WebApp) с безопасными заглушками для веб-версии вне MAX.
 * Документация: https://dev.max.ru/docs/webapps/bridge
 */

export function getWebApp() {
  if (typeof window === 'undefined') {
    return null;
  }
  return window.WebApp ?? null;
}

/** Мини-приложение открыто внутри MAX (есть подписанные данные запуска) */
export function isInsideMax() {
  const webApp = getWebApp();
  return Boolean(webApp && (webApp.initData || webApp.initDataUnsafe?.user));
}

export function getPlatform() {
  return getWebApp()?.platform ?? 'web';
}

export function getStartParam() {
  const webApp = getWebApp();
  const fromBridge = webApp?.initDataUnsafe?.start_param;
  if (fromBridge) {
    return fromBridge;
  }
  try {
    // Для веб-демо: ?startapp=att-12-0457 в адресной строке
    return new URLSearchParams(window.location.search).get('startapp');
  } catch {
    return null;
  }
}

export function readyAndExpand() {
  const webApp = getWebApp();
  try {
    webApp?.ready?.();
    webApp?.expand?.();
  } catch (error) {
    console.warn('MAX Bridge: ready/expand недоступны', error);
  }
}

/** Сканер QR-кода MAX доступен только на мобильных платформах */
export function canScanQr() {
  const webApp = getWebApp();
  const platform = getPlatform();
  return Boolean(webApp?.openCodeReader) && (platform === 'ios' || platform === 'android');
}

/** Открыть сканер QR. Возвращает строку из QR или null, если пользователь закрыл сканер. */
export async function scanQr() {
  const webApp = getWebApp();
  if (!webApp?.openCodeReader) {
    throw new Error('Сканер QR недоступен на этой платформе — введите код вручную');
  }
  const result = await webApp.openCodeReader(false);
  if (typeof result === 'string') {
    return result;
  }
  return result?.value ?? result?.data ?? result?.text ?? null;
}

export function haptic(type = 'success') {
  const feedback = getWebApp()?.HapticFeedback;
  try {
    if (type === 'success' || type === 'error' || type === 'warning') {
      feedback?.notificationOccurred?.(type);
    } else {
      feedback?.impactOccurred?.(type);
    }
  } catch {
    /* вибрация — необязательный эффект */
  }
}

/**
 * Системная кнопка «Назад» MAX: стек обработчиков (модалки закрываются по очереди).
 * push() возвращает функцию снятия обработчика.
 */
const backStack = [];
let backListenerAttached = false;

function onBackPressed() {
  const handler = backStack[backStack.length - 1];
  if (handler) {
    handler();
  }
}

export const maxBackButton = {
  push(handler) {
    const backButton = getWebApp()?.BackButton;
    backStack.push(handler);
    try {
      if (backButton) {
        if (!backListenerAttached) {
          backButton.onClick?.(onBackPressed);
          backListenerAttached = true;
        }
        backButton.show?.();
      }
    } catch {
      /* BackButton недоступен вне MAX */
    }
    return () => {
      const index = backStack.lastIndexOf(handler);
      if (index >= 0) {
        backStack.splice(index, 1);
      }
      try {
        if (!backStack.length) {
          backButton?.hide?.();
        }
      } catch {
        /* ignore */
      }
    };
  }
};

/**
 * Поделиться текстом и ссылкой: в MAX — shareMaxContent (все платформы, нужен клик пользователя),
 * в браузере — Web Share API, иначе копирование в буфер. Возвращает 'shared' | 'copied' | 'cancelled'.
 */
export async function shareContent({ text, link }) {
  const webApp = getWebApp();
  try {
    if (webApp?.shareMaxContent) {
      await webApp.shareMaxContent({ text, link });
      return 'shared';
    }
    if (navigator.share) {
      await navigator.share({ text, url: link });
      return 'shared';
    }
  } catch (error) {
    if (error?.name === 'AbortError') return 'cancelled';
  }
  try {
    await navigator.clipboard.writeText(link ? `${text}\n${link}` : text);
    return 'copied';
  } catch {
    return 'cancelled';
  }
}
