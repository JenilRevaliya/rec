import './globals.css'
import { Inter, Space_Mono } from 'next/font/google'
import type { Metadata } from 'next'

const inter = Inter({ 
  subsets: ['latin'],
  variable: '--font-inter',
})

const spaceMono = Space_Mono({ 
  weight: ['400', '700'],
  subsets: ['latin'],
  variable: '--font-space-mono',
})

export const metadata: Metadata = {
  title: 'REC | Autonomous Event Capture',
  description: 'AI Photography System and Match Portal',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={`${inter.variable} ${spaceMono.variable}`}>
      <body className="antialiased min-h-screen flex flex-col">
        {/* Grain Overlay for Texture */}
        <div className="fixed inset-0 pointer-events-none opacity-[0.03] z-50 bg-[url('https://upload.wikimedia.org/wikipedia/commons/7/76/1k_Dissolve_Noise_Texture.png')] bg-repeat mix-blend-multiply"></div>
        
        {/* Navigation Bar */}
        <nav className="border-b-4 border-black bg-white p-4 sticky top-0 z-40 shadow-neo">
          <div className="max-w-6xl mx-auto flex justify-between items-center">
            <a href="/" className="font-bold text-2xl uppercase tracking-tighter bg-neo-yellow px-2 border-2 border-black shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] hover:translate-x-1 hover:translate-y-1 hover:shadow-none transition-all">
              REC.
            </a>
            <div className="flex gap-4">
              <a href="/admin" className="font-mono font-bold border-2 border-black px-4 py-2 hover:bg-black hover:text-white transition-colors uppercase hidden md:block">
                Admin
              </a>
              <a href="/photographer" className="font-mono font-bold border-2 border-black px-4 py-2 hover:bg-neo-green transition-colors uppercase hidden md:block">
                Studio
              </a>
              <a href="/user" className="font-mono font-bold border-2 border-black px-4 py-2 hover:bg-neo-orange transition-colors uppercase hidden md:block">
                Gallery
              </a>
              <a href="/lab" className="font-mono font-bold border-2 border-black px-4 py-2 hover:bg-neo-blue hover:text-white transition-colors uppercase">
                AI Lab
              </a>
            </div>
          </div>
        </nav>

        <main className="flex-grow">
          {children}
        </main>
      </body>
    </html>
  )
}
