"use client";

import React, {
  type ButtonHTMLAttributes,
  type HTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
} from "react";
import Link from "next/link";

type Tone = "light" | "parchment" | "dark" | "dark2" | "dark3";

type TileProps = HTMLAttributes<HTMLElement> & {
  tone?: Tone;
  children: ReactNode;
};

export function GlobalNav({ alertCount = 0 }: { alertCount?: number }) {
  return (
    <header className="h-[44px] bg-[var(--surface-black)] px-4 text-[var(--on-dark)]">
      <div className="mx-auto flex h-full max-w-[390px] items-center justify-between">
        <Link href="/" className="flex items-center gap-2 text-[12px] font-normal tracking-[-0.12px] text-[var(--on-dark)]">
          <span className="inline-flex h-5 w-5 items-center justify-center rounded-[var(--r-xs)] border border-[var(--hairline)] bg-[var(--surface-tile-1)] text-[10px]">
            C
          </span>
          CircleCue
        </Link>
        <Link href="/permissions" className="flex items-center gap-2 text-[12px] tracking-[-0.12px] text-[var(--body-muted)]">
          <span>Alerts</span>
          {alertCount > 0 ? (
            <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-[var(--primary)] px-1 text-[10px] font-semibold text-[var(--on-primary)]">
              {alertCount}
            </span>
          ) : (
            <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-[var(--surface-tile-1)] px-1 text-[10px] text-[var(--body-muted)]">
              0
            </span>
          )}
        </Link>
      </div>
    </header>
  );
}

export function SubNavFrosted({
  title,
  action,
}: {
  title: string;
  action?: ReactNode;
}) {
  return (
    <div className="border-b border-[var(--hairline)] bg-[rgba(245,245,247,0.8)] px-4 py-3 backdrop-blur-md">
      <div className="mx-auto flex max-w-[390px] items-center justify-between gap-3">
        <span className="font-[family-name:var(--font-display)] text-[21px] font-semibold leading-[1.19] tracking-[0.231px] text-[var(--ink)]">
          {title}
        </span>
        {action ?? null}
      </div>
    </div>
  );
}

export function Tile({ tone = "light", children, className = "", ...props }: TileProps) {
  const toneClasses = {
    light: "bg-[var(--canvas)] text-[var(--ink)]",
    parchment: "bg-[var(--canvas-parchment)] text-[var(--ink)]",
    dark: "bg-[var(--surface-tile-1)] text-[var(--body-on-dark)]",
    dark2: "bg-[var(--surface-tile-2)] text-[var(--body-on-dark)]",
    dark3: "bg-[var(--surface-tile-3)] text-[var(--body-on-dark)]",
  };

  return (
    <section
      {...props}
      className={`rounded-[var(--r-lg)] border border-[var(--hairline)] ${toneClasses[tone]} ${className}`}
    >
      {children}
    </section>
  );
}

export function PillButton({
  children,
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "ghost" | "danger";
}) {
  const base =
    "inline-flex min-h-[44px] items-center justify-center rounded-[var(--r-pill)] px-4 py-[11px] text-[17px] leading-[1.24] tracking-[-0.374px] transition-transform active:scale-[0.95] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary-focus)] disabled:opacity-50 disabled:pointer-events-none";
  
  let styles = "bg-[var(--primary)] text-[var(--on-primary)]";
  if (variant === "ghost") {
    styles = "border border-[var(--hairline)] bg-[var(--canvas)] text-[var(--primary)]";
  } else if (variant === "danger") {
    styles = "border border-[var(--danger)] bg-transparent text-[var(--danger)]";
  }

  return (
    <button {...props} type={props.type ?? "button"} className={`${base} ${styles} ${className}`}>
      {children}
    </button>
  );
}

export function UtilityButton({
  children,
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...props}
      type={props.type ?? "button"}
      className={`inline-flex min-h-[36px] items-center justify-center rounded-[var(--r-sm)] bg-[var(--surface-tile-1)] px-3 py-2 text-[14px] font-normal leading-[1.29] tracking-[-0.224px] text-[var(--on-dark)] transition-transform active:scale-[0.95] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary-focus)] ${className}`}
    >
      {children}
    </button>
  );
}

