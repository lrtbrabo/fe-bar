/* The "Agente NIP": the Genie space embedded as a side panel reachable from every page.
   Pages register context-aware suggested questions; any page can open it with a question. */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import {
  Button,
  GenieChatInput,
  GenieChatMessageList,
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  useGenieChat,
} from '@databricks/appkit-ui/react';
import { RotateCcw, Sparkles } from 'lucide-react';

interface AgentApi {
  open: () => void;
  ask: (question: string) => void;
  setSuggestions: (s: string[]) => void;
}

const AgentContext = createContext<AgentApi | null>(null);

export function useAgent(): AgentApi {
  const ctx = useContext(AgentContext);
  if (!ctx) throw new Error('useAgent must be used inside <AgentProvider>');
  return ctx;
}

/* Register the suggested questions for the current page. */
export function useAgentSuggestions(questions: string[]) {
  const { setSuggestions } = useAgent();
  const key = questions.join('\u0001');
  useEffect(() => {
    setSuggestions(key ? key.split('\u0001') : []);
  }, [key, setSuggestions]);
}

export function AgentProvider({ children }: { children: ReactNode }) {
  const [isOpen, setOpen] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const { messages, status, error, sendMessage, reset, hasPreviousPage, fetchPreviousPage } =
    useGenieChat({ alias: 'default', persistInUrl: false });
  const busy = status === 'streaming' || status === 'loading-history';

  const ask = useCallback(
    (question: string) => {
      setOpen(true);
      if (!busy) sendMessage(question);
    },
    [busy, sendMessage],
  );
  const api = useMemo<AgentApi>(() => ({ open: () => setOpen(true), ask, setSuggestions }), [ask]);

  return (
    <AgentContext.Provider value={api}>
      {children}
      <Sheet open={isOpen} onOpenChange={setOpen}>
        <SheetContent side="right" className="w-full sm:max-w-xl p-0 gap-0 flex flex-col">
          <SheetHeader className="border-b px-5 py-4">
            <SheetTitle className="flex items-center gap-2">
              <Sparkles className="h-4 w-4" style={{ color: 'var(--viz-series-1)' }} aria-hidden />
              Agente NIP
            </SheetTitle>
            <SheetDescription>
              Pergunte em português sobre a fila, os prazos, as guias e o radar. As respostas vêm do Genie, com as suas
              permissões no Unity Catalog (dados pessoais mascarados).
            </SheetDescription>
          </SheetHeader>

          {messages.length === 0 ? (
            <div className="flex-1 overflow-y-auto px-5 py-6 space-y-3">
              <p className="text-sm text-muted-foreground">Sugestões para esta tela:</p>
              {suggestions.map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => ask(q)}
                  disabled={busy}
                  className="w-full rounded-lg border px-3 py-2.5 text-left text-sm text-foreground hover:bg-muted/60 transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          ) : (
            <div className="flex-1 min-h-0 flex flex-col">
              <GenieChatMessageList
                messages={messages}
                status={status}
                hasPreviousPage={hasPreviousPage}
                onFetchPreviousPage={fetchPreviousPage}
                className="flex-1 min-h-0"
              />
              {!busy && suggestions.length > 0 && (
                <div className="flex gap-1.5 overflow-x-auto px-4 pt-2 pb-1">
                  {suggestions.slice(0, 3).map((q) => (
                    <button
                      key={q}
                      type="button"
                      onClick={() => ask(q)}
                      className="shrink-0 max-w-[16rem] truncate rounded-full border px-2.5 py-1 text-xs text-muted-foreground hover:text-foreground"
                      title={q}
                    >
                      {q}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {error && <p className="px-5 pb-1 text-xs" style={{ color: 'var(--status-critical)' }}>{error}</p>}
          <div className="border-t px-4 py-3 flex items-end gap-2">
            <GenieChatInput onSend={sendMessage} disabled={busy} placeholder="Ex.: quais NIPs vencem hoje?" className="flex-1" />
            {messages.length > 0 && (
              <Button variant="ghost" size="icon" onClick={reset} disabled={busy} title="Nova conversa">
                <RotateCcw className="h-4 w-4" />
                <span className="sr-only">Nova conversa</span>
              </Button>
            )}
          </div>
        </SheetContent>
      </Sheet>
    </AgentContext.Provider>
  );
}
