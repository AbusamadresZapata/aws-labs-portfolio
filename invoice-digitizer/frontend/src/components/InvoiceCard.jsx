import { useState } from 'react';

export default function InvoiceCard({ invoice }) {
  const [expandedText,  setExpandedText]  = useState(false);
  const [expandedItems, setExpandedItems] = useState(false);

  const isError    = invoice.status === 'error';
  const confidence = Number(invoice.confidence || 0);
  const total      = Number(invoice.total || 0);

  let items = [];
  try {
    const raw = invoice.items_json;
    items = raw ? (typeof raw === 'string' ? JSON.parse(raw) : raw) : [];
  } catch { items = []; }
  const hasItems = items.length > 0;

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
        <div style={{ display:'flex', gap:16, marginTop:10, paddingTop:8, borderTop:'0.5px solid #f0f0f0', flexWrap:'wrap' }}>
          <span style={{ fontSize:11, color:'#888' }}>
            Confianza OCR: <span style={{ color:confColor, fontWeight:500 }}>{confidence.toFixed(0)}%</span>
          </span>
          <span style={{ fontSize:11, color:'#888' }}>Procesado: {dateStr}</span>
          <div style={{ marginLeft:'auto', display:'flex', gap:12 }}>
            {hasItems && (
              <button onClick={() => setExpandedItems(!expandedItems)}
                style={{ fontSize:11, color:'#0066cc', background:'none', border:'none', cursor:'pointer', padding:0 }}>
                {expandedItems ? 'Ocultar productos' : `Ver productos (${items.length})`}
              </button>
            )}
            {invoice.raw_text && (
              <button onClick={() => setExpandedText(!expandedText)}
                style={{ fontSize:11, color:'#888', background:'none', border:'none', cursor:'pointer', padding:0 }}>
                {expandedText ? 'Ocultar texto' : 'Ver texto extraído'}
              </button>
            )}
          </div>
        </div>
      )}

      {expandedItems && hasItems && (
        <div style={{ marginTop:10, overflowX:'auto' }}>
          <table style={{ width:'100%', borderCollapse:'collapse', fontSize:11 }}>
            <thead>
              <tr style={{ borderBottom:'1px solid #e8e8e8', color:'#999' }}>
                <th style={{ textAlign:'right',  padding:'4px 6px', fontWeight:500, whiteSpace:'nowrap' }}>#</th>
                <th style={{ textAlign:'left',   padding:'4px 6px', fontWeight:500, whiteSpace:'nowrap' }}>Referencia</th>
                <th style={{ textAlign:'left',   padding:'4px 6px', fontWeight:500 }}>Producto</th>
                <th style={{ textAlign:'center', padding:'4px 6px', fontWeight:500, whiteSpace:'nowrap' }}>Unidad</th>
                <th style={{ textAlign:'right',  padding:'4px 6px', fontWeight:500, whiteSpace:'nowrap' }}>Cant</th>
                <th style={{ textAlign:'right',  padding:'4px 6px', fontWeight:500, whiteSpace:'nowrap' }}>P.Unit</th>
                <th style={{ textAlign:'right',  padding:'4px 6px', fontWeight:500, whiteSpace:'nowrap' }}>Desc %</th>
                <th style={{ textAlign:'right',  padding:'4px 6px', fontWeight:500, whiteSpace:'nowrap' }}>Total</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item, i) => (
                <tr key={i} style={{ borderBottom:'0.5px solid #f5f5f5' }}>
                  <td style={{ padding:'4px 6px', textAlign:'right',  color:'#aaa' }}>
                    {item.item || '—'}
                  </td>
                  <td style={{ padding:'4px 6px', textAlign:'left',   color:'#888' }}>
                    {item.referencia || '—'}
                  </td>
                  <td style={{ padding:'4px 6px', textAlign:'left',   color:'#333' }}>
                    {item.producto || '—'}
                  </td>
                  <td style={{ padding:'4px 6px', textAlign:'center', color:'#888' }}>
                    {item.unidad || '—'}
                  </td>
                  <td style={{ padding:'4px 6px', textAlign:'right',  color:'#666' }}>
                    {item.cantidad != null ? item.cantidad : '—'}
                  </td>
                  <td style={{ padding:'4px 6px', textAlign:'right',  color:'#666', whiteSpace:'nowrap' }}>
                    {item.precio_unit != null
                      ? `$${Number(item.precio_unit).toLocaleString('es-CO', { minimumFractionDigits:0 })}`
                      : '—'}
                  </td>
                  <td style={{ padding:'4px 6px', textAlign:'right',  color:'#888' }}>
                    {item.descuento_pct != null ? `${item.descuento_pct}%` : '—'}
                  </td>
                  <td style={{ padding:'4px 6px', textAlign:'right',  color:'#333', fontWeight:500, whiteSpace:'nowrap' }}>
                    {item.valor_total != null
                      ? `$${Number(item.valor_total).toLocaleString('es-CO', { minimumFractionDigits:0 })}`
                      : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {expandedText && invoice.raw_text && (
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
