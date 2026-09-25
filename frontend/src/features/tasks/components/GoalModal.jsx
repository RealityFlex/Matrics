import React from 'react';
import { Modal } from '../../../components/common/Modal.jsx';
import { GoalForm } from './GoalForm.jsx';

export function GoalModal({
  title,
  isOpen,
  onClose,
  values,
  onChange,
  onSubmit,
  submitLabel,
  disabled
}) {
  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title}>
      <GoalForm values={values} onChange={onChange} onSubmit={onSubmit} submitLabel={submitLabel} disabled={disabled} />
    </Modal>
  );
}

