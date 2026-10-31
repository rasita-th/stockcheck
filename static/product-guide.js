(() => {
  'use strict';
  if (window.StockRadarGuide) return;
  const KEY = 'stockRadar.productGuide.v1';
  const tours = {
    scanner: { name: 'Scanner', version: 1, steps: [
      ['เริ่มจากหุ้นที่สนใจ', 'ค้นหาสัญลักษณ์หุ้น เช่น NVDA แล้วเพิ่มหุ้นที่คุณต้องการติดตามลง My Portfolio ตัวอย่างในบทสอนนี้จะไม่เพิ่มหุ้นให้คุณ', ['#symbolSearch', '[data-add-symbol]', '#scannerPageGuide'], 'search'],
      ['อ่านราคาและเวลาอัปเดต', 'ดูราคาและเวลาอัปเดตก่อนอ่านสัญญาณเสมอ ข้อมูลหลังตลาดปิดอาจเป็นราคาของรอบซื้อขายล่าสุด ไม่ใช่ราคาเรียลไทม์', ['#technicalTableBody tr[data-select]', '#technicalMobileCards > [data-select]', '#alertSubtitle'], 'freshness'],
      ['EMA ช่วยดูแนวโน้ม', 'EMA คือราคาเฉลี่ยที่ให้น้ำหนักกับราคาล่าสุด ตัวเลข 20 หรือ 200 คือจำนวนช่วงข้อมูล ใช้ดูแนวโน้มและระยะห่างจากเส้น ไม่ใช่สัญญาณซื้อที่รับประกันผล', ['#watchlistPanel .filter-card', '[data-open-panel="filters"]'], 'ema'],
      ['Drawdown คือระยะที่ลดจากยอด', 'ถ้าราคาจากจุดสูงสุด 100 ลดเหลือ 90 จะมี Drawdown 10% ช่วง 5–15 หมายถึงลดจากยอดตั้งแต่ 5% จนถึงน้อยกว่า 15% ไม่ได้แปลว่าราคาถูกเสมอ', ['[data-drawdown-filter="desktop"]', '[data-open-panel="filters"]'], 'drawdown'],
      ['เปิดรายละเอียด แล้วติดตามต่อ', 'เลือกแถวหุ้นหรือการ์ดเพื่อเปิดรายละเอียด ดูกราฟและข้อมูลประกอบ ก่อนจดแผนใน Memo ส่วน Alert Center รวมสิ่งที่ควรตรวจต่อ ไม่ใช่คำสั่งซื้อขาย', ['#technicalTableBody tr[data-select]', '#technicalMobileCards > [data-select]', '#alertCenter'], 'detail']
    ] },
    today: { name: 'Today', version: 1, steps: [
      ['วันนี้มีอะไรควรติดตาม', 'Today รวมเหตุการณ์และประเด็นที่เกี่ยวกับหุ้นในขอบเขตที่แสดง เริ่มจากภาพรวมและเวลาอัปเดต ก่อนเลือกอ่านทีละรายการ', ['#attentionPageP4 .p4-page-heading', '#attentionHero', '#attentionPageP4', '#attentionPage'], 'freshness'],
      ['เลือกประเภทเหตุการณ์', 'ใช้ตัวกรองเพื่อเจาะข่าว งบการเงิน หรือเหตุการณ์ที่สนใจ หากไม่มีรายการในหมวดนั้น ไม่ได้หมายความว่าระบบพบสัญญาณใหม่', ['#attentionPageP4 .p4-toolbar', '#attentionFilterBar', '#attentionPageP4', '#attentionPage'], 'filter'],
      ['อ่านสถานะและแหล่งข้อมูล', 'อ่านวันที่ สถานะ และแหล่งอ้างอิงของการ์ดแต่ละใบ วันที่ประมาณการยังเปลี่ยนได้ ให้ยึดสถานะที่ระบุจริง ไม่เหมารวมว่าทุกรายการได้รับการยืนยันแล้ว', ['#attentionPageP4 .p4-catalyst-hero', '#attentionPageP4 .p4-empty', '#attentionTableCard', '#attentionCardList', '#attentionPageP4', '#attentionPage'], 'event'],
      ['เปิดต้นทางก่อนตัดสินใจ', 'เปิดแหล่งอ้างอิงของเหตุการณ์ที่สนใจ แล้วกลับไปดูหุ้นใน Scanner เพื่อประกอบภาพรวม หากวันนี้ไม่มีเหตุการณ์ คุณยังดูการ์ดสาธิตนี้ได้', ['#attentionPageP4 .p4-primary-action', '#attentionPageP4 .p4-text-link', '#attentionTableCard', '#attentionCardList', '#attentionPageP4', '#attentionPage'], 'source']
    ] },
    memo: { name: 'Memo', version: 1, steps: [
      ['จดแผนของคุณเอง', 'Memo ใช้บันทึกเหตุผลและเงื่อนไขที่อยากกลับมาติดตาม เริ่มจาก Add Memo หรือเลือกหุ้นจาก Scanner บทสอนจะไม่เปิดฟอร์มหรือบันทึกแทนคุณ', ['#memoPage [data-memo-add]', '#memoPage'], 'memo'],
      ['เขียนเหตุผลและเงื่อนไข', 'บันทึกว่ากำลังรออะไร เช่น ผลประกอบการ แล้วกำหนดราคาเป้าหมายหรือเงื่อนไขแจ้งเตือนตามแผนของคุณ ตัวอย่างนี้เป็นข้อมูลจำลอง', ['#memoPage .memo-top', '#memoPage'], 'plan'],
      ['ค้นหาและทบทวนบันทึก', 'ใช้ Search และตัวกรองเพื่อกลับมาหาแผนเดิม แยกสถานะของ Memo ออกจากความเชื่อมั่น และทบทวนเมื่อข้อมูลใหม่เปลี่ยนสมมติฐาน', ['#memoFilters', '#memoPage'], 'filter'],
      ['บันทึกเมื่อคุณพร้อม', 'ตรวจหุ้น ทิศทางราคาเป้าหมาย และเงื่อนไขก่อนกดบันทึกจริง การแจ้งเตือนเป็นสิ่งให้กลับมาตรวจแผน ไม่ได้ยืนยันว่าควรซื้อหรือขาย', ['#memoStats', '#memoPage'], 'memo']
    ] },
    market: { name: 'Market Pulse', version: 1, steps: [
      ['เริ่มจากภาพรวมและเวลา', 'Market Pulse อธิบายฉากหลังของตลาด ก่อนอ่านตัวเลขให้ตรวจเวลาอัปเดตและสถานะข้อมูล ข้อมูลที่ unavailable หรือ stale ต้องอ่านพร้อมข้อจำกัดนั้น', ['.fresh-card', '.intro'], 'freshness'],
      ['Market กับ Portfolio ต่างกันอย่างไร', 'Market แสดงภาพกว้าง ส่วน Portfolio เน้นผลต่อหุ้นที่ติดตาม เลือกมุมมองตามคำถามของคุณ บทสอนนี้จะไม่เปลี่ยนพอร์ตหรือเลือกมุมมองให้', ['.pulse-mode-tabs', '#marketBriefing'], 'views'],
      ['อ่านแรงหนุนและความเสี่ยง', 'อ่าน Briefing คู่กับ Risk สีและป้ายข้อความช่วยบอกบริบท ไม่ใช่คำสั่งซื้อขาย และไม่ควรใช้สีเพียงอย่างเดียวในการตัดสินใจ', ['#pulseSignalGrid', '#pulseSummaryList', '#marketBriefing'], 'risk'],
      ['เจาะ Sector และ Theme', 'เปรียบเทียบผลตอบแทนในช่วงเวลาเดียวกัน Rotation ในหน้านี้หมายถึงความแข็งแกร่งเปรียบเทียบของ ETF ตัวแทน ไม่ใช่ข้อมูลเงินไหลเข้าจริง', ['#sectorTable', '#themeTable'], 'rotation'],
      ['กลับไปยืนยันรายหุ้น', 'ใช้ภาพรวมตลาดเป็นบริบท แล้วกลับไปดูรายละเอียดหุ้นใน Scanner ตรวจที่มาและวิธีอ่านด้านล่างเมื่อมีข้อสงสัย', ['.method', '.topnav'], 'source']
    ] }
  };
  const glossary = {
    ema: ['EMA คืออะไร', 'ราคาเฉลี่ยที่ให้น้ำหนักกับราคาล่าสุด ใช้ดูแนวโน้มและระยะห่างของราคา เลขช่วงมากขึ้นจะสะท้อนแนวโน้มระยะยาวขึ้น', 'ema'],
    drawdown: ['Drawdown คืออะไร', 'เปอร์เซ็นต์ที่ราคาลดจากจุดสูงสุดก่อนหน้า เช่น จาก 100 เหลือ 90 = ลดลง 10% ไม่ใช่ผลตอบแทนที่คาดว่าจะได้', 'drawdown'],
    alerts: ['Alert Center ใช้อย่างไร', 'รวมสัญญาณที่ควรกลับมาตรวจ ใช้ All, Unread และ Priority เพื่อจัดรายการ อ่านรายละเอียดก่อนตัดสินใจ สัญญาณไม่ใช่คำแนะนำซื้อขาย', 'event'],
    freshness: ['ข้อมูลสดแค่ไหน', 'ดูเวลาอัปเดตและสถานะตลาดร่วมกัน ข้อมูลหลังตลาดปิดอาจอ้างอิงรอบซื้อขายล่าสุด ส่วนข้อมูล stale คือข้อมูลที่เกินเงื่อนไขความสดของระบบ', 'freshness']
  };
  let saved = {};
  try { const value = JSON.parse(localStorage.getItem(KEY) || '{}'); if (value && typeof value === 'object' && !Array.isArray(value)) saved = value; } catch (_) {}
  let view = '', session = null, previousFocus = null, frame = 0;
  const $ = (selector, root = document) => root.querySelector(selector);
  const visible = el => el && el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden';
  function currentView() {
    if (/market\.html$/i.test(location.pathname)) return 'market';
    if (document.body.classList.contains('attention-active')) return 'today';
    if (document.body.classList.contains('memo-active')) return 'memo';
    const active = $('[data-app-view].active')?.dataset.appView;
    return active === 'attention' ? 'today' : active === 'memo' ? 'memo' : 'scanner';
  }
  function remember(status) {
    if (!session || session.topic) return;
    if (saved[session.view]?.version === tours[session.view].version && saved[session.view]?.status === 'completed') return;
    saved[session.view] = { version: tours[session.view].version, status };
    try { localStorage.setItem(KEY, JSON.stringify(saved)); } catch (_) {}
  }
  function el(tag, className, text) {
    const node = document.createElement(tag); node.className = className || '';
    if (text) node.textContent = text;
    return node;
  }
  function button(label, action) {
    const node = el('button', '', label); node.type = 'button'; node.dataset.guideAction = action; return node;
  }
  function illustration(kind) {
    const figure = el('figure', 'guide-figure');
    const caption = el('figcaption', '', 'ตัวอย่างประกอบ · ไม่ใช่ข้อมูลจริงของคุณ');
    if (kind === 'ema' || kind === 'drawdown' || kind === 'rotation') {
      figure.innerHTML = `<svg viewBox="0 0 280 88" role="img" aria-label="${kind === 'drawdown' ? 'ราคาจาก 100 เหลือ 90 ลดลง 10 เปอร์เซ็นต์' : kind === 'ema' ? 'ตัวอย่างเส้นราคาและเส้นค่าเฉลี่ย EMA' : 'เปรียบเทียบผลตอบแทนของกลุ่ม A และ B'}"><path d="M16 66H264" stroke="#68798d" fill="none"/><path d="${kind === 'drawdown' ? 'M20 20L85 30L145 25L205 54L260 64' : 'M20 65L65 38L110 48L155 20L205 35L260 15'}" stroke="#79c5ff" stroke-width="3" fill="none"/>${kind === 'ema' ? '<path d="M20 65Q140 43 260 32" stroke="#ffc86b" stroke-width="3" fill="none"/><text x="190" y="77">ราคา / EMA</text>' : kind === 'drawdown' ? '<text x="18" y="16">100</text><text x="225" y="83">90 · −10%</text>' : '<text x="18" y="16">กลุ่ม A / กลุ่ม B</text>'}</svg>`;
    } else {
      const labels = {
        search: ['⌕ NVDA', 'เลือกหุ้น → ดูรายละเอียด'], freshness: ['◷ อัปเดตรอบล่าสุด', 'ตรวจเวลา + สถานะข้อมูล'],
        event: ['เหตุการณ์ตัวอย่าง', 'วันที่ประมาณการ · ตรวจแหล่งอ้างอิง'], source: ['เหตุการณ์ → แหล่งต้นทาง', 'อ่านข้อมูลประกอบ → ตรวจรายหุ้น'],
        detail: ['แถวหุ้น → รายละเอียด', 'กราฟ · แนวโน้ม · แผนติดตาม'], filter: ['ทั้งหมด → หมวดที่สนใจ', 'ไม่มีรายการ = ไม่มีข้อมูลตรงตัวกรอง'],
        memo: ['บันทึกแผน → กลับมาทบทวน', 'ยังไม่มีการบันทึกข้อมูลใด ๆ'], plan: ['เหตุผล: รอผลประกอบการ', 'เงื่อนไขตัวอย่าง: ตรวจเมื่อราคา ≤ 90'],
        views: ['Market ↔ Portfolio', 'ภาพกว้าง ↔ ผลต่อหุ้นที่ติดตาม'], risk: ['แรงหนุน ↑ · เฝ้าดู ◷ · ความเสี่ยง !', 'อ่านป้ายข้อความควบคู่กับสี']
      };
      (labels[kind] || labels.detail).forEach((text, index) => figure.append(el(index ? 'small' : 'strong', '', text)));
      if (['search', 'detail', 'filter', 'views'].includes(kind)) {
        const pointer = el('div', 'guide-demo-click'); pointer.setAttribute('aria-hidden', 'true');
        pointer.innerHTML = '<svg viewBox="0 0 60 40"><circle cx="30" cy="18" r="10" fill="none" stroke="#79c5ff"/><path d="M27 7V31L33 25L38 34L43 31L37 22L46 21Z" fill="#d5e9ff" stroke="#111c2a"/></svg>';
        figure.append(pointer);
      }
    }
    figure.append(caption); return figure;
  }
  const dock = el('aside', 'guide-dock');
  const launcher = button('ⓘ วิธีใช้', 'menu'); launcher.setAttribute('aria-expanded', 'false');
  launcher.setAttribute('aria-controls', 'product-guide-menu');
  const menu = el('section', 'guide-menu'); menu.id = 'product-guide-menu'; menu.hidden = true;
  dock.append(menu, launcher);
  const layer = el('div', 'guide-layer'); layer.hidden = true;
  const shield = el('div', 'guide-shield');
  const ring = el('div', 'guide-spotlight'); ring.setAttribute('aria-hidden', 'true');
  const panel = el('section', 'guide-panel'); panel.setAttribute('role', 'dialog'); panel.setAttribute('aria-modal', 'true');
  panel.setAttribute('aria-labelledby', 'product-guide-title'); panel.setAttribute('aria-describedby', 'product-guide-description'); panel.tabIndex = -1;
  layer.append(shield, ring, panel);
  function close(status = 'dismissed') {
    if (session) remember(status);
    session = null; layer.hidden = true; ring.hidden = true;
    if (previousFocus?.isConnected && visible(previousFocus)) previousFocus.focus({preventScroll:true});
    else launcher.focus({preventScroll:true});
    previousFocus = null;
  }
  function open(topic = null) {
    if (session) close();
    previousFocus = document.activeElement;
    menu.hidden = true; launcher.setAttribute('aria-expanded', 'false');
    session = { view: currentView(), index: 0, topic };
    layer.hidden = false; render(); panel.focus({preventScroll:true});
  }
  function position() {
    if (!session) return;
    const step = session.topic ? null : tours[session.view].steps[session.index];
    const target = step?.[2].map(selector => [...document.querySelectorAll(selector)].find(visible)).find(Boolean);
    ring.hidden = !target;
    const vw = document.documentElement.clientWidth, vh = window.innerHeight;
    const pw = Math.min(368, vw - 24), ph = Math.min(panel.offsetHeight, vh - 24);
    let left = (vw - pw) / 2, top = (vh - ph) / 2;
    if (target) {
      const r = target.getBoundingClientRect();
      const x = Math.max(6, r.left - 5), y = Math.max(6, r.top - 5);
      const w = Math.max(0, Math.min(vw - 6, r.right + 5) - x), h = Math.max(0, Math.min(vh - 6, r.bottom + 5) - y);
      Object.assign(ring.style, {left:`${x}px`,top:`${y}px`,width:`${w}px`,height:`${h}px`});
      if (vw > 760 && r.right + pw + 24 < vw) { left = r.right + 16; top = r.top; }
      else if (r.bottom + ph + 20 < vh) { left = r.left; top = r.bottom + 16; }
      else if (r.top - ph - 16 > 0) { left = r.left; top = r.top - ph - 16; }
      else { top = vh - ph - 12; }
    }
    Object.assign(panel.style, {left:`${Math.max(12,Math.min(left,vw-pw-12))}px`,top:`${Math.max(12,Math.min(top,vh-ph-12))}px`});
  }
  function render() {
    const tour = tours[session.view], topic = session.topic && glossary[session.topic];
    const step = topic || tour.steps[session.index];
    panel.replaceChildren();
    const header = el('div', 'guide-top');
    header.append(el('span', '', topic ? 'คำอธิบายเพิ่มเติม' : `${tour.name} · ${session.index + 1} จาก ${tour.steps.length}`), button('ปิด ×','close'));
    const title = el('h2', '', step[0]); title.id = 'product-guide-title';
    const description = el('p', '', step[1]); description.id = 'product-guide-description';
    panel.append(header, title, description, illustration(topic ? topic[2] : step[3]));
    const note = el('p', 'guide-note', 'สาธิตเท่านั้น · ไม่เพิ่มหุ้น ไม่เปลี่ยนตัวกรอง และไม่บันทึก Memo'); panel.append(note);
    const footer = el('div', 'guide-footer');
    if (topic) footer.append(button('เข้าใจแล้ว','close'));
    else {
      footer.append(button('ข้ามบทนี้','skip'));
      const back = button('ย้อนกลับ','back'); back.disabled = session.index === 0;
      footer.append(back, button(session.index === tour.steps.length - 1 ? 'จบบทสอน' : 'ถัดไป','next'));
    }
    panel.append(footer);
    if (!topic) {
      const target = step[2].map(selector => [...document.querySelectorAll(selector)].find(visible)).find(Boolean);
      if (target) target.scrollIntoView({block:'center',behavior:'instant'});
      else note.textContent = 'ส่วนนี้ยังไม่แสดงบนหน้าจอ · อ่านตัวอย่างก่อนได้ หรือปิดบทสอนแล้วเปิดส่วนนี้เอง';
    }
    requestAnimationFrame(position);
  }
  function refreshMenu() {
    const now = currentView();
    if (now !== view) {
      if (session) close();
      view = now;
      menu.hidden = saved[view]?.version === tours[view].version;
      launcher.setAttribute('aria-expanded', String(!menu.hidden));
    }
    const tour = tours[view];
    if (menu.dataset.view !== view) {
      menu.dataset.view = view; menu.replaceChildren();
      menu.append(el('strong', '', `วิธีใช้ ${tour.name}`), el('p', '', 'เรียนรู้ทีละจุด พร้อมตัวอย่างประกอบ ใช้เวลาประมาณหนึ่งนาที'));
      menu.append(button('เริ่มแนะนำหน้านี้','start'), button('ไว้ภายหลัง','later'));
      const topics = el('div', 'guide-topics');
      Object.entries(glossary).forEach(([key, item]) => { const b = button(`ⓘ ${item[0]}`, 'topic'); b.dataset.guideTopic = key; topics.append(b); });
      menu.append(topics);
      const links = el('nav', 'guide-links'); links.setAttribute('aria-label','บทสอนตามหน้า');
      Object.entries(tours).forEach(([key, item]) => { const a = el('a','',item.name); a.href = key === 'market' ? 'market.html' : `index.html#${key === 'today' ? 'today' : key}`; links.append(a); });
      menu.append(links);
    }
    const contexts = [
      ['#scannerPageGuide strong', null, 'Scanner'], ['#attentionPageP4 .p4-page-heading h1', null, 'Today'], ['#attentionHero h2', null, 'Today'], ['#memoPage .memo-title h2', null, 'Memo'],
      ['.intro h1', null, 'Market Pulse'], ['#alertCenter h2', 'alerts', 'Alert Center'],
      ['#watchlistPanel .filter-card h2','ema','EMA'], ['[data-drawdown-filter="desktop"] .drawdown-filter-head','drawdown','Drawdown'], ['.fresh-card','freshness','เวลาอัปเดต'], ['#filtersSheet .drawdown-sheet-heading','drawdown','Drawdown']
    ];
    for (const [selector, topic, label] of contexts) {
      const parent = $(selector);
      if (!parent || parent.querySelector('.guide-info')) continue;
      const info = button('ⓘ', topic ? 'topic' : 'start'); info.className = 'guide-info';
      info.setAttribute('aria-label',`วิธีใช้ ${label}`); if (topic) info.dataset.guideTopic = topic;
      parent.append(info);
    }
  }
  function schedule() { if (frame) return; frame = requestAnimationFrame(() => { frame = 0; refreshMenu(); if (session) position(); }); }
  function click(event) {
    const control = event.target.closest?.('[data-guide-action]'); if (!control) return;
    event.preventDefault(); event.stopPropagation();
    switch (control.dataset.guideAction) {
      case 'menu': menu.hidden = !menu.hidden; launcher.setAttribute('aria-expanded',String(!menu.hidden)); break;
      case 'later': saved[view] = {version:tours[view].version,status:'skipped'}; try {localStorage.setItem(KEY,JSON.stringify(saved));} catch (_) {} menu.hidden = true; launcher.setAttribute('aria-expanded','false'); launcher.focus(); break;
      case 'start': open(); break;
      case 'topic': open(control.dataset.guideTopic); break;
      case 'back': session.index = Math.max(0,session.index-1); render(); panel.focus({preventScroll:true}); break;
      case 'next': if (session.index === tours[session.view].steps.length-1) close('completed'); else {session.index++;render();panel.focus({preventScroll:true});} break;
      case 'skip': close('skipped'); break;
      case 'close': close(); break;
    }
  }
  function boot() {
    document.body.append(dock,layer); refreshMenu();
    document.addEventListener('click', click, true);
    document.addEventListener('keydown', event => {
      if (!session) { if(event.key === 'Escape') {menu.hidden=true;launcher.setAttribute('aria-expanded','false');} return; }
      if (event.key === 'Escape') {event.preventDefault();event.stopPropagation();close();}
      if (event.key === 'Tab') {
        const controls = [...panel.querySelectorAll('button:not(:disabled), a[href]')].filter(visible);
        const first = controls[0], last = controls[controls.length-1];
        if (event.shiftKey && (document.activeElement === first || document.activeElement === panel)) {event.preventDefault();last?.focus();}
        else if (!event.shiftKey && (document.activeElement === last || document.activeElement === panel)) {event.preventDefault();first?.focus();}
      }
    }, true);
    new MutationObserver(schedule).observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['class']});
    window.addEventListener('resize',schedule); document.addEventListener('scroll',schedule,true); window.addEventListener('hashchange',schedule);
  }
  window.StockRadarGuide = Object.freeze({open:() => open(),close:() => close()});
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded',boot,{once:true}); else boot();
})();