export function Chip({
  selected = false,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { selected?: boolean }) {
  return (
    <button
      {...props}
      type={props.type ?? "button"}
      className={`inline-flex min-h-[36px] items-center justify-center rounded-[var(--r-pill)] border px-3 py-2 text-[14px] font-normal leading-[1.29] tracking-[-0.224px] transition-transform active:scale-[0.95] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary-focus)] ${
        selected
          ? "border-[var(--primary-focus)] bg-[var(--canvas)] text-[var(--ink)] ring-1 ring-[var(--primary-focus)]"
          : "border-[var(--hairline)] bg-[var(--canvas)] text-[var(--ink-muted-80)]"
      }`}
    >
      {children}
    </button>
  );
}

export function UtilityCard({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-[var(--r-lg)] border border-[var(--hairline)] bg-[var(--canvas)] p-4 text-[var(--ink)]">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="text-[17px] font-semibold leading-[1.24] tracking-[-0.374px]">{title}</h3>
          {subtitle ? (
            <p className="mt-1 text-[14px] font-normal leading-[1.43] tracking-[-0.224px] text-[var(--ink-muted-48)]">
              {subtitle}
            </p>
          ) : null}
        </div>
        {action ?? null}
      </div>
    </div>
  );
}

export function SearchInput({
  placeholder = "What's happening?",
  value,
  onChange,
  onFocus,
}: {
  placeholder?: string;
  value?: string;
  onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onFocus?: () => void;
}) {
  return (
    <label className="flex items-center gap-3 rounded-[var(--r-pill)] border border-[var(--hairline)] bg-[var(--canvas)] px-4 py-3 text-[17px] text-[var(--ink-muted-80)] focus-within:ring-2 focus-within:ring-[var(--primary-focus)]">
      <span aria-hidden="true" className="text-[20px] text-[var(--ink-muted-48)]">
        ⌕
      </span>
      <input
        aria-label="Quick composer"
        placeholder={placeholder}
        value={value}
        onChange={onChange}
        onFocus={onFocus}
        className="w-full border-0 bg-transparent text-[17px] leading-[1.47] tracking-[-0.374px] text-[var(--ink)] placeholder:text-[var(--ink-muted-48)] focus:outline-none"
      />
    </label>
  );
}

export function InputField({
  label,
  error,
  className = "",
  ...props
}: InputHTMLAttributes<HTMLInputElement> & {
  label?: string;
  error?: string | null;
}) {
  return (
    <div className="flex flex-col gap-1">
      {label ? (
        <label className="text-[14px] font-normal leading-[1.29] tracking-[-0.224px] text-[var(--ink-muted-80)]">
          {label}
        </label>
      ) : null}
      <input
        {...props}
        className={`min-h-[44px] rounded-[var(--r-md)] border border-[var(--hairline)] bg-[var(--canvas)] px-3 py-2 text-[17px] leading-[1.47] tracking-[-0.374px] text-[var(--ink)] placeholder:text-[var(--ink-muted-48)] focus:outline-none focus:ring-2 focus:ring-[var(--primary-focus)] ${className}`}
      />
      {error ? (
        <span className="text-[12px] text-[var(--danger)]">{error}</span>
      ) : null}
    </div>
  );
}

export function Switch({
  checked = false,
  onChange,
  label,
}: {
  checked?: boolean;
  onChange?: (checked: boolean) => void;
  label?: string;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      {label ? (
        <span className="text-[14px] font-normal leading-[1.29] tracking-[-0.224px] text-[var(--ink-muted-80)]">
          {label}
        </span>
      ) : null}
      <button
        type="button"
        aria-label={label ?? "Toggle switch"}
        aria-pressed={checked}
        onClick={() => onChange?.(!checked)}
        className={`relative inline-flex h-[31px] w-[51px] items-center rounded-[var(--r-pill)] p-1 transition-colors active:scale-[0.95] ${
          checked ? "bg-[var(--primary)]" : "bg-[var(--surface-chip-translucent)]"
        }`}
      >
        <span
          className={`inline-block h-[23px] w-[23px] rounded-full bg-[var(--canvas)] transition-transform ${
            checked ? "translate-x-[20px]" : "translate-x-0"
          }`}
        />
      </button>
    </div>
  );
}

export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { label: string; value: T }[];
  value: T;
  onChange: (val: T) => void;
}) {
  return (
    <div className="inline-flex rounded-[var(--r-md)] border border-[var(--hairline)] bg-[var(--canvas-parchment)] p-1">
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => onChange(opt.value)}
          className={`rounded-[var(--r-sm)] px-3 py-1 text-[13px] font-normal transition-colors active:scale-[0.95] ${
            value === opt.value
              ? "bg-[var(--canvas)] text-[var(--ink)] shadow-sm font-semibold"
              : "text-[var(--ink-muted-80)] hover:text-[var(--ink)]"
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

export function AvatarCircle({
  name,
  url,
  size = 40,
}: {
  name: string;
  url?: string | null;
  size?: number;
}) {
  const initials = name
    .split(" ")
    .map((n) => n[0])
    .slice(0, 2)
    .join("")
    .toUpperCase() || "U";

  if (url) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={url}
        alt={name}
        className="rounded-full object-cover border border-[var(--hairline)]"
        style={{ width: size, height: size }}
      />
    );
  }

  return (
    <div
      className="inline-flex items-center justify-center rounded-full border border-[var(--hairline)] bg-[var(--surface-pearl)] text-[14px] font-semibold text-[var(--ink)]"
      style={{ width: size, height: size }}
    >
      {initials}
    </div>
  );
}

export function SkeletonBlock({ className = "" }: { className?: string }) {
  return (
    <div
      className={`rounded-[var(--r-md)] bg-[var(--canvas-parchment)] border border-[var(--hairline)] animate-pulse ${className}`}
    />
  );
}

export function BottomSheet({
  isOpen,
  onClose,
  title,
  children,
}: {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex flex-col justify-end bg-black/40 backdrop-blur-sm">
      <div className="fixed inset-0" onClick={onClose} />
      <div className="relative z-10 mx-auto flex w-full max-w-[390px] max-h-[85dvh] flex-col rounded-t-[var(--r-xl)] border-t border-[var(--hairline)] bg-[var(--canvas)] p-5 shadow-2xl overflow-hidden">
        <div className="flex items-center justify-between pb-3 border-b border-[var(--hairline)]">
          <h2 className="font-[family-name:var(--font-display)] text-[20px] font-semibold text-[var(--ink)]">
            {title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--canvas-parchment)] text-[var(--ink-muted-80)] active:scale-[0.95]"
          >
            ✕
          </button>
        </div>
        <div className="mt-4 min-h-0 overflow-y-auto overscroll-contain">{children}</div>
      </div>
    </div>
  );
}

export function Footer() {
  return (
    <footer className="pt-6 text-center text-[12px] font-normal leading-[1.3] tracking-[-0.12px] text-[var(--ink-muted-48)]">
      Privacy-first context sharing. No private data leaves your circle without a clear grant.
    </footer>
  );
}

export function ProvenanceCapsule({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-[var(--r-md)] bg-[var(--surface-pearl)] px-2 py-1 text-[12px] font-normal leading-[1.29] tracking-[-0.12px] text-[var(--ink-muted-80)]">
      {children}
    </span>
  );
}

export function BottomNav({ current = "home" }: { current?: "home" | "people" | "alerts" | "me" }) {
  return (
    <nav className="fixed inset-x-0 bottom-0 z-40 mx-auto flex max-w-[390px] items-center justify-around rounded-t-[var(--r-lg)] border-t border-[var(--hairline)] bg-[rgba(245,245,247,0.85)] px-3 py-2 backdrop-blur-md">
      <Link
        href="/"
        className={`flex min-w-[44px] flex-col items-center gap-0.5 text-[11px] ${
          current === "home" ? "text-[var(--primary)] font-semibold" : "text-[var(--ink-muted-48)]"
        }`}
      >
        <span className="text-xl leading-none">⌂</span>
        Home
      </Link>
      <Link
        href="/people"
        className={`flex min-w-[44px] flex-col items-center gap-0.5 text-[11px] ${
          current === "people" ? "text-[var(--primary)] font-semibold" : "text-[var(--ink-muted-48)]"
        }`}
      >
        <span className="text-xl leading-none">◎</span>
        People
      </Link>
      <Link
        href="/permissions"
        className={`flex min-w-[44px] flex-col items-center gap-0.5 text-[11px] ${
          current === "alerts" ? "text-[var(--primary)] font-semibold" : "text-[var(--ink-muted-48)]"
        }`}
      >
        <span className="text-xl leading-none">◌</span>
        Alerts
      </Link>
      <Link
        href="/me"
        className={`flex min-w-[44px] flex-col items-center gap-0.5 text-[11px] ${
          current === "me" ? "text-[var(--primary)] font-semibold" : "text-[var(--ink-muted-48)]"
        }`}
      >
        <span className="text-xl leading-none">☰</span>
        Me
      </Link>
    </nav>
  );
}
