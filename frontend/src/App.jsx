import React from 'react';
import { AppProvider } from './state/AppProvider.jsx';
import { AppShell } from './components/layout/AppShell.jsx';
import { ToastViewport } from './components/ui/toast.jsx';

export default function App() {
  return (
    <AppProvider>
      <AppShell />
      <ToastViewport />
    </AppProvider>
  );
}
