/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  "#fdf4e7",
          100: "#fbe3b8",
          500: "#e8a020",
          600: "#d4891a",
          900: "#7a4a05",
        },
      },
    },
  },
  plugins: [],
}
