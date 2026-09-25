import React, { useEffect, useRef, useState } from 'react';
import { Modal } from '../../../components/common/Modal.jsx';
import { Button } from '../../../components/ui/index.jsx';

export function CodeInputModal({ isOpen, onClose, title, onVerify, isLoading }) {
  const [digits, setDigits] = useState(['', '', '', '']);
  const inputRef0 = useRef(null);
  const inputRef1 = useRef(null);
  const inputRef2 = useRef(null);
  const inputRef3 = useRef(null);
  const inputRefs = [inputRef0, inputRef1, inputRef2, inputRef3];

  useEffect(() => {
    if (isOpen) {
      // Фокус на первое поле без прокрутки
      setTimeout(() => {
        if (inputRefs[0].current) {
          inputRefs[0].current.focus({ preventScroll: true });
        }
      }, 100);
    } else {
      setDigits(['', '', '', '']);
    }
  }, [isOpen]);

  const handleDigitChange = (index, value) => {
    const digit = value.replace(/\D/g, '').slice(0, 1);
    const newDigits = [...digits];
    newDigits[index] = digit;
    setDigits(newDigits);

    // Автоматически переходим к следующему полю без прокрутки
    if (digit && index < 3) {
      setTimeout(() => {
        if (inputRefs[index + 1].current) {
          inputRefs[index + 1].current.focus({ preventScroll: true });
        }
      }, 10);
    }
  };

  const handleKeyDown = (index, e) => {
    // Backspace - удаляем текущую цифру и переходим к предыдущему полю без прокрутки
    if (e.key === 'Backspace' && !digits[index] && index > 0) {
      setTimeout(() => {
        if (inputRefs[index - 1].current) {
          inputRefs[index - 1].current.focus({ preventScroll: true });
        }
      }, 10);
    }
    // Enter - отправляем форму если все поля заполнены
    if (e.key === 'Enter' && digits.every(d => d !== '')) {
      handleSubmit(e);
    }
  };

  const handlePaste = (e) => {
    e.preventDefault();
    const pastedData = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 4);
    const newDigits = ['', '', '', ''];
    for (let i = 0; i < pastedData.length; i++) {
      newDigits[i] = pastedData[i];
    }
    setDigits(newDigits);
    const focusIndex = pastedData.length < 4 ? pastedData.length : 3;
    setTimeout(() => {
      if (inputRefs[focusIndex].current) {
        inputRefs[focusIndex].current.focus({ preventScroll: true });
      }
    }, 10);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const code = digits.join('');
    if (code.length === 4 && !isLoading) {
      onVerify(code);
    }
  };

  const isComplete = digits.every(d => d !== '');

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title}>
      <form onSubmit={handleSubmit} className="code-modal">
        <p className="code-modal__hint">Введите 4-значный код для отметки посещения</p>

        <div className="code-modal__digits" onPaste={handlePaste}>
          {digits.map((digit, index) => (
            <input
              key={index}
              ref={inputRefs[index]}
              type="tel"
              inputMode="numeric"
              pattern="[0-9]"
              value={digit}
              onChange={(e) => handleDigitChange(index, e.target.value)}
              onKeyDown={(e) => handleKeyDown(index, e)}
              maxLength={1}
              disabled={isLoading}
              aria-label={`Цифра ${index + 1}`}
              className={`code-modal__digit ${digit ? 'is-filled' : ''}`}
            />
          ))}
        </div>

        <div className="dialog-actions">
          <Button variant="secondary" onClick={onClose} disabled={isLoading}>
            Отмена
          </Button>
          <Button type="submit" loading={isLoading} disabled={!isComplete}>
            Подтвердить
          </Button>
        </div>
      </form>
    </Modal>
  );
}

