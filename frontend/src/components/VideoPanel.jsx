import React, { useState } from 'react'

const VideoPanel = React.memo(function VideoPanel({ data, onClose }) {
  const [activeVideo, setActiveVideo] = useState(null)

  if (!data) return null

  const videos = data.videos || []
  const articles = data.articles || []
  const currentVideo = activeVideo || (videos.length > 0 ? videos[0] : null)
  const query = data.query || ''

  return (
    <div className={'video-panel' + (data ? ' open' : '')}>
      <div className="panel-header">
        <h2>VIDEO / NEWS INTEL</h2>
        <button className="panel-close" onClick={onClose}>&times;</button>
      </div>

      {/* YouTube Embed if we have a video */}
      {currentVideo && currentVideo.video_id && (
        <iframe
          className="video-embed"
          src={`https://www.youtube.com/embed/${currentVideo.video_id}?autoplay=1&mute=1`}
          title={currentVideo.title || 'Video'}
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowFullScreen
        />
      )}

      {/* YouTube search embed when no direct video found */}
      {!currentVideo && !data.loading && query && (
        <div style={{ padding: '12px' }}>
          <a
            href={`https://www.youtube.com/results?search_query=${encodeURIComponent(query)}`}
            target="_blank"
            rel="noopener noreferrer"
            className="video-search-link"
          >
            SEARCH YOUTUBE FOR: {query}
          </a>
        </div>
      )}

      {/* Loading state */}
      {data.loading && (
        <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
          SEARCHING INTELLIGENCE...
        </div>
      )}

      {/* Video List */}
      <div className="video-list">
        {videos.length > 0 && (
          <div style={{ padding: '8px 0', fontSize: '11px', color: 'var(--accent)', fontFamily: 'var(--font-mono)', letterSpacing: '1px' }}>
            VIDEOS ({videos.length})
          </div>
        )}
        {videos.map((v, i) => (
          <div
            key={i}
            className="video-item"
            onClick={() => setActiveVideo(v)}
            style={currentVideo === v ? { background: 'var(--bg-active)', borderColor: 'var(--border-accent)' } : {}}
          >
            <div>
              <div className="video-item-title">{v.title || 'Untitled'}</div>
              <div className="video-item-source">{v.source || 'YouTube'} {v.date ? '| ' + v.date : ''}</div>
            </div>
          </div>
        ))}

        {/* News articles — always show when available */}
        {articles.length > 0 && (
          <>
            <div style={{ padding: '12px 0 6px', fontSize: '11px', color: 'var(--accent)', fontFamily: 'var(--font-mono)', letterSpacing: '1px' }}>
              RELATED INTEL ({articles.length})
            </div>
            {articles.map((a, i) => (
              <div
                key={`art-${i}`}
                className="video-item"
                onClick={() => a.url && window.open(a.url, '_blank')}
              >
                <div>
                  <div className="video-item-title">{a.title}</div>
                  <div className="video-item-source">{a.source || 'GDELT'} {a.date ? '| ' + a.date : ''}</div>
                </div>
              </div>
            ))}
          </>
        )}

        {!data.loading && videos.length === 0 && articles.length === 0 && (
          <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '12px' }}>
            No results found. Try clicking a different event.
          </div>
        )}
      </div>
    </div>
  )
})

export default VideoPanel
