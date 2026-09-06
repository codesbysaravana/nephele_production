import './App.css'
import VoiceOverlay from './components/VoiceOverlay'

function App() {
  return (
    <div style={{ position: 'relative', width: '100%', height: '100dvh', overflow: 'hidden', background: '#000' }}>

      {/* Full-screen Nephele video */}
      <video
        autoPlay
        loop
        muted
        playsInline
        style={{
          position: 'absolute',
          inset: 0,
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          objectPosition: 'center top',
          zIndex: 0,
        }}
      >
        <source src="/nepheletrimmed.mp4" type="video/mp4" />
      </video>

      {/* Subtle bottom gradient so the mic button stands out */}
      <div
        style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          height: '220px',
          background: 'linear-gradient(to top, rgba(0,0,0,0.65) 0%, transparent 100%)',
          zIndex: 1,
          pointerEvents: 'none',
        }}
      />

      {/* Voice overlay on top of everything */}
      <div style={{ position: 'relative', zIndex: 10 }}>
        <VoiceOverlay />
      </div>

    </div>
  )
}

export default App
