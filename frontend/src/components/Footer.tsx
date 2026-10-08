"use client";

import React from "react";

export function Footer() {
  return (
    <footer className="border-t border-slate-900 bg-slate-950/90 w-full">
      <div className="max-w-7xl w-full mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-5 flex flex-col sm:flex-row items-center justify-between gap-2.5 sm:gap-4 text-xs text-slate-400">
        {/* Left Side: Copyright & FTMS */}
        <div className="text-slate-400">
          <span>&copy; {new Date().getFullYear()} Factory Traffic Management System (FTMS)</span>
        </div>

        {/* Middle: CSI Smart Tech Assessment */}
        <div className="text-slate-500 font-medium">
          Built for CSI Smart Tech Assessment
        </div>

        {/* Right Side: Developed by Arka Karmoker (no github icon) */}
        <div>
          <span className="text-slate-400">Developed by </span>
          <a
            href="https://github.com/ArkaKarmoker"
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-400 hover:text-blue-300 font-semibold transition-colors underline-offset-4 hover:underline"
          >
            Arka Karmoker
          </a>
        </div>
      </div>
    </footer>
  );
}
