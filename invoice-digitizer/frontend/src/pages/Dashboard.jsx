import { useState, useEffect, useCallback } from 'react';
import { fetchAuthSession } from 'aws-amplify/auth';
import { get, post } from 'aws-amplify/api';
import InvoiceCard from '../components/InvoiceCard';

const POLL_DELAY_MS    = 20000;
const POLL_INTERVAL_MS = 5000;
const MAX_POLLS        = 6;

export default function Dashboard({ user, onSignOut }) {
  const [invoices, setInvoices] = useState([]);
  const [loading,  setLoading]  = useState(true);
  const [uploading,setUploading]= useState(false);
  const [statusMsg,setStatusMsg]= useState('');
  const [dragOver, setDragOver] = useState(false);
  const [error,    setError]    = useState('');

  const loadInvoices = useCallback(async () => {
    try {
      const session = await fetchAuthSession();
      const token   = session.tokens?.idToken?.toString();
      const resp    = await get({ apiName: 'InvoiceAPI', path: '/invoices',
                        options: { headers: { Authorization: token } } }).response;
      const data    = await resp.body.json();
      setInvoices(data.invoices || []);
    } catch (err) {
      setError('No se pudo cargar el historial. Intenta recargar la página.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadInvoices(); }, [loadInvoices]);

  async function handleFile(file) {
    if (!file) return;
    const allowed = ['image/jpeg','image/jpg','image/png','image/heic','image/webp'];
    if (!allowed.includes(file.type)) { setError('Solo imágenes JPG, PNG, HEIC o WEBP'); return; }
    if (file.size > 10 * 1024 * 1024) { setError('Máximo 10 MB por imagen'); return; }

    setError(''); setUploading(true); setStatusMsg('Preparando subida segura...');

    try {
      const session = await fetchAuthSession();
      const token   = session.tokens?.idToken?.toString();

      // Paso 1: obtener presigned URL de nuestra API autenticada
      const urlResp = await post({
        apiName: 'InvoiceAPI', path: '/upload-url',
        options: { headers: { Authorization: token }, body: { content_type: file.type } }
      }).response;
      const { upload_url, invoice_id } = await urlResp.body.json();

      setStatusMsg('Subiendo foto...');

      // Paso 2: subir directo a S3 — no pasa por Lambda (más eficiente)
      const s3Resp = await fetch(upload_url, {
        method: 'PUT', body: file, headers: { 'Content-Type': file.type }
      });
      if (!s3Resp.ok) throw new Error(`S3 error: ${s3Resp.status}`);

      setStatusMsg('Procesando con IA... (~20 segundos)');

      // Paso 3: polling hasta que DynamoDB tenga el resultado
      await sleep(POLL_DELAY_MS);
      for (let i = 0; i < MAX_POLLS; i++) {
        setStatusMsg(`Verificando resultado... (${i + 1}/${MAX_POLLS})`);
        const r    = await get({ apiName: 'InvoiceAPI', path: '/invoices',
                       options: { headers: { Authorization: token } } }).response;
        const data = await r.body.json();
        const found = (data.invoices || []).find(inv => inv.invoice_id === invoice_id);
        if (found) {
          setInvoices(data.invoices || []);
          if (found.status === 'error') setError(`OCR falló: ${found.error || 'Error desconocido'}`);
          break;
        }
        if (i < MAX_POLLS - 1) await sleep(POLL_INTERVAL_MS);
      }
    } catch (err) {
      setError(`Error: ${err.message}`);
    } finally {
      setUploading(false); setStatusMsg('');
      await loadInvoices();
    }
  }

  const emailDisplay = user?.signInDetails?.loginId || user?.username || 'Usuario';

  return (
    <div style={{ maxWidth: 680, margin: '0 auto', padding: '1.5rem 1rem 3rem' }}>

      {/* Header */}
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

      {/* Zona de subida */}
      <div
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={e => { e.preventDefault(); setDragOver(false); handleFile(e.dataTransfer.files[0]); }}
        style={{
          border: `2px dashed ${dragOver ? '#0066cc' : uploading ? '#ccc' : '#bbb'}`,
          borderRadius:12, padding:'2rem 1rem', textAlign:'center',
          marginBottom:'1.5rem', background: dragOver ? '#f0f7ff' : 'transparent',
          transition:'all 0.2s', opacity: uploading ? 0.65 : 1,
        }}
      >
        {uploading ? (
          <div>
            <p style={{ fontSize:14, color:'#0066cc', fontWeight:500 }}>{statusMsg}</p>
            <p style={{ fontSize:12, color:'#888', marginTop:6 }}>Textract está leyendo tu recibo</p>
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
              <input type="file" accept="image/*" capture="environment"
                onChange={e => { handleFile(e.target.files[0]); e.target.value=''; }}
                style={{ display:'none' }} />
            </label>
            <p style={{ fontSize:11, color:'#aaa', marginTop:10 }}>JPG · PNG · HEIC · WEBP · máx 10 MB</p>
          </div>
        )}
      </div>

      {/* Error */}
      {error && (
        <div style={{ background:'#fff3f3', border:'0.5px solid #ffcdd2', borderRadius:8,
          padding:'10px 14px', marginBottom:'1rem', fontSize:13, color:'#c62828' }}>
          {error}
          <button onClick={() => setError('')}
            style={{ float:'right', background:'none', border:'none', cursor:'pointer', color:'#c62828', fontSize:16 }}>×</button>
        </div>
      )}

      {/* Historial */}
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:'0.75rem' }}>
        <h2 style={{ fontSize:15, fontWeight:500 }}>Historial {!loading && `(${invoices.length})`}</h2>
        <button onClick={loadInvoices} disabled={loading}
          style={{ fontSize:12, color:'#0066cc', background:'none', border:'none', cursor:'pointer', padding:0 }}>
          {loading ? 'Cargando...' : '↻ Actualizar'}
        </button>
      </div>

      {loading && <p style={{ fontSize:13, color:'#888', textAlign:'center', padding:'2rem 0' }}>Cargando historial...</p>}

      {!loading && invoices.length === 0 && (
        <div style={{ textAlign:'center', padding:'3rem 0', color:'#aaa' }}>
          <p style={{ fontSize:14 }}>Aún no tienes recibos digitalizados</p>
          <p style={{ fontSize:12, marginTop:4 }}>Sube tu primera foto arriba</p>
        </div>
      )}

      {invoices.map(inv => <InvoiceCard key={inv.invoice_id} invoice={inv} />)}
    </div>
  );
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }