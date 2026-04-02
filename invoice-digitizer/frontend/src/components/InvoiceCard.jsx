import { useState } from 'react';

export default function InvoiceCard({ invoice }) {
  const [expanded, setExpanded] = useState(false);
  const isError   = invoice.status === 'error';
  const confidence = Number(invoice.confidence || 0);
  const total      = Number(invoice.total || 0);

  const confColor = confidence >= 85 ? '#2e7d32' : confidence >= 65 ? '#f57c00' : '#c62828';
  const dateStr   = new Date(invoice.processed_at).toLocaleDateString('es-CO',
                    { day:'2-digit', month:'short', year:'numeric' });
  const timeStr   = new Date(invoice.processed_at).toLocaleTimeString('es-CO',
                    { hour:'2-digit', minute:'2-digit' });

  return (
    <div style={{
      background:'#fff', border:`0.5px solid ${isError ? '#ffcdd2' : '#e0e0e0'}`,
      borderRadius:10, padding:'14px 16px', marginBottom:'0.65rem',
    }}>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start' }}>
        <div style={{ flex:1, minWidth:0 }}>
          <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:4 }}>
            <span style={{ fontSize:14, fontWeight:500, color: isError ? '#c62828' : '#222',
              overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
              {invoice.vendor !== 'N/A' ? invoice.vendor : 'Comercio no detectado'}
            </span>
            {isError && (
              <span style={{ fontSize:10, background:'#ffebee', color:'#c62828',
                borderRadius:4, padding:'1px 6px', flexShrink:0 }}>Error OCR</span>
            )}
          </div>
          <div style={{ fontSize:12, color:'#888' }}>
            {invoice.invoice_number !== 'N/A' && `# ${invoice.invoice_number} · `}
            {invoice.date !== 'N/A' ? invoice.date : dateStr}
            {invoice.items_count > 0 && ` · ${invoice.items_count} producto${invoice.items_count !== 1 ? 's' : ''}`}
          </div>
        </div>
        <div style={{ textAlign:'right', marginLeft:12, flexShrink:0 }}>
          {!isError && total > 0
            ? <div style={{ fontSize:16, fontWeight:500, color:'#0066cc' }}>
                ${total.toLocaleString('es-CO', { minimumFractionDigits:0 })}
              </div>
            : <div style={{ fontSize:12, color:'#aaa' }}>Sin total</div>
          }
          <div style={{ fontSize:11, color:'#aaa', marginTop:2 }}>{timeStr}</div>
        </div>
      </div>

      {!isError && (
        <div style={{ display:'flex', gap:16, marginTop:10, paddingTop:8, borderTop:'0.5px solid #f0f0f0' }}>
          <span style={{ fontSize:11, color:'#888' }}>
            Confianza OCR: <span style={{ color:confColor, fontWeight:500 }}>{confidence.toFixed(0)}%</span>
          </span>
          <span style={{ fontSize:11, color:'#888' }}>Procesado: {dateStr}</span>
          {invoice.raw_text && (
            <button onClick={() => setExpanded(!expanded)}
              style={{ fontSize:11, color:'#0066cc', background:'none', border:'none', cursor:'pointer', padding:0, marginLeft:'auto' }}>
              {expanded ? 'Ocultar texto' : 'Ver texto extraído'}
            </button>
          )}
        </div>
      )}

      {expanded && invoice.raw_text && (
        <div style={{ marginTop:10, padding:'10px 12px', background:'#f8f8f8',
          borderRadius:6, fontSize:12, fontFamily:'monospace', whiteSpace:'pre-wrap',
          color:'#444', maxHeight:200, overflowY:'auto', lineHeight:1.6 }}>
          {invoice.raw_text}
        </div>
      )}

      {isError && invoice.error && (
        <div style={{ fontSize:12, color:'#c62828', marginTop:8 }}>{invoice.error}</div>
      )}
    </div>
  );
}