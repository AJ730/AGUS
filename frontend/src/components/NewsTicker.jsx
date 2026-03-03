import React from 'react'

const NewsTicker = React.memo(function NewsTicker({ items }) {
  if (!items || items.length === 0) return null

  // Duplicate items for seamless infinite scroll
  const doubled = [...items, ...items]

  return (
    <div className="news-ticker">
      <span className="ticker-label">LIVE</span>
      <div className="ticker-track">
        <div className="ticker-content">
          {doubled.map((item, i) => (
            <a
              key={i}
              className="ticker-item"
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
            >
              <span className="ticker-source">{item.source}</span>
              {item.title}
            </a>
          ))}
        </div>
      </div>
    </div>
  )
})

export default NewsTicker
