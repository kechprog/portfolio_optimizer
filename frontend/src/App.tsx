import { AppRouter } from './router/AppRouter';
import { ToastProvider } from './contexts/ToastContext';
import { ToastContainer } from './components/Toast';

function App() {
  return (
    <ToastProvider>
      <AppRouter />
      <ToastContainer />
    </ToastProvider>
  );
}

export default App;
