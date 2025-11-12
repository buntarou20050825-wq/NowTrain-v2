import React, { useState, useEffect, useRef } from 'react';

function App() {
  const [trains, setTrains] = useState([]);
  const [stopsMap, setStopsMap] = useState({});
  const [railPaths, setRailPaths] = useState({});
  const [connected, setConnected] = useState(false);
  const [useTheoretical, setUseTheoretical] = useState(true);
  const [stats, setStats] = useState({ total: 0, matched: 0, delayed: 0 });
  const canvasRef = useRef(null);
  const animationFrameRef = useRef(null);

  // Load stops.json
  useEffect(() => {
    fetch('/stops.json')
      .then(r => r.json())
      .then(data => {
        const map = {};
        data.forEach(stop => {
          map[stop.stop_id] = {
            lat: parseFloat(stop.stop_lat),
            lng: parseFloat(stop.stop_lon),
            name: stop.stop_name
          };
        });
        setStopsMap(map);
        console.log('[Stops] Loaded', Object.keys(map).length, 'stops');
      })
      .catch(err => {
        console.error('[Stops] Failed to load:', err);
      });
  }, []);

  // SSE connection
  useEffect(() => {
    const es = new EventSource('http://localhost:8000/api/trains/stream');

    es.addEventListener('snapshot', (e) => {
      const data = JSON.parse(e.data);

      // Rail paths (first time only)
      if (data.rail_paths && Object.keys(railPaths).length === 0) {
        setRailPaths(data.rail_paths);
        console.log('[Rail] Loaded rail paths');
      }

      setTrains(data.vehicles || []);

      // Calculate stats
      const total = data.vehicles?.length || 0;
      const matched = data.vehicles?.filter(t => t.interpolated).length || 0;
      const delayed = data.vehicles?.filter(t => t.delay > 60).length || 0;
      setStats({ total, matched, delayed });
    });

    es.onopen = () => {
      console.log('[SSE] Connected');
      setConnected(true);
    };

    es.onerror = (err) => {
      console.log('[SSE] Disconnected', err);
      setConnected(false);
    };

    return () => {
      es.close();
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, []);

  // Canvas rendering (60fps)
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || trains.length === 0) return;

    const ctx = canvas.getContext('2d');
    const rect = canvas.getBoundingClientRect();

    // Set canvas resolution
    canvas.width = rect.width * window.devicePixelRatio;
    canvas.height = rect.height * window.devicePixelRatio;
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio);

    const animate = () => {
      ctx.clearRect(0, 0, rect.width, rect.height);

      // Calculate positions
      const positions = trains.map(t => {
        if (useTheoretical && t.from_stop_gtfs && t.to_stop_gtfs) {
          return calculateTheoreticalPosition(t);
        }
        return { lat: t.lat, lng: t.lng, train: t };
      }).filter(p => p.lat && p.lng);

      if (positions.length === 0) {
        animationFrameRef.current = requestAnimationFrame(animate);
        return;
      }

      // Calculate map bounds
      const lats = positions.map(p => p.lat);
      const lngs = positions.map(p => p.lng);
      const minLat = Math.min(...lats) - 0.05;
      const maxLat = Math.max(...lats) + 0.05;
      const minLng = Math.min(...lngs) - 0.05;
      const maxLng = Math.max(...lngs) + 0.05;

      const latToY = (lat) => rect.height - ((lat - minLat) / (maxLat - minLat)) * rect.height;
      const lngToX = (lng) => ((lng - minLng) / (maxLng - minLng)) * rect.width;

      // Draw rail paths
      ctx.strokeStyle = '#ccc';
      ctx.lineWidth = 2;
      Object.values(railPaths).forEach(paths => {
        paths.forEach(path => {
          if (path.length < 2) return;
          ctx.beginPath();
          path.forEach((point, i) => {
            const x = lngToX(point.lng);
            const y = latToY(point.lat);
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
          });
          ctx.stroke();
        });
      });

      // Draw trains
      positions.forEach(pos => {
        const train = pos.train;
        const x = lngToX(pos.lng);
        const y = latToY(pos.lat);

        // Color by delay
        let color = '#10B981'; // Green (on time)
        if (train.delay >= 300) color = '#EF4444'; // Red (5+ min)
        else if (train.delay >= 60) color = '#F59E0B'; // Orange (1+ min)

        // Ripple effect
        ctx.beginPath();
        ctx.arc(x, y, 15, 0, Math.PI * 2);
        ctx.strokeStyle = color + '40';
        ctx.lineWidth = 2;
        ctx.stroke();

        // Train dot
        ctx.beginPath();
        ctx.arc(x, y, 6, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 2;
        ctx.stroke();
      });

      animationFrameRef.current = requestAnimationFrame(animate);
    };

    animationFrameRef.current = requestAnimationFrame(animate);

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [trains, stopsMap, railPaths, useTheoretical]);

  function calculateTheoreticalPosition(train) {
    const now = Date.now() / 1000;
    const progress = (now - train.seg_dep_epoch) /
      (train.seg_arr_epoch - train.seg_dep_epoch);
    const clampedProgress = Math.max(0, Math.min(1, progress));

    const fromPos = stopsMap[train.from_stop_gtfs];
    const toPos = stopsMap[train.to_stop_gtfs];

    if (!fromPos || !toPos) {
      return { lat: train.lat, lng: train.lng, train };
    }

    return {
      lat: fromPos.lat + (toPos.lat - fromPos.lat) * clampedProgress,
      lng: fromPos.lng + (toPos.lng - fromPos.lng) * clampedProgress,
      train
    };
  }

  return (
    <div style={{ width: '100vw', height: '100vh', background: '#1a1a1a' }}>
      <div style={{
        padding: '15px 20px',
        background: '#2a2a2a',
        color: '#fff',
        boxShadow: '0 2px 8px rgba(0,0,0,0.3)'
      }}>
        <h1 style={{ fontSize: '24px', marginBottom: '10px' }}>
          JR東日本リアルタイム列車マップ
        </h1>
        <div style={{
          display: 'flex',
          gap: '30px',
          alignItems: 'center',
          fontSize: '14px'
        }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <span style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background: connected ? '#10B981' : '#EF4444',
              display: 'inline-block'
            }}></span>
            {connected ? 'LIVE接続' : '切断'}
          </div>
          <div>
            <strong>{stats.total}</strong> 編成
          </div>
          <div>
            マッチ: <strong>{stats.matched}</strong>/{stats.total}
          </div>
          <div>
            遅延: <strong>{stats.delayed}</strong>
          </div>
          <label style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            cursor: 'pointer'
          }}>
            <input
              type="checkbox"
              checked={useTheoretical}
              onChange={(e) => setUseTheoretical(e.target.checked)}
              style={{ cursor: 'pointer' }}
            />
            理論進捗補間（推奨）
          </label>
        </div>
      </div>
      <canvas
        ref={canvasRef}
        style={{
          width: '100%',
          height: 'calc(100vh - 90px)',
          background: '#f5f5f5'
        }}
      />
    </div>
  );
}

export default App;
