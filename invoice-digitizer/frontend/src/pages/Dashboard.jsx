import { useState, useEffect, useCallback } from 'react';
import { fetchAuthSession } from 'aws-amplify/auth';
import InvoiceCard from '../components/InvoiceCard';

const API              = process.env.REACT_APP_API_ENDPOINT;
const POLL_DELAY_MS    = 20000;
const POLL_INTERVAL_MS = 5000;
const MAX_POLLS        = 6;
const UPLOAD_STEPS     = ['Subiendo', 'Leyendo', 'Analizando'];

async function getToken() {
  const session = await fetchAuthSession();
  const token   = session.tokens?.idToken?.toString();
  if (!token) throw new Error('Sesión expirada');
  return token;
}

export default function Dashboard({ user, onSignOut }) {
  const [invoices,     setInvoices]     = useState([]);
  const [loading,      setLoading]      = useState(true);
  const [uploading,    setUploading]    = useState(false);
  const [uploadStep,   setUploadStep]   = useState(0);
  const [statusMsg,    setStatusMsg]    = useState('');
  const [dragOver,     setDragOver]     = useState(false);
  const [error,        setError]        = useState('');
  const [filterVendor, setFilterVendor] = useState('');
  const [filterDate,   setFilterDate]   = useState('');

  const loadInvoices = useCallback(async () => {
    try {
      const token = await getToken();
      const resp  = await fetch(`${API}/invoices`, {
        method: 'GET',
        headers: { Authorization: token }
      });

      console.log('GET /invoices status:', resp.status);
      if (!resp.ok) {
        const txt = await resp.text();
        console.error('GET /invoices body:', txt);
        throw new Error(`API respondió ${resp.status}: ${txt}`);
      }

      const data = await resp.json();
      setInvoices(data.invoices || []);
      setError('');
    } catch (err) {
      console.error('loadInvoices error:', err);
      setError(`Error cargando historial: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadInvoices(); }, [loadInvoices]);

  async function handleFile(file) {
    if (!file) return;
    const allowed = ['image/jpeg','image/jpg','image/png','image/heic','image/webp'];
    if (!allowed.includes(file.type)) { setError('Solo imágenes JPG, PNG, HEIC o WEBP'); return; }
    if (file.size > 10 * 1024 * 1024) { setError('Máximo 10 MB'); return; }

    setError(''); setUploading(true); setUploadStep(1); setStatusMsg('Obteniendo URL segura...');

    try {
      const token = await getToken();

      const urlResp = await fetch(`${API}/upload-url`, {
        method: 'POST',
        headers: { Authorization: token, 'Content-Type': 'application/json' },
        body: JSON.stringify({ content_type: file.type })
      });
      if (!urlResp.ok) {
        const txt = await urlResp.text();
        throw new Error(`Error obteniendo URL: ${urlResp.status} — ${txt}`);
      }
      const { upload_url, invoice_id } = await urlResp.json();

      setStatusMsg('Subiendo imagen a S3...');
      const s3Resp = await fetch(upload_url, {
        method: 'PUT', body: file, headers: { 'Content-Type': file.type }
      });
      if (!s3Resp.ok) throw new Error(`S3 rechazó el archivo: ${s3Resp.status}`);

      setUploadStep(2); setStatusMsg('Textract leyendo el documento...');
      await sleep(POLL_DELAY_MS);

      setUploadStep(3); setStatusMsg('IA analizando campos...');
      for (let i = 0; i < MAX_POLLS; i++) {
        const r    = await fetch(`${API}/invoices`, { headers: { Authorization: token } });
        const data = await r.json();
        const found = (data.invoices || []).find(inv => inv.invoice_id === invoice_id);
        if (found) {
          setInvoices(data.invoices || []);
          if (found.status === 'error') setError(`OCR falló: ${found.error || 'Error desconocido'}`);
          break;
        }
        if (i < MAX_POLLS - 1) await sleep(POLL_INTERVAL_MS);
      }

    } catch (err) {
      console.error('handleFile error:', err);
      setError(`Error: ${err.message}`);
    } finally {
      setUploading(false); setUploadStep(0); setStatusMsg('');
      await loadInvoices();
    }
  }

  const filteredInvoices = invoices.filter(inv => {
    if (filterVendor) {
      if (!(inv.vendor || '').toLowerCase().includes(filterVendor.toLowerCase())) return false;
    }
    if (filterDate) {
      const invDate = inv.processed_at ? inv.processed_at.slice(0, 10) : '';
      if (invDate < filterDate) return false;
    }
    return true;
  });

  const emailDisplay  = user?.signInDetails?.loginId || user?.username || 'Usuario';
  const activeFilters = filterVendor || filterDate;

  return (
    <div style={{ maxWidth:680, margin:'0 auto', padding:'1.5rem 1rem 3rem' }}>

      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:'1.5rem' }}>
        <div>
          <h1 style={{ fontSize:20, fontWeight:500, marginBottom:2 }}>Mis recibos</h1>
          <p style={{ fontSize:12, color:'#888' }}>{emailDisplay}</p>
        </div>
        <button onClick={onSignOut}
          style={{ fontSize:13, padding:'6px 14px', borderRadius:8, border:'0.5px solid #ccc', background:'transparent', cursor:'pointer', color:'#555' }}>
          Cerrar sesión
        </button>
      </div>

      <div
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={e => { e.preventDefault(); setDragOver(false); handleFile(e.dataTransfer.files[0]); }}
        style={{
          border:`2px dashed ${dragOver ? '#0066cc' : uploading ? '#ccc' : '#bbb'}`,
          borderRadius:12, padding:'2rem 1rem', textAlign:'center',
          marginBottom:'1.5rem', background: dragOver ? '#f0f7ff' : 'transparent',
          transition:'all 0.2s', opacity: uploading ? 0.9 : 1,
        }}
      >
        {uploading ? (
          <div>
            <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'center', marginBottom:16 }}>
              {UPLOAD_STEPS.map((label, idx) => {
                const n      = idx + 1;
                const done   = uploadStep > n;
                const active = uploadStep === n;
                return (
                  <div key={n} style={{ display:'flex', alignItems:'flex-start' }}>
                    <div style={{ display:'flex', flexDirection:'column', alignItems:'center', gap:4, width:76 }}>
                      <div style={{
                        width:28, height:28, borderRadius:'50%',
                        background: done ? '#2e7d32' : active ? '#0066cc' : '#e0e0e0',
                        color: done || active ? '#fff' : '#aaa',
                        display:'flex', alignItems:'center', justifyContent:'center',
                        fontSize:12, fontWeight:600, transition:'background 0.3s',
                      }}>
                        {done ? '✓' : n}
                      </div>
                      <span style={{ fontSize:10, color: active ? '#0066cc' : done ? '#2e7d32' : '#bbb', textAlign:'center', lineHeight:1.3 }}>
                        {label}
                      </span>
                    </div>
                    {idx < UPLOAD_STEPS.length - 1 && (
                      <div style={{ width:24, height:1, background: uploadStep > n ? '#2e7d32' : '#e0e0e0', marginTop:14, flexShrink:0, transition:'background 0.3s' }} />
                    )}
                  </div>
                );
              })}
            </div>
            <p style={{ fontSize:13, color:'#555', margin:0 }}>{statusMsg}</p>
          </div>
        ) : (
          <div>
            <p style={{ fontSize:14, color:'#333', marginBottom:12 }}>
              Arrastra una foto aquí o haz clic para seleccionar
            </p>
            <label style={{
              display:'inline-block', padding:'8px 20px', background:'#0066cc',
              color:'#fff', borderRadius:8, cursor:'pointer', fontSize:14, fontWeight:500,
            }}>
              Subir recibo
              <input type="file" accept="image/*"
                onChange={e => { handleFile(e.target.files[0]); e.target.value=''; }}
                style={{ display:'none' }} />
            </label>
            <p style={{ fontSize:11, color:'#aaa', marginTop:10 }}>JPG · PNG · HEIC · WEBP · máx 10 MB</p>
          </div>
        )}
      </div>

      {error && (
        <div style={{ background:'#fff3f3', border:'0.5px solid #ffcdd2', borderRadius:8,
          padding:'10px 14px', marginBottom:'1rem', fontSize:13, color:'#c62828' }}>
          {error}
          <button onClick={() => setError('')}
            style={{ float:'right', background:'none', border:'none', cursor:'pointer', color:'#c62828', fontSize:16 }}>×</button>
        </div>
      )}

      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:'0.5rem' }}>
        <h2 style={{ fontSize:15, fontWeight:500 }}>
          Historial{' '}
          {!loading && (
            <span style={{ fontWeight:400, color:'#888' }}>
              ({activeFilters && filteredInvoices.length !== invoices.length
                ? `${filteredInvoices.length} de ${invoices.length}`
                : invoices.length})
            </span>
          )}
        </h2>
        <button onClick={loadInvoices} disabled={loading}
          style={{ fontSize:12, color:'#0066cc', background:'none', border:'none', cursor:'pointer', padding:0 }}>
          {loading ? 'Cargando...' : '↻ Actualizar'}
        </button>
      </div>

      {!loading && invoices.length > 0 && (
        <div style={{ display:'flex', gap:8, marginBottom:'0.75rem' }}>
          <input
            placeholder="Buscar por comercio..."
            value={filterVendor}
            onChange={e => setFilterVendor(e.target.value)}
            style={{ flex:1, padding:'6px 10px', borderRadius:8, border:'0.5px solid #ddd', fontSize:13, outline:'none' }}
          />
          <input
            type="date"
            value={filterDate}
            onChange={e => setFilterDate(e.target.value)}
            style={{ padding:'6px 10px', borderRadius:8, border:'0.5px solid #ddd', fontSize:13, outline:'none' }}
          />
          {activeFilters && (
            <button onClick={() => { setFilterVendor(''); setFilterDate(''); }}
              style={{ padding:'6px 12px', borderRadius:8, border:'0.5px solid #ddd', background:'#f5f5f5', cursor:'pointer', fontSize:13, color:'#555', whiteSpace:'nowrap' }}>
              Limpiar
            </button>
          )}
        </div>
      )}

      {loading && <p style={{ fontSize:13, color:'#888', textAlign:'center', padding:'2rem 0' }}>Cargando historial...</p>}

      {!loading && invoices.length === 0 && !error && (
        <div style={{ textAlign:'center', padding:'3rem 0', color:'#aaa' }}>
          <p style={{ fontSize:14 }}>Aún no tienes recibos digitalizados</p>
          <p style={{ fontSize:12, marginTop:4 }}>Sube tu primera foto arriba</p>
        </div>
      )}

      {!loading && invoices.length > 0 && filteredInvoices.length === 0 && (
        <p style={{ fontSize:13, color:'#aaa', textAlign:'center', padding:'1rem 0' }}>
          Ningún recibo coincide con los filtros
        </p>
      )}

      {filteredInvoices.map(inv => <InvoiceCard key={inv.invoice_id} invoice={inv} />)}
    </div>
  );
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
