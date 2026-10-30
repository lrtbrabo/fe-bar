import { createBrowserRouter, NavLink, Outlet, RouterProvider } from 'react-router';
import { Button } from '@databricks/appkit-ui/react';
import { LayoutDashboard, ListChecks, Radar, Sparkles } from 'lucide-react';
import { AgentProvider, useAgent } from './components/agent';
import { PainelPage } from './pages/PainelPage';
import { FilaPage } from './pages/FilaPage';
import { RadarPage } from './pages/RadarPage';

const navClass = ({ isActive }: { isActive: boolean }) =>
  `inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
    isActive ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground'
  }`;

function Header() {
  const agent = useAgent();
  return (
    <header className="sticky top-0 z-20 border-b bg-background/95 backdrop-blur px-4 md:px-6 py-3 flex flex-wrap items-center gap-x-6 gap-y-2">
      <div className="min-w-0">
        <h1 className="text-base font-semibold text-foreground leading-tight">NIP → VPP Copilot</h1>
        <p className="text-xs text-muted-foreground leading-tight">Centro de comando de NIPs da ANS</p>
      </div>
      <nav className="flex gap-1 overflow-x-auto">
        <NavLink to="/" end className={navClass}><LayoutDashboard className="h-4 w-4" />Painel</NavLink>
        <NavLink to="/fila" className={navClass}><ListChecks className="h-4 w-4" />Fila de NIPs</NavLink>
        <NavLink to="/radar" className={navClass}><Radar className="h-4 w-4" />Radar de prevenção</NavLink>
      </nav>
      <Button size="sm" className="ml-auto" onClick={() => agent.open()}>
        <Sparkles className="h-4 w-4" /> Agente NIP
      </Button>
    </header>
  );
}

function Layout() {
  return (
    <AgentProvider>
      <div className="min-h-screen bg-background flex flex-col">
        <Header />
        <main className="flex-1 w-full max-w-[1600px] mx-auto p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </AgentProvider>
  );
}

const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: '/', element: <PainelPage /> },
      { path: '/fila', element: <FilaPage /> },
      { path: '/radar', element: <RadarPage /> },
    ],
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
