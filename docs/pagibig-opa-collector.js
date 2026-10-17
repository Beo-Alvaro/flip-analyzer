// Pag-IBIG Online Public Auction collector
// -----------------------------------------
// Reads every property listed for one province on Pag-IBIG's Online Public
// Auction site (1st auction, 2nd auction, and negotiated sale tabs) and
// saves them as a JSON file for `python -m flip.pagibig <file>.json`.
//
// How to use (about 10 minutes for Cavite):
//   1. Open https://www.pagibigfundservices.com/OnlinePublicAuction/
//   2. Choose the Region (e.g. REGION 4-A) and Province (e.g. CAVITE).
//   3. Open the browser console: press F12, then click the "Console" tab.
//   4. Paste this whole file and press Enter. Leave the tab open; it reads
//      one city at a time, pausing between pages so it doesn't strain the
//      site, and prints its progress.
//   5. When it finishes, your browser downloads opa_listings.json. Move it
//      to data/market/ and run:
//        python -m flip.pagibig data/market/opa_listings.json
//
// It only reads what the page shows; it never bids, logs in, or submits
// anything.

(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  const cards = pane => [...pane.querySelectorAll('[id^="property-images-"]')].map(img => {
    const card = img.closest('form') || img.parentElement;
    const field = t => (card.querySelector(`[title="${t}"], [data-bs-original-title="${t}"]`)?.innerText || '').trim();
    return {
      id: img.id.replace('property-images-', ''),
      name: (card.querySelector('h3')?.innerText || '').trim(),
      type: (card.querySelector('.bi-houses')?.parentElement.innerText || '').trim(),
      dates: (card.querySelector('#acceptance_offer')?.innerText || '').replace('|', '').trim(),
      batch: card.querySelector('[data-batch]')?.getAttribute('data-batch') || '',
      occupancy: field('Occupancy Status'), lot: field('Lot Area'), floor: field('Floor Area'),
      price: field('Minimum Bid/Selling Price'),
    };
  });

  async function collectTab(paneId, tabStart, sale) {
    [...document.querySelectorAll('button, a')].find(e => e.textContent.trim().startsWith(tabStart)).click();
    await sleep(1500);
    const pane = document.querySelector(paneId);
    const rows = [], seen = new Set();
    for (let page = 0; page < 200; page++) {
      const now = cards(pane);
      let fresh = 0;
      for (const c of now) if (!seen.has(c.id)) { seen.add(c.id); rows.push({...c, sale}); fresh++; }
      if (!now.length || !fresh) break;
      const next = [...pane.querySelectorAll('button, a')].find(b => b.textContent.trim() === 'Next');
      if (!next || next.disabled || next.classList.contains('disabled')) break;
      const firstId = now[0].id;
      next.click();
      for (let w = 0; w < 20; w++) { await sleep(400); const c = cards(pane); if (c.length && c[0].id !== firstId) break; }
      await sleep(800);  // pause between pages
    }
    return rows;
  }

  const citySelect = [...document.querySelectorAll('select')]
    .find(s => [...s.options].some(o => /^Select City/i.test(o.text)));
  const cities = [...citySelect.options].map(o => o.text.trim()).filter(t => t && !/^Select/i.test(t));
  if (!cities.length) { console.error('Choose a Region and Province first.'); return; }

  const all = [];
  for (const city of cities) {
    const option = [...citySelect.options].find(o => o.text.trim() === city);
    citySelect.value = option.value;
    citySelect.dispatchEvent(new Event('change', {bubbles: true}));
    await sleep(800);
    [...document.querySelectorAll('a')].find(a => a.textContent.trim() === 'Search').click();
    await sleep(6000);
    const before = all.length;
    for (const [pane, tab, sale] of [['#nav-first', 'First Auction', '1st auction'],
                                     ['#nav-second', 'Second Auction', '2nd auction'],
                                     ['#nav-nego', 'Negotiated Sale', 'negotiated sale']]) {
      all.push(...(await collectTab(pane, tab, sale)).map(r => ({...r, city})));
    }
    console.log(`${city}: ${all.length - before} properties (total ${all.length})`);
    await sleep(2000);  // pause between cities
  }

  const blob = new Blob([JSON.stringify(all, null, 1)], {type: 'application/json'});
  const a = Object.assign(document.createElement('a'),
                          {href: URL.createObjectURL(blob), download: 'opa_listings.json'});
  document.body.appendChild(a); a.click(); a.remove();
  console.log(`Done: ${all.length} properties saved to opa_listings.json`);
})();
