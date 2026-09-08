/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bgPrimary: '#F8F9FC',
        bgCard: '#FFFFFF',
        bgCardAlt: '#F0F4FF',
        accentPrimary: '#2563EB',
        accentSecondary: '#0EA5E9',
        accentSuccess: '#10B981',
        accentWarning: '#F59E0B',
        accentDanger: '#EF4444',
        textPrimary: '#0F172A',
        textSecondary: '#64748B',
        textMuted: '#94A3B8',
        border: '#E2E8F0',
        bg: '#F8F9FC',
        text: '#0F172A',
        muted: '#94A3B8',
        primary: '#2563EB',
        danger: '#EF4444',
        success: '#10B981',
        warning: '#F59E0B',
      },
      fontFamily: {
        display: ['"DM Sans"', 'sans-serif'],
        body: ['"IBM Plex Sans"', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'monospace'],
      },
      boxShadow: {
        card: '0 1px 3px rgba(0,0,0,0.06), 0 4px 16px rgba(0,0,0,0.04)',
      }
    },
  },
  plugins: [],
}