import Dashboard from './components/Dashboard'
import './App.css'
import { ToastProvider } from './ui'

function App() {
  return (
    <ToastProvider>
      <Dashboard />
    </ToastProvider>
  )
}

export default App
