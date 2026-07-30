import { Camera, Search, ArrowRight, Zap, Image as ImageIcon, Check } from 'lucide-react'

export default function Home() {
  return (
    <div className="flex-grow flex flex-col items-center">
      
      {/* Navigation */}
      <nav className="w-full max-w-7xl px-6 py-6 flex justify-between items-center border-b-4 border-neo-black bg-white">
        <div className="flex items-center gap-3">
          <div className="bg-neo-orange text-white p-2 border-2 border-neo-black shadow-[2px_2px_0px_black]">
            <Camera size={28} strokeWidth={2.5} />
          </div>
          <span className="font-mono font-bold text-3xl uppercase tracking-tighter">REC.</span>
        </div>
        <div className="hidden md:flex gap-8 font-bold uppercase tracking-wide">
          <a href="#how" className="hover:text-neo-orange transition-colors">How it works</a>
          <a href="#gallery" className="hover:text-neo-blue transition-colors">Gallery</a>
        </div>
        <button className="neo-btn bg-neo-green text-sm flex items-center gap-2">
          Find My Photos <Search size={16} />
        </button>
      </nav>

      {/* Hero Section */}
      <main className="w-full max-w-7xl px-6 py-20 md:py-32 grid grid-cols-1 md:grid-cols-12 gap-8 md:gap-16 items-center">
        
        {/* Left Column - Typographic Focus */}
        <div className="md:col-span-7 flex flex-col items-start space-y-8">
          <div className="inline-block bg-neo-yellow border-2 border-neo-black px-4 py-2 font-mono font-bold uppercase shadow-neo-hover transform -rotate-2">
            Autonomous AI Photography
          </div>
          
          <h1 className="text-6xl md:text-8xl font-black uppercase leading-[0.9] tracking-tighter">
            Never Miss <br/>
            <span className="text-neo-orange drop-shadow-[4px_4px_0_black]">The Moment</span>
          </h1>
          
          <p className="text-xl md:text-2xl font-medium max-w-xl leading-relaxed border-l-4 border-neo-black pl-6">
            Intelligent cameras capture you from every angle. Upload a selfie and our AI instantly finds all your high-quality event photos.
          </p>
          
          <div className="flex flex-col sm:flex-row gap-6 pt-4 w-full sm:w-auto">
            <button className="neo-btn bg-neo-orange text-white flex-1 sm:flex-none text-xl py-4 flex justify-center items-center gap-3 group">
              Upload Selfie
              <ArrowRight className="group-hover:translate-x-2 transition-transform" />
            </button>
            <button className="neo-btn bg-white flex-1 sm:flex-none text-xl py-4 flex justify-center items-center gap-3">
              Explore Demo
            </button>
          </div>
        </div>

        {/* Right Column - Broken Grid / Imagery */}
        <div className="md:col-span-5 relative h-full min-h-[400px]">
          {/* Abstract geometric composition instead of generic images */}
          <div className="absolute top-10 left-10 w-full h-full bg-neo-blue border-4 border-neo-black shadow-neo-lg z-0"></div>
          
          <div className="absolute top-0 left-0 w-full h-full bg-white border-4 border-neo-black shadow-neo-lg z-10 p-8 flex flex-col justify-between">
            <div className="flex justify-between items-start">
              <span className="font-mono text-4xl font-bold">01</span>
              <Zap size={48} className="text-neo-yellow fill-neo-yellow" />
            </div>
            <div>
              <h3 className="text-3xl font-black uppercase mb-4 leading-none">Instant<br/>Matching</h3>
              <div className="h-4 w-full bg-neo-bg border-2 border-neo-black relative overflow-hidden">
                <div className="absolute top-0 left-0 h-full w-3/4 bg-neo-green border-r-2 border-neo-black"></div>
              </div>
            </div>
          </div>

          {/* Floating Element */}
          <div className="absolute -bottom-8 -left-8 bg-neo-orange border-4 border-neo-black shadow-neo p-4 z-20 flex items-center gap-3 transform rotate-3">
            <ImageIcon size={32} className="text-white" />
            <span className="font-bold text-white uppercase text-lg tracking-wide">10,000+ Captures</span>
          </div>
        </div>
      </main>

      {/* Value Props - Asymmetric Marquee / Grid */}
      <section id="how" className="w-full bg-neo-black text-white py-24 border-y-4 border-neo-black">
        <div className="max-w-7xl mx-auto px-6 grid grid-cols-1 md:grid-cols-3 gap-12">
          
          <div className="flex flex-col gap-6">
            <div className="w-16 h-16 bg-neo-green text-neo-black flex items-center justify-center font-black text-3xl border-2 border-white transform -rotate-6">1</div>
            <h3 className="text-3xl font-bold uppercase">Smart Capture</h3>
            <p className="text-gray-300 font-medium text-lg leading-relaxed">
              Our PTZ cameras track faces, calculate optimal angles, and trigger the shutter only when the composition is perfect. No blurry shots.
            </p>
          </div>

          <div className="flex flex-col gap-6 md:translate-y-12">
            <div className="w-16 h-16 bg-neo-blue text-white flex items-center justify-center font-black text-3xl border-2 border-white transform rotate-3">2</div>
            <h3 className="text-3xl font-bold uppercase">Fairness Engine</h3>
            <p className="text-gray-300 font-medium text-lg leading-relaxed">
              We ensure everyone gets covered. The AI intelligently prioritizes guests who haven't been photographed yet.
            </p>
          </div>

          <div className="flex flex-col gap-6">
            <div className="w-16 h-16 bg-neo-yellow text-neo-black flex items-center justify-center font-black text-3xl border-2 border-white transform -rotate-3">3</div>
            <h3 className="text-3xl font-bold uppercase">Deep Re-ID</h3>
            <p className="text-gray-300 font-medium text-lg leading-relaxed">
              AuraFace embedding vectors map your facial structure to instantly retrieve all your photos across thousands of event captures.
            </p>
          </div>

        </div>
      </section>

    </div>
  )
}
