import "./App.css";
import VoiceOverlay from "./components/VoiceOverlay";

export default function App() {
  return (
    <div className="app-shell">
      <header className="site-header">
        <a className="wordmark" href="/" aria-label="Nephele home">
          <img src="/nepheleIcon.png" width="32" height="32" alt="" />
          nephele<span className="wordmark-dot">.</span>
        </a>
        <span className="header-caption">YOUR PLACEMENT COMPANION</span>
      </header>
      <main className="main-layout">
        <section className="companion" aria-label="Meet Nephele">
          <div className="companion-orbit" aria-hidden="true" />
          <div className="video-frame">
            <img
              className="companion-art"
              src="/nepheleIcon.png"
              alt="Nephele, a friendly blue robot"
            />
            <div className="video-shade" />
            <div className="companion-caption">
              <span className="eyebrow">A VOICE IN YOUR CORNER</span>
              <h2>Meet Nephele.</h2>
              <p>Practice. Ask. Find your next step.</p>
            </div>
          </div>
          <div className="companion-tags">
            <span>Interview prep</span>
            <span>Resume advice</span>
            <span>Career clarity</span>
          </div>
          <details className="original-animation">
            <summary>View Nephele's original animation</summary>
            <video
              controls
              loop
              muted
              playsInline
              preload="none"
              aria-label="Original Nephele face animation"
            >
              <source src="/nepheletrimmed.mp4" type="video/mp4" />
            </video>
          </details>
        </section>
        <VoiceOverlay />
      </main>
      <footer className="site-footer">
        <span>Built by The Cloud PeP Students</span>
        <span>Tech leads: Saravana &amp; Joshua</span>
      </footer>
    </div>
  );
}
