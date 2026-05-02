import React, { useState, useEffect } from 'react';
import { AlertTriangle, RefreshCw, Printer, Volume2 } from 'lucide-react';

const CANDIDATES = [
  { id: 1, name_en: "A. Rajkumar", name_ta: "ஏ. ராஜ்குமார்", party_en: "Progressive Party", party_ta: "முற்போக்கு கட்சி", symbol: "☀️" },
  { id: 2, name_en: "B. Lakshmi", name_ta: "பி. லட்சுமி", party_en: "Development Front", party_ta: "வளர்ச்சி முன்னணி", symbol: "🌳" },
  { id: 3, name_en: "C. Murugan", name_ta: "சி. முருகன்", party_en: "Peoples Voice", party_ta: "மக்கள் குரல்", symbol: "🚲" },
  { id: 4, name_en: "D. Karthik", name_ta: "டி. கார்த்திக்", party_en: "United Alliance", party_ta: "ஐக்கிய கூட்டணி", symbol: "🌟" },
  { id: 5, name_en: "NOTA", name_ta: "நோட்டா", party_en: "None of the Above", party_ta: "மேற்கண்ட எவருமில்லை", symbol: "❌" }
];

export default function EVMDemo({ lang }) {
  const [selectedCandidate, setSelectedCandidate] = useState(null);
  const [vvpatTimer, setVvpatTimer] = useState(0);
  const [voteRecorded, setVoteRecorded] = useState(false);
  const [activeBeep, setActiveBeep] = useState(false);

  const t = {
    notice: lang === 'ta' ? "இது ஒரு மாதிரி மட்டுமே. உங்கள் உண்மையான வாக்கு ரகசியமானது மற்றும் பாதுகாப்பானது." : "This is a demo only. Your actual vote is private and secure.",
    ballotUnit: lang === 'ta' ? "வாக்குப்பதிவு இயந்திரம் (Ballot Unit)" : "Ballot Unit",
    vvpat: lang === 'ta' ? "விவிபாட் சாளரம் (VVPAT Window)" : "VVPAT Window",
    candidateList: lang === 'ta' ? "வேட்பாளர் பட்டியல் (Candidate List)" : "Candidate List",
    resultLight: lang === 'ta' ? "முடிவு விளக்கு (Result Light)" : "Result Light",
    recorded: lang === 'ta' ? "வாக்கு வெற்றிகரமாக பதிவு செய்யப்பட்டது" : "Vote recorded successfully",
    reset: lang === 'ta' ? "மீட்டமை" : "Reset EVM",
    voteNow: lang === 'ta' ? "வாக்களிக்க நீல நிற பொத்தானை அழுத்தவும்" : "Press blue button to vote"
  };

  useEffect(() => {
    let interval;
    if (vvpatTimer > 0) {
      interval = setInterval(() => {
        setVvpatTimer(prev => prev - 1);
      }, 1000);
    } else if (selectedCandidate && !voteRecorded) {
      setVoteRecorded(true);
      setActiveBeep(true);
      setTimeout(() => setActiveBeep(false), 2000); // Beep animation for 2 seconds
    }
    return () => clearInterval(interval);
  }, [vvpatTimer, selectedCandidate, voteRecorded]);

  const handleVote = (candidate) => {
    if (selectedCandidate) return; // Prevent multiple votes
    setSelectedCandidate(candidate);
    setVvpatTimer(7);
  };

  const handleReset = () => {
    setSelectedCandidate(null);
    setVvpatTimer(0);
    setVoteRecorded(false);
    setActiveBeep(false);
  };

  return (
    <div className="evm-wrapper">
      <div className="evm-container">
        <div className="evm-notice">
          <AlertTriangle size={18} className="notice-icon" />
          <span>{t.notice}</span>
        </div>

        <div className="evm-machine-layout">
          {/* Ballot Unit */}
          <div className="evm-unit ballot-unit">
            <div className="unit-header">
              <h3 className="unit-title">{t.ballotUnit}</h3>
            </div>
            
            <div className="unit-labels-row">
              <span className="label-text">{t.candidateList}</span>
              <span className="label-text text-right">{t.resultLight}</span>
            </div>

            <div className="evm-buttons-panel">
              {CANDIDATES.map(c => (
                <div key={c.id} className="evm-row">
                  <div className="evm-serial">{c.id}</div>
                  <div className="evm-candidate-info">
                    <div className="evm-name">{lang === 'ta' ? c.name_ta : c.name_en}</div>
                    <div className="evm-party">{lang === 'ta' ? c.party_ta : c.party_en}</div>
                  </div>
                  <div className="evm-symbol">{c.symbol}</div>
                  <div className="evm-light-container">
                    <div className={`evm-light ${(voteRecorded || activeBeep) && selectedCandidate?.id === c.id ? 'glow-red' : ''}`}></div>
                  </div>
                  <button 
                    className={`evm-vote-btn ${selectedCandidate ? 'disabled' : ''}`}
                    onClick={() => handleVote(c)}
                    disabled={selectedCandidate !== null}
                    aria-label={`Vote for ${c.name_en}`}
                  ></button>
                </div>
              ))}
            </div>
          </div>

          {/* VVPAT Unit & Status */}
          <div className="evm-side-panel">
            <div className="evm-unit vvpat-unit">
              <div className="unit-header vvpat-header">
                <Printer size={18} />
                <h3 className="unit-title">{t.vvpat}</h3>
              </div>
              
              <div className="vvpat-screen-bezel">
                <div className="vvpat-screen">
                  {vvpatTimer > 0 ? (
                    <div className="vvpat-slip slip-animation">
                      <div className="slip-symbol">{selectedCandidate.symbol}</div>
                      <div className="slip-name">{lang === 'ta' ? selectedCandidate.name_ta : selectedCandidate.name_en}</div>
                      <div className="slip-party">{lang === 'ta' ? selectedCandidate.party_ta : selectedCandidate.party_en}</div>
                      <div className="slip-timer">{vvpatTimer}s</div>
                    </div>
                  ) : voteRecorded ? (
                    <div className="vvpat-empty">
                      <div className="slip-dropped">Slip secured in box</div>
                    </div>
                  ) : (
                    <div className="vvpat-empty">{t.voteNow}</div>
                  )}
                </div>
              </div>
            </div>

            {(voteRecorded || activeBeep) && (
              <div className={`evm-status ${activeBeep ? 'beeping' : ''}`}>
                <Volume2 size={24} className="beep-icon" />
                <span>{t.recorded}</span>
              </div>
            )}

            {voteRecorded && (
              <button className="evm-reset-btn" onClick={handleReset}>
                <RefreshCw size={16} />
                <span>{t.reset}</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
