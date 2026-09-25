import React from 'react';
import { Modal } from '../../../components/common/Modal.jsx';
import { HabitForm } from './HabitForm.jsx';

export function HabitModal({
  title,
  isOpen,
  onClose,
  values,
  onChange,
  onSubmit,
  submitLabel,
  disabled,
  coinsInfo,
  intelligenceInfo,
  satisfactionInfo
}) {
  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title}>
      <HabitForm
        values={values}
        onChange={onChange}
        onSubmit={onSubmit}
        submitLabel={submitLabel}
        disabled={disabled}
        coinsInfo={coinsInfo}
        intelligenceInfo={intelligenceInfo}
        satisfactionInfo={satisfactionInfo}
      />
    </Modal>
  );
}

