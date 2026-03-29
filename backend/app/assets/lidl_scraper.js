/**
 * LIDL eBon Scraper — Paste into browser console while logged into lidl.de
 *
 * Works on any lidl.de page while you're logged into your Lidl Plus account.
 * Fetches all receipts via the internal API and downloads a JSON file.
 */
(async function lidlScraper() {
  const DELAY_MS = 600;
  const API_BASE = '/mre/api/v1';

  function sleep(ms) {
    return new Promise(r => setTimeout(r, ms));
  }

  /** Strip escaped/extra quotes from API attribute values */
  function clean(s) {
    if (!s) return '';
    return s.replace(/^["\\]+|["\\]+$/g, '').trim();
  }

  function parseGermanDecimal(s) {
    if (!s) return 0;
    const cleaned = clean(s).replace(',', '.');
    const num = parseFloat(cleaned);
    return isNaN(num) ? 0 : num;
  }

  /**
   * Parse receipt HTML (the styled <pre> block with data-* attributes).
   */
  function parseReceiptHtml(html, transactionId) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');

    const headerSpans = doc.querySelectorAll('.header span[class*="css_bold"]');
    const addressParts = [];
    headerSpans.forEach(s => {
      const text = s.textContent.trim();
      if (text) addressParts.push(text);
    });

    const items = [];
    const articleMap = new Map();
    doc.querySelectorAll('[data-art-id]').forEach(span => {
      const desc = span.dataset.artDescription || '';
      const artId = span.dataset.artId || '';
      const key = `${artId}|||${desc}`;
      if (!articleMap.has(key)) {
        articleMap.set(key, {
          description: desc,
          unit_price: span.dataset.unitPrice || '0',
          quantity: span.dataset.artQuantity || '',
          tax_type: span.dataset.taxType || 'B',
        });
      }
    });

    for (const [, data] of articleMap) {
      const unitPrice = parseGermanDecimal(data.unit_price);
      const qty = data.quantity ? parseGermanDecimal(data.quantity) : 0;
      let totalPrice;
      let quantity = null;

      if (qty > 0) {
        totalPrice = Math.round(qty * unitPrice * 100) / 100;
        quantity = data.quantity;
      } else {
        totalPrice = unitPrice;
      }

      items.push({
        description: data.description,
        unit_price: data.unit_price,
        total_price: totalPrice.toFixed(2).replace('.', ','),
        quantity: quantity,
        tax_type: data.tax_type,
      });
    }

    const discounts = [];
    const seenPromotions = new Set();
    doc.querySelectorAll('[data-promotion-id]').forEach(span => {
      const promoId = clean(span.dataset.promotionId || '');
      if (!promoId || seenPromotions.has(promoId)) return;
      seenPromotions.add(promoId);
      let amount = '0', description = 'Lidl Plus Rabatt';
      doc.querySelectorAll(`[data-promotion-id]`).forEach(bs => {
        const pid = clean(bs.dataset.promotionId || '');
        if (pid !== promoId) return;
        if (!bs.classList.contains('css_bold')) return;
        const text = bs.textContent.trim();
        if (text.match(/^-?\d+[.,]\d{2}$/)) amount = text.replace('-', '');
        else if (text.length > 3) description = text.trim();
      });
      if (parseGermanDecimal(amount) > 0) {
        discounts.push({ description, amount, promotion_id: promoId });
      }
    });

    let totalAmount = '0';
    doc.querySelectorAll('#purchase_summary_2').forEach(span => {
      if (span.classList.contains('css_bold')) {
        const text = span.textContent.trim();
        if (text.match(/^\d+[.,]\d{2}$/)) totalAmount = text;
      }
    });

    let paymentMethod = '';
    const tender = doc.querySelectorAll('[data-tender-description]');
    if (tender.length > 0) paymentMethod = clean(tender[0].dataset.tenderDescription || '');

    let rawDatetime = '', belegNr = '', tseTransaction = '';

    // TSE Transaktionsnummer from return_code_line_2
    const rc2Spans = doc.querySelectorAll('[id="return_code_line_2"].css_bold');
    rc2Spans.forEach(span => {
      const text = span.textContent.trim();
      if (text.match(/^\d+$/) && text.length > 3) tseTransaction = text;
    });

    // Date/time from return_code_line_13: "3405   004385/85  05.03.26 15:10"
    const rc13Spans = doc.querySelectorAll('[id="return_code_line_13"].css_bold');
    if (rc13Spans.length >= 4) {
      // Last two bold spans are date and time
      rawDatetime = `${rc13Spans[rc13Spans.length - 2].textContent.trim()} ${rc13Spans[rc13Spans.length - 1].textContent.trim()}`;
    }

    // Fallback: ISO timestamps from line 11/12
    if (!rawDatetime) {
      const rc11 = doc.querySelector('[id="return_code_line_11"].css_bold');
      if (rc11) {
        const ts = rc11.textContent.trim();
        if (ts.match(/^\d{4}-\d{2}-\d{2}T/)) rawDatetime = ts;
      }
    }

    // Beleg-Nr from purchase_tender_information_8: "TA-Nr. 004104  Beleg-Nr. 3939"
    const pti8 = doc.querySelector('[id="purchase_tender_information_8"].css_bold');
    if (pti8) {
      const match = pti8.textContent.match(/Beleg-Nr\.\s*(\d+)/);
      if (match) belegNr = match[1];
    }

    return {
      transaction_id: transactionId,
      store_address: addressParts.join(', '),
      total_amount: totalAmount,
      payment_method: paymentMethod,
      raw_datetime: rawDatetime,
      tse_transaction: tseTransaction,
      beleg_nr: belegNr,
      items,
      discounts,
    };
  }

  // --- Step 1: Get all ticket IDs via paginated list API ---
  console.log('%c[LIDL Scraper] Starting...', 'color: #00b0f0; font-weight: bold;');

  const transactionIds = [];
  let page = 1;
  let hasMore = true;

  while (hasMore) {
    const listUrl = `${API_BASE}/tickets?country=DE&page=${page}`;
    console.log(`[LIDL Scraper] Fetching ticket list page ${page}...`);

    try {
      const res = await fetch(listUrl, { credentials: 'include' });
      if (!res.ok) { hasMore = false; break; }
      const text = await res.text();
      let foundOnPage = 0;

      try {
        const json = JSON.parse(text);
        const tickets = json.tickets || json.records || json.items || json.data || json.results || json;
        if (Array.isArray(tickets)) {
          for (const ticket of tickets) {
            const id = String(ticket.id || ticket.ticketId || ticket.transactionId || ticket.t || '');
            if (id && !transactionIds.includes(id)) {
              transactionIds.push(id);
              foundOnPage++;
            }
          }
        }
        if (foundOnPage === 0) {
          const matches = [...JSON.stringify(json).matchAll(/["'](\d{15,})["']/g)];
          for (const m of matches) {
            if (!transactionIds.includes(m[1])) { transactionIds.push(m[1]); foundOnPage++; }
          }
        }
        const totalPages = json.totalPages || json.total_pages || json.pageCount;
        if (totalPages && page >= totalPages) hasMore = false;
        else if (foundOnPage === 0) hasMore = false;
      } catch {
        const matches = [...text.matchAll(/[?&]t=([^&"']+)/g)];
        for (const m of matches) {
          if (!transactionIds.includes(m[1])) { transactionIds.push(m[1]); foundOnPage++; }
        }
        if (foundOnPage === 0) hasMore = false;
      }

      console.log(`  Found ${foundOnPage} receipts on page ${page}`);
      if (foundOnPage === 0) hasMore = false;
      page++;
      await sleep(DELAY_MS);
    } catch (e) {
      console.error(`[LIDL Scraper] Error:`, e.message);
      hasMore = false;
    }
  }

  if (transactionIds.length === 0) {
    console.warn('%c[LIDL Scraper] No receipts found via API.', 'color: #ff6600;');
    return;
  }

  console.log(`%c[LIDL Scraper] Found ${transactionIds.length} receipts total`, 'color: #00b0f0; font-weight: bold;');

  // --- Step 2: Fetch each receipt ---
  const receipts = [];

  for (let i = 0; i < transactionIds.length; i++) {
    const tid = transactionIds[i];
    console.log(`[LIDL Scraper] Fetching ${i + 1}/${transactionIds.length}...`);

    try {
      const url = `${API_BASE}/tickets/${tid}?country=DE&languageCode=de-DE`;
      const res = await fetch(url, { credentials: 'include' });
      let html = await res.text();

      // If the response is JSON-wrapped HTML, extract the HTML string
      if (html.trim().startsWith('{') || html.trim().startsWith('"')) {
        try {
          const parsed = JSON.parse(html);
          if (typeof parsed === 'string') {
            html = parsed;
          } else if (typeof parsed === 'object' && parsed !== null) {
            // Search all values (recursively) for a string containing receipt HTML
            function findHtml(obj) {
              for (const val of Object.values(obj)) {
                if (typeof val === 'string' && val.includes('data-art-id')) return val;
                if (typeof val === 'object' && val !== null) {
                  const found = findHtml(val);
                  if (found) return found;
                }
              }
              return null;
            }
            const found = findHtml(parsed);
            if (found) html = found;
          }
        } catch { /* not JSON, use as-is */ }
      }

      if (html.includes('data-art-id') || html.includes('purchase_list')) {
        const receipt = parseReceiptHtml(html, tid);
        receipts.push(receipt);
        console.log(`  ✓ ${receipt.items.length} items, €${receipt.total_amount}`);
      } else {
        console.warn(`  ✗ No receipt data found`);
      }
    } catch (e) {
      console.error(`  ✗ Error: ${e.message}`);
    }

    await sleep(DELAY_MS);
  }

  if (receipts.length === 0) {
    console.warn('%c[LIDL Scraper] No receipts could be parsed.', 'color: #ff6600;');
    return;
  }

  // --- Step 3: Download ---
  const output = { receipts };
  const blob = new Blob([JSON.stringify(output, null, 2)], { type: 'application/json' });
  const blobUrl = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = blobUrl;
  a.download = `lidl_receipts_${new Date().toISOString().slice(0, 16).replace('T', '_').replace(':', '-')}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(blobUrl);

  console.log(`%c[LIDL Scraper] Done! Downloaded ${receipts.length} receipts.`, 'color: #00ff00; font-weight: bold;');
})();
