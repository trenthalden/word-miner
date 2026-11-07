// word-miner — Desktop flashcard pane (SDK-only, plain ESM, no build step).
// Data via ctx.rest → dashboard/plugin_api.py. If the backend half is disabled,
// the pane shows a clear error instead of crashing.
import React from 'react'
import { Button, host, PANES_AREA } from '@hermes/plugin-sdk'

const h = React.createElement

function useRest(ctx) {
  return React.useCallback(async (path, opts) => {
    if (!ctx?.rest) throw new Error('ctx.rest unavailable — enable the word-miner agent plugin')
    const res = await ctx.rest(path, opts)
    if (res == null) throw new Error('empty response from word-miner backend')
    return typeof res === 'string' ? JSON.parse(res) : res
  }, [ctx])
}

function StatsPanel({ stats }) {
  if (!stats) return null
  const levels = stats.levels || {}
  return h('div', { className: 'space-y-1 text-xs' },
    h('div', { className: 'font-medium' }, `Total ${stats.total ?? 0} · due ${stats.due_today ?? 0} · streak ${stats.streak_days ?? 0}d`),
    h('div', { className: 'text-muted-foreground' },
      ['new', 'weak', 'medium', 'good', 'mastered'].map(k => `${k} ${levels[k] || 0}`).join(' · ')))
}

function Flashcard({ card, revealed, elapsedMs, onReveal, onGrade }) {
  if (!card) return h('div', { className: 'text-sm text-muted-foreground' }, 'No cards in this session.')
  return h('div', { className: 'space-y-3' },
    h('div', { className: 'text-[11px] uppercase tracking-wide text-muted-foreground' },
      `${card.mastery || ''} · ${card.prompt_side || ''} · ${(elapsedMs / 1000).toFixed(1)}s`),
    h('div', { className: 'text-lg font-semibold leading-snug' }, card.prompt),
    card.hint ? h('div', { className: 'text-xs text-muted-foreground' }, card.hint) : null,
    !revealed
      ? h(Button, { size: 'sm', onClick: onReveal }, 'Reveal')
      : h('div', { className: 'space-y-2' },
          h('div', { className: 'rounded border border-border/60 bg-muted/30 p-2 text-sm' },
            card.expected,
            card.reading ? h('span', { className: 'text-muted-foreground' }, ` · ${card.reading}`) : null),
          h('div', { className: 'flex flex-wrap gap-1' },
            [1, 2, 3, 4].map(r => h(Button, {
              key: r, size: 'sm', variant: r >= 3 ? 'default' : 'outline',
              onClick: () => onGrade(r),
            }, ({ 1: 'Again', 2: 'Hard', 3: 'Good', 4: 'Easy' })[r])))))
}

function Pane({ ctx }) {
  const rest = useRest(ctx)
  const [deck, setDeck] = React.useState('ja-en')
  const [decks, setDecks] = React.useState([])
  const [stats, setStats] = React.useState(null)
  const [cards, setCards] = React.useState([])
  const [index, setIndex] = React.useState(0)
  const [revealed, setRevealed] = React.useState(false)
  const [shownAt, setShownAt] = React.useState(Date.now())
  const [elapsed, setElapsed] = React.useState(0)
  const [error, setError] = React.useState(null)
  const [busy, setBusy] = React.useState(false)

  React.useEffect(() => {
    const t = setInterval(() => setElapsed(Date.now() - shownAt), 100)
    return () => clearInterval(t)
  }, [shownAt])

  const refreshStats = React.useCallback(async () => {
    try {
      const s = await rest(`/stats?deck=${encodeURIComponent(deck)}`)
      setStats(s)
      const d = await rest('/decks')
      if (d?.decks) setDecks(d.decks)
    } catch (e) {
      setError(String(e?.message || e))
    }
  }, [rest, deck])

  const startSession = React.useCallback(async () => {
    setBusy(true); setError(null)
    try {
      const s = await rest(`/session?deck=${encodeURIComponent(deck)}`)
      setCards(s.cards || [])
      setIndex(0)
      setRevealed(false)
      setShownAt(Date.now())
      await refreshStats()
    } catch (e) {
      setError(String(e?.message || e))
    } finally {
      setBusy(false)
    }
  }, [rest, deck, refreshStats])

  React.useEffect(() => { refreshStats() }, [refreshStats])

  const card = cards[index]
  const onReveal = () => setRevealed(true)
  const onGrade = async (rating) => {
    if (!card) return
    setBusy(true)
    try {
      await rest('/grade', {
        method: 'POST',
        body: { card_id: card.card_id, rating, response_ms: Date.now() - shownAt },
      })
      const next = index + 1
      if (next >= cards.length) {
        setCards([])
        setIndex(0)
        await refreshStats()
      } else {
        setIndex(next)
        setRevealed(false)
        setShownAt(Date.now())
      }
    } catch (e) {
      setError(String(e?.message || e))
    } finally {
      setBusy(false)
    }
  }

  return h('div', { className: 'flex h-full flex-col gap-3 overflow-auto p-3 text-sm text-foreground' },
    h('div', { className: 'flex items-center gap-2' },
      h('span', { className: 'text-xs font-semibold uppercase tracking-wide' }, 'word-miner'),
      h('select', {
        className: 'rounded border border-border bg-background px-2 py-1 text-xs',
        value: deck,
        onChange: e => setDeck(e.target.value),
      },
        ...(decks.length ? decks : [{ name: deck }]).map(d =>
          h('option', { key: d.name || d, value: d.name || d }, d.name || d))),
      h('span', { className: 'flex-1' }),
      h(Button, { size: 'sm', disabled: busy, onClick: startSession }, busy ? '…' : 'Session')),
    error ? h('div', { className: 'rounded border border-red-500/40 p-2 text-xs text-red-500' }, error,
      h('div', { className: 'mt-1 text-muted-foreground' },
        'Enable the word-miner agent plugin in this profile, then Rescan Desktop plugins.')) : null,
    h(StatsPanel, { stats }),
    h(Flashcard, { card, revealed, elapsedMs: elapsed, onReveal, onGrade }),
    !card && !error ? h('div', { className: 'text-xs text-muted-foreground' },
      'Start a session, or mine words via chat with skill word-miner:word-miner-extract.') : null)
}

export default {
  id: 'word-miner',
  name: 'Word Miner',
  defaultEnabled: false,
  register(ctx) {
    ctx.register({
      id: 'pane',
      area: PANES_AREA,
      title: 'deck',
      data: {
        placement: 'right',
        collapsible: true,
        dock: { pane: 'workspace', pos: 'right' },
        width: '360px',
        minWidth: '280px',
        maxWidth: '520px',
      },
      render: () => h(Pane, { ctx }),
    })
  },
}
