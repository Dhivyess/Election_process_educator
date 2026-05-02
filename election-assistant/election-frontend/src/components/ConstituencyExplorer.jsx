import React, { useState } from 'react';
import { Search, MapPin, Users, HelpCircle } from 'lucide-react';

const CONSTITUENCIES = [
  { id: 1, name: "Gummidipoondi", district: "Thiruvallur", type: "General", voters: "~2.1L" },
  { id: 2, name: "Ponneri", district: "Thiruvallur", type: "SC", voters: "~1.9L" },
  { id: 5, name: "Chennai North", district: "Chennai", type: "General", voters: "~2.4L" },
  { id: 6, name: "Chennai South", district: "Chennai", type: "General", voters: "~2.2L" },
  { id: 102, name: "Coimbatore North", district: "Coimbatore", type: "General", voters: "~2.6L" },
  { id: 103, name: "Coimbatore South", district: "Coimbatore", type: "General", voters: "~2.3L" },
  { id: 168, name: "Madurai Central", district: "Madurai", type: "General", voters: "~1.8L" },
  { id: 220, name: "Trichy West", district: "Trichy", type: "General", voters: "~2.0L" },
  { id: 232, name: "Salem West", district: "Salem", type: "SC", voters: "~1.9L" },
  { id: 234, name: "Vikravandi", district: "Villupuram", type: "General", voters: "~2.2L" },
];

export default function ConstituencyExplorer({ onAsk }) {
  const [query, setQuery] = useState('');

  const filtered = CONSTITUENCIES.filter(c => {
    const q = query.toLowerCase();
    return c.name.toLowerCase().includes(q) || c.district.toLowerCase().includes(q);
  });

  return (
    <div className="explorer-container">
      <div className="explorer-header-section">
        <h2 className="explorer-title">Constituency Explorer</h2>
        <p className="explorer-subtitle">Find your constituency and learn more about its details.</p>
        
        <div className="explorer-search">
          <Search size={18} className="search-icon" />
          <input
            type="text"
            placeholder="Search by constituency name or district..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="search-input"
          />
        </div>
      </div>

      <div className="explorer-grid">
        {filtered.map(c => (
          <div key={c.id} className="constituency-card">
            <div className="card-top">
              <div className="card-title-row">
                <span className="card-id">#{c.id}</span>
                <h3 className="card-name">{c.name}</h3>
              </div>
              <span className={`card-type ${c.type === 'SC' ? 'type-sc' : 'type-general'}`}>{c.type}</span>
            </div>
            
            <div className="card-details">
              <div className="detail-item">
                <MapPin size={15} />
                <span>{c.district}</span>
              </div>
              <div className="detail-item">
                <Users size={15} />
                <span>{c.voters} Voters</span>
              </div>
            </div>

            <button 
              className="ask-btn"
              onClick={() => onAsk(`Tell me about the ${c.name} constituency in ${c.district} district.`)}
            >
              <HelpCircle size={15} />
              <span>Ask about this constituency</span>
            </button>
          </div>
        ))}
        {filtered.length === 0 && (
          <div className="no-results">
            No constituencies found matching "{query}"
          </div>
        )}
      </div>
    </div>
  );
}
