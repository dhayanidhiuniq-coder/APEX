"use client";

import { useEffect, useRef, useState } from "react";

const STORAGE_KEY = "apex-theme";

export function ThemeToggle() {
  const [mounted, setMounted] = useState(false);
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const initialized = useRef(false);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;
    const stored = localStorage.getItem(STORAGE_KEY) as "light" | "dark" | null;
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const initial =
      stored === "light" || stored === "dark" ? stored : prefersDark ? "dark" : "light";
    setTheme(initial);
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted) return;
    document.documentElement.classList.toggle("dark", theme === "dark");
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      // Ignore storage errors
    }
  }, [mounted, theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === "light" ? "dark" : "light"));
  };

  if (!mounted) {
    return (
      <div className="h-9 w-20 rounded-md border border-neutral-300 dark:border-neutral-700" />
    );
  }

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={`Switch to ${theme === "light" ? "dark" : "light"} theme`}
      className="rounded-md border border-neutral-300 px-3 py-1.5 text-sm font-medium transition-colors hover:bg-neutral-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neutral-500 disabled:cursor-not-allowed disabled:opacity-60 dark:border-neutral-700 dark:hover:bg-neutral-800 dark:focus-visible:ring-neutral-400"
    >
      {theme === "light" ? "🌙 Dark" : "☀️ Light"}
    </button>
  );
}
