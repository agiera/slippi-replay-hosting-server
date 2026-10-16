export function LivePill({ children }) {
  return (
    <span
      className={
        "inline-flex items-center gap-1.5 rounded-full border border-[rgb(255_90_90/0.5)] bg-live/12 " +
        "px-2 py-px text-[0.68rem] font-bold tracking-[0.08em] text-live-fg"
      }
    >
      <span className="size-[7px] rounded-full bg-live shadow-[0_0_0_3px_rgb(255_59_59/0.2)]" aria-hidden="true" />
      {children}
    </span>
  );
}
