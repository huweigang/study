import React from 'react';

/**
 * Step 1: 布局骨架（灰色块）
 */
function PlayerSkeleton({ position, rotate = false }) {
  const positionClass = {
    bottom: 'bottom-4 left-1/2 -translate-x-1/2',
    top: 'top-4 left-1/2 -translate-x-1/2',
    left: 'left-4 top-1/2 -translate-y-1/2',
    right: 'right-4 top-1/2 -translate-y-1/2',
  }[position];

  return (
    <div className={`absolute ${positionClass}`}>
      <div
        className={`flex items-center gap-2 rounded-lg bg-zinc-500/70 px-3 py-2 ${
          rotate ? 'rotate-90' : ''
        }`}
      >
        <div className="h-10 w-10 rounded-md bg-zinc-300" />
        <div className="flex flex-col gap-1">
          <div className="h-3 w-16 rounded bg-zinc-300" />
          <div className="h-3 w-12 rounded bg-zinc-300" />
        </div>
      </div>
    </div>
  );
}

function TableCenterSkeleton() {
  return <div className="h-28 w-36 rounded-2xl bg-zinc-600/80" />;
}

function HandCardsSkeleton() {
  return (
    <div className="flex items-end gap-1 rounded-xl bg-zinc-700/60 p-2">
      {Array.from({ length: 13 }).map((_, index) => (
        <div key={index} className="h-14 w-9 rounded-md bg-zinc-400" />
      ))}
    </div>
  );
}

function ActionBarSkeleton() {
  return (
    <div className="flex items-center gap-3">
      {Array.from({ length: 4 }).map((_, index) => (
        <div key={index} className="h-10 w-20 rounded-xl bg-zinc-500" />
      ))}
    </div>
  );
}

export function MahjongLayoutSkeleton() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-900 p-4">
      <div className="relative flex h-[800px] w-[800px] items-center justify-center rounded-3xl bg-zinc-700 p-8">
        <div className="relative flex h-[600px] w-[600px] items-center justify-center rounded-3xl bg-zinc-600 p-4">
          <PlayerSkeleton position="top" />
          <PlayerSkeleton position="left" rotate />
          <PlayerSkeleton position="right" rotate />
          <PlayerSkeleton position="bottom" />

          <TableCenterSkeleton />

          <div className="absolute bottom-24 left-1/2 -translate-x-1/2">
            <ActionBarSkeleton />
          </div>

          <div className="absolute bottom-4 left-1/2 -translate-x-1/2">
            <HandCardsSkeleton />
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Step 2: 完整 UI
 */
function Player({ name, score, wind, position, rotate = false, highlight = false }) {
  const positionClass = {
    bottom: 'bottom-4 left-1/2 -translate-x-1/2',
    top: 'top-4 left-1/2 -translate-x-1/2',
    left: 'left-4 top-1/2 -translate-y-1/2',
    right: 'right-4 top-1/2 -translate-y-1/2',
  }[position];

  return (
    <div className={`absolute ${positionClass}`}>
      <div
        className={`flex items-center gap-2 rounded-xl border px-3 py-2 ${
          highlight
            ? 'border-amber-300 bg-emerald-950/85 shadow-[0_0_14px_rgba(253,224,71,0.45)]'
            : 'border-white/20 bg-black/45'
        } ${rotate ? 'rotate-90' : ''}`}
      >
        <div className="flex h-10 w-10 items-center justify-center rounded-md bg-slate-200 text-sm font-bold text-slate-700">
          {wind}
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="text-sm font-semibold text-white">{name}</span>
          <span className="text-sm font-bold text-amber-300">{score}</span>
        </div>
      </div>
    </div>
  );
}

function TableCenter() {
  return (
    <div className="flex h-36 w-44 flex-col items-center justify-center gap-1 rounded-3xl border border-zinc-500 bg-zinc-900/90">
      <span className="text-xl font-bold text-amber-400">东风圈</span>
      <span className="text-5xl font-black text-sky-400">08</span>
      <span className="text-sm font-semibold text-amber-200">剩 52 张</span>
    </div>
  );
}

function HandCards({ cards, activeIndex = 10 }) {
  return (
    <div className="flex items-end gap-1 rounded-xl border border-amber-300/50 bg-amber-200/10 p-2">
      {cards.map((card, index) => (
        <button
          key={`${card}-${index}`}
          type="button"
          className={`flex h-16 w-11 items-center justify-center rounded-md border border-zinc-300 bg-zinc-50 text-lg font-bold text-zinc-800 ${
            index === activeIndex ? '-translate-y-3 shadow-[0_0_0_2px_rgba(252,211,77,0.8)]' : ''
          }`}
        >
          {card}
        </button>
      ))}
    </div>
  );
}

function ActionBar() {
  const actions = [
    { label: '胡', className: 'bg-red-500' },
    { label: '碰', className: 'bg-amber-500' },
    { label: '杠', className: 'bg-green-500' },
    { label: '过', className: 'bg-sky-500' },
  ];

  return (
    <div className="flex items-center gap-3">
      {actions.map((item) => (
        <button
          key={item.label}
          type="button"
          className={`h-12 w-24 rounded-xl text-2xl font-black text-white shadow-lg ${item.className}`}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}

export default function MahjongGameUI() {
  const handCards = ['二', '三', '五', '六', '七', '八', '九', '九', '◉', '◎', 'Ⅲ', '东', '南'];

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 p-4">
      <div className="relative h-[800px] w-[800px] rounded-[28px] bg-gradient-to-br from-amber-900 via-amber-700 to-amber-950 p-8">
        <div className="relative h-[600px] w-[600px] rounded-[24px] bg-gradient-to-b from-emerald-600 to-emerald-800 p-4 shadow-inner shadow-black/50">
          <div className="absolute left-3 top-3 rounded-lg border border-white/10 bg-black/40 px-3 py-2">
            <div className="text-sm font-semibold text-amber-300">血流成河 · 底分100</div>
            <div className="text-xs text-zinc-300">房间号：888888</div>
          </div>

          <Player name="风徐来" score="25,600" wind="北" position="top" />
          <Player name="明月几时有" score="18,400" wind="西" position="left" rotate />
          <Player name="南山南" score="31,200" wind="东" position="right" rotate />
          <Player name="你" score="28,800" wind="南" position="bottom" highlight />

          <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
            <TableCenter />
          </div>

          <div className="absolute bottom-24 left-1/2 -translate-x-1/2">
            <ActionBar />
          </div>

          <div className="absolute bottom-4 left-1/2 -translate-x-1/2">
            <HandCards cards={handCards} />
          </div>
        </div>
      </div>
    </div>
  );
}
