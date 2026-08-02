const interview = () => {
    return `
    <div class="interview-page" style="min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 40px 20px; background: var(--bg-obsidian);">
        <div class="interview-container" style="width: 100%; max-width: 580px;">

            <!-- Upload Card -->
            <div id="uploadCard" class="glass-card" style="padding: 48px 36px; border-radius: var(--radius-lg); background: var(--bg-card); border: 1px solid var(--border-subtle); backdrop-filter: var(--glass); box-shadow: var(--shadow-md);">
                <h2 style="color: var(--text-primary); font-size: 1.5rem; font-weight: 700; margin-bottom: 8px; text-align: center;">Upload Your Resume</h2>
                <p style="color: var(--text-secondary); font-size: 0.85rem; text-align: center; margin-bottom: 32px;">PDF or plain text. We'll analyze it to personalize your interview.</p>

                <!-- Drop Zone -->
                <div id="dropZone" style="border: 2px dashed var(--border-accent); border-radius: var(--radius-md); padding: 48px 24px; text-align: center; cursor: pointer; transition: var(--transition-smooth);">
                    <div style="font-size: 2.5rem; margin-bottom: 12px;">📄</div>
                    <p style="color: var(--text-secondary); font-size: 0.9rem;">Drag & drop your resume here</p>
                    <p style="color: var(--text-muted); font-size: 0.75rem; margin-top: 6px;">or click to browse</p>
                    <input type="file" id="fileInput" accept=".pdf,.txt,.md" style="display: none;">
                </div>

                <div id="fileName" style="color: var(--accent); font-size: 0.85rem; text-align: center; margin-top: 16px; display: none;"></div>
                <button id="uploadBtn" disabled style="width: 100%; margin-top: 24px; padding: 14px; border-radius: var(--radius-sm); background: var(--accent-dim); color: var(--accent); font-weight: 600; border: 1px solid var(--border-accent); cursor: pointer; transition: var(--transition-smooth); font-size: 0.9rem;">Upload & Analyze</button>
            </div>

            <!-- Loading State -->
            <div id="loadingCard" style="display: none; text-align: center; padding: 60px 36px; border-radius: var(--radius-lg); background: var(--bg-card); border: 1px solid var(--border-subtle); backdrop-filter: var(--glass);">
                <div class="loader" style="width: 40px; height: 40px; border: 3px solid var(--border-subtle); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.8s linear infinite; margin: 0 auto 20px;"></div>
                <p style="color: var(--text-primary); font-size: 1rem;">Analyzing your resume...</p>
            </div>

            <!-- Parsed Confirmation -->
            <div id="parsedCard" style="display: none; padding: 36px; border-radius: var(--radius-lg); background: var(--bg-card); border: 1px solid var(--border-subtle); backdrop-filter: var(--glass);">
                <h3 style="color: var(--text-primary); font-size: 1.2rem; margin-bottom: 20px; text-align: center;">Resume Analyzed ✓</h3>
                <div id="skillsList" style="margin-bottom: 16px;"></div>
                <div id="projectsList" style="margin-bottom: 24px;"></div>
                <button id="startInterviewBtn" style="width: 100%; padding: 16px; border-radius: var(--radius-sm); background: var(--accent); color: var(--bg-obsidian); font-weight: 700; border: none; cursor: pointer; font-size: 1rem; transition: var(--transition-smooth);">Start Voice Interview</button>
            </div>

            <!-- Interview Active -->
            <div id="interviewActive" style="display: none; text-align: center; padding: 60px 36px; border-radius: var(--radius-lg); background: var(--bg-card); border: 1px solid var(--border-accent); backdrop-filter: var(--glass); box-shadow: var(--shadow-glow);">
                <div style="width: 60px; height: 60px; border-radius: 50%; background: var(--accent-dim); border: 2px solid var(--accent); display: flex; align-items: center; justify-content: center; margin: 0 auto 20px; animation: pulse 2s infinite;">
                    <span style="font-size: 1.5rem;">🎤</span>
                </div>
                <p style="color: var(--text-primary); font-size: 1.1rem; font-weight: 600;">Interview in Progress</p>
                <p id="modeStatus" style="color: var(--accent); font-size: 0.85rem; margin-top: 8px;">Mode: Conversation</p>
                <button id="endBtn" style="margin-top: 24px; padding: 10px 24px; border-radius: var(--radius-sm); background: transparent; color: var(--text-secondary); border: 1px solid var(--border-subtle); cursor: pointer; font-size: 0.8rem;">End Interview</button>
            </div>
        </div>
    </div>
    <style>
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.6; } }
        #dropZone:hover, #dropZone.dragover { border-color: var(--accent); background: var(--accent-dim); }
        #uploadBtn:not(:disabled):hover { background: var(--accent); color: var(--bg-obsidian); }
        #startInterviewBtn:hover { box-shadow: var(--shadow-glow); transform: translateY(-1px); }
    </style>
    `;
}

export default interview;
