import React, { useState } from 'react';
import { ExternalLink, CheckCircle } from 'lucide-react';

const CHECKLIST_ITEMS = {
  en: [
    { title: "Check name on voter list", desc: "Verify your enrollment in the electoral roll.", link: "https://electoralsearch.in" },
    { title: "Download e-EPIC / keep Voter ID ready", desc: "Ensure you have your digital or physical Voter ID.", link: "https://voters.eci.gov.in/" },
    { title: "Know your polling booth location", desc: "Find exactly where you need to go to cast your vote." },
    { title: "Prepare a valid alternate photo ID", desc: "Aadhaar, PAN, or Passport are valid alternatives if needed." },
    { title: "Note polling day: April 23, 2026, 7 AM – 6 PM", desc: "Mark your calendar and plan your day." },
    { title: "Check candidate list", desc: "Review the candidates running in your constituency.", link: "https://myneta.info" },
    { title: "Report MCC violations via cVIGIL app", desc: "Help ensure a fair election by reporting violations." },
    { title: "Help a family member register if needed", desc: "Assist others in exercising their democratic right." }
  ],
  ta: [
    { title: "வாக்காளர் பட்டியலில் பெயரைச் சரிபார்க்கவும்", desc: "வாக்காளர் பட்டியலில் உங்கள் பெயர் உள்ளதா என உறுதிப்படுத்தவும்.", link: "https://electoralsearch.in" },
    { title: "e-EPIC ஐப் பதிவிறக்கவும் / வாக்காளர் அடையாள அட்டையை தயாராக வைத்திருக்கவும்", desc: "உங்கள் டிஜிட்டல் அல்லது நேரடி வாக்காளர் அடையாள அட்டை இருப்பதை உறுதிப்படுத்தவும்.", link: "https://voters.eci.gov.in/" },
    { title: "உங்கள் வாக்குச்சாவடி இருப்பிடத்தை அறியவும்", desc: "நீங்கள் வாக்களிக்க எங்கு செல்ல வேண்டும் என்பதைத் தெரிந்து கொள்ளவும்." },
    { title: "செல்லுபடியாகும் மாற்று அடையாள அட்டையைத் தயார் செய்யவும்", desc: "தேவைப்பட்டால் ஆதார், பான் அல்லது பாஸ்போர்ட் பயன்படுத்தலாம்." },
    { title: "வாக்குப்பதிவு நாள்: ஏப்ரல் 23, 2026, காலை 7 – மாலை 6", desc: "தேதியை குறித்து வைத்து உங்கள் நாளைத் திட்டமிடுங்கள்." },
    { title: "வேட்பாளர் பட்டியலைச் சரிபார்க்கவும்", desc: "உங்கள் தொகுதியில் போட்டியிடும் வேட்பாளர்களைப் பற்றி அறியவும்.", link: "https://myneta.info" },
    { title: "cVIGIL செயலி மூலம் விதிமீறல்களைப் புகாரளிக்கவும்", desc: "விதிமீறல்களைப் புகாரளிப்பதன் மூலம் நியாயமான தேர்தலை உறுதிப்படுத்த உதவுங்கள்." },
    { title: "தேவைப்பட்டால் குடும்ப உறுப்பினர் பதிவு செய்ய உதவவும்", desc: "மற்றவர்களும் தங்கள் ஜனநாயக உரிமையைப் பயன்படுத்த உதவுங்கள்." }
  ]
};

export default function VoterChecklist({ lang }) {
  const items = CHECKLIST_ITEMS[lang] || CHECKLIST_ITEMS.en;
  const [checkedState, setCheckedState] = useState(new Array(items.length).fill(false));

  const handleToggle = (position) => {
    const updatedCheckedState = checkedState.map((item, index) =>
      index === position ? !item : item
    );
    setCheckedState(updatedCheckedState);
  };

  const checkedCount = checkedState.filter(Boolean).length;
  const totalCount = items.length;
  const progressPercentage = Math.round((checkedCount / totalCount) * 100);

  return (
    <div className="checklist-container">
      <div className="checklist-header-section">
        <h2 className="checklist-title">
          {lang === 'ta' ? 'வாக்காளர் தயார்நிலை சரிபார்ப்பு பட்டியல்' : 'Voter Readiness Checklist'}
        </h2>
        <p className="checklist-subtitle">
          {lang === 'ta' ? 'எதிர்வரும் தேர்தலுக்கு நீங்கள் தயாராக உள்ளீர்களா என்பதை உறுதிப்படுத்தவும்.' : 'Ensure you are fully prepared for the upcoming elections.'}
        </p>

        <div className="progress-section">
          <div className="progress-bar-container">
            <div 
              className="progress-bar-fill" 
              style={{ width: `${progressPercentage}%` }}
            ></div>
          </div>
          <div className="progress-text">
            {checkedCount} / {totalCount} {lang === 'ta' ? 'முடிந்தது' : 'complete'}
          </div>
        </div>

        {checkedCount === totalCount && (
          <div className="congrats-banner">
            <CheckCircle size={20} className="congrats-icon" />
            <span>
              {lang === 'ta' ? "நீங்கள் தேர்தலுக்குத் தயார்! 🗳️" : "You're election-ready! 🗳️"}
            </span>
          </div>
        )}
      </div>

      <div className="checklist-items">
        {items.map((item, index) => (
          <div 
            key={index} 
            className={`checklist-item ${checkedState[index] ? 'checked' : ''}`}
            onClick={() => handleToggle(index)}
          >
            <div className="checkbox-wrapper">
              <input 
                type="checkbox" 
                className="checklist-checkbox"
                checked={checkedState[index]}
                onChange={() => handleToggle(index)}
                onClick={(e) => e.stopPropagation()}
              />
            </div>
            <div className="item-content">
              <h3 className="item-title">{item.title}</h3>
              <p className="item-desc">{item.desc}</p>
              {item.link && (
                <a 
                  href={item.link} 
                  target="_blank" 
                  rel="noopener noreferrer" 
                  className="item-link"
                  onClick={(e) => e.stopPropagation()}
                >
                  {lang === 'ta' ? 'இணைப்பிற்குச் செல்லவும்' : 'Visit Link'} <ExternalLink size={14} />
                </a>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
