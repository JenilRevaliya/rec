/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        'neo-bg': '#E5E5E5',
        'neo-yellow': '#F4E85B',
        'neo-orange': '#FF6B35',
        'neo-green': '#A1E44D',
        'neo-blue': '#4D9DE0',
        'neo-purple': '#9370DB',
        'neo-black': '#121212',
      },
      boxShadow: {
        'neo': '4px 4px 0px 0px rgba(18,18,18,1)',
        'neo-lg': '8px 8px 0px 0px rgba(18,18,18,1)',
        'neo-hover': '2px 2px 0px 0px rgba(18,18,18,1)',
      },
      fontFamily: {
        mono: ['var(--font-space-mono)', 'monospace'],
        sans: ['var(--font-inter)', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
