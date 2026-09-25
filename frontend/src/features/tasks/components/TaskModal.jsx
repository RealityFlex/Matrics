import React from 'react';
import { Modal } from '../../../components/common/Modal.jsx';
import { TaskForm } from './TaskForm.jsx';

export function TaskModal({
  title,
  isOpen,
  onClose,
  values,
  onChange,
  onSubmit,
  submitLabel,
  disabled,
  showGenerate,
  onGenerate,
  isGenerating,
  generateStatus,
  generateDisabled,
  coinsInfo,
  intelligenceInfo
}) {
  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title}>
      <TaskForm
        values={values}
        onChange={onChange}
        onSubmit={onSubmit}
        submitLabel={submitLabel}
        disabled={disabled}
        showGenerate={showGenerate}
        onGenerate={onGenerate}
        isGenerating={isGenerating}
        generateStatus={generateStatus}
        generateDisabled={generateDisabled}
        coinsInfo={coinsInfo}
        intelligenceInfo={intelligenceInfo}
      />
    </Modal>
  );
}

