(() => {
  'use strict';
  const archiveEl = document.getElementById('archive-data');
  if (!archiveEl) return;
  let payload;
  try { payload = JSON.parse(archiveEl.textContent); }
  catch (error) { console.error('Archive data could not be read:', error); return; }
  const games = Array.isArray(payload.games) ? payload.games : [];
  const byId = new Map(games.map(game => [String(game.id), game]));
  const gallery = document.getElementById('gallery');
  const tableBody = document.getElementById('table-body');
  const cardById = new Map([...gallery.children].map(el => [el.dataset.gameId, el]));
  const rowById = new Map([...tableBody.children].map(el => [el.dataset.gameId, el]));
  const search = document.getElementById('search');
  const status = document.getElementById('status');
  const images = document.getElementById('images-filter');
  const sort = document.getElementById('sort');
  const resultCount = document.getElementById('result-count');
  const noResults = document.getElementById('empty-state');
  const tableView = document.getElementById('table-view');
  const gridView = document.getElementById('gallery');
  const clearBtn = document.getElementById('clear-filters');
  const detail = document.getElementById('detail-dialog');
  const integer = new Intl.NumberFormat('en-US');
  const pct = (n) => (Math.round(Number(n) * 10) / 10).toLocaleString('en-US', { maximumFractionDigits: 1 }) + '%';
  const score = (g, key, prop) => (Number(g?.[key]?.[prop]) || 0);
  const ratio = g => Number.isFinite(Number(g.ta_ratio)) ? Number(g.ta_ratio) : 0;
  const byName = (a, b) => a.title.localeCompare(b.title, undefined, { sensitivity: 'base', numeric: true });
  const comparators = {
    'title-asc': (a,b) => byName(a,b),
    'title-desc': (a,b) => byName(b,a),
    'ta-desc': (a,b) => score(b,'ta_score','earned') - score(a,'ta_score','earned') || byName(a,b),
    'gs-desc': (a,b) => score(b,'gamerscore','earned') - score(a,'gamerscore','earned') || byName(a,b),
    'ach-desc': (a,b) => score(b,'achievements','earned') - score(a,'achievements','earned') || byName(a,b),
    'completion-desc': (a,b) => Number(b.completion_percentage) - Number(a.completion_percentage) || byName(a,b),
    'completion-asc': (a,b) => Number(a.completion_percentage) - Number(b.completion_percentage) || byName(a,b),
    'ratio-desc': (a,b) => ratio(b)-ratio(a) || byName(a,b),
  };
  function update() {
    const query = search.value.trim().toLocaleLowerCase();
    const selectedStatus = status.value;
    const selectedImage = images.value;
    const visible = games.filter(g => {
      return (!query || g.title.toLocaleLowerCase().includes(query))
        && (selectedStatus === 'all' || g.completion_status === selectedStatus)
        && (selectedImage === 'all' || (selectedImage === 'available') === Boolean(g.image_src));
    }).sort(comparators[sort.value] || comparators['ta-desc']);
    gallery.replaceChildren(...visible.map(g => cardById.get(String(g.id))).filter(Boolean));
    tableBody.replaceChildren(...visible.map(g => rowById.get(String(g.id))).filter(Boolean));
    resultCount.textContent = integer.format(visible.length);
    noResults.hidden = visible.length !== 0;
    clearBtn.hidden = !(query || selectedStatus !== 'all' || selectedImage !== 'all' || sort.value !== 'ta-desc');
  }
  [search, status, images, sort].forEach(el => { el.addEventListener('input', update); el.addEventListener('change', update); });
  clearBtn.addEventListener('click', () => {
    search.value = ''; status.value = 'all'; images.value = 'all'; sort.value = 'ta-desc'; update(); search.focus();
  });
  const viewBtns = [...document.querySelectorAll('[data-view]')];
  function chooseView(view) {
    const isTable = view === 'table';
    tableView.hidden = !isTable;
    gridView.hidden = isTable;
    viewBtns.forEach(btn => {
      const active = btn.dataset.view === view;
      btn.classList.toggle('is-active',active);
      btn.setAttribute('aria-pressed', String(active));
    });
  }
  viewBtns.forEach(btn => btn.addEventListener('click', () => chooseView(btn.dataset.view)));
  const detailStatus = document.getElementById('detail-status');
  const detailTitle = document.getElementById('detail-title');
  const detailImage = document.getElementById('detail-image');
  const detailMetrics = document.getElementById('detail-metrics');
  const detailLink = document.getElementById('detail-link');
  const detailNote = document.getElementById('detail-note');
  const metric = (label, value) => {
    const el = document.createElement('div');
    el.className = 'dialog-metric';
    const small = document.createElement('span'); small.textContent = label;
    const strong = document.createElement('strong'); strong.textContent = value;
    el.append(small,strong); return el;
  };
  function openDetails(game) {
    if (!game || !detail || typeof detail.showModal !== 'function') return;
    detailTitle.textContent = game.title;
    detailStatus.textContent = game.completion_status === 'completed' ? 'All TA achievements unlocked' : game.completion_status === 'incomplete' ? 'Achievements in progress' : 'Completion not verified';
    detailImage.replaceChildren();
    if (game.image_src) {
      const img = document.createElement('img');
      img.src = game.image_src;
      img.alt = `${game.title} TrueAchievements summary`;
      detailImage.append(img);
    } else {
      const span = document.createElement('span'); span.textContent = 'Achievement image not downloaded yet';
      detailImage.append(span);
    }
    detailMetrics.replaceChildren(
      metric('TA score',`${integer.format(score(game,'ta_score','earned'))} / ${integer.format(score(game,'ta_score','total'))}`),
      metric('Gamerscore',`${integer.format(score(game,'gamerscore','earned'))} / ${integer.format(score(game,'gamerscore','total'))}`),
      metric('Achievements',`${integer.format(score(game,'achievements','earned'))} / ${integer.format(score(game,'achievements','total'))}`),
      metric('Completion',pct(game.completion_percentage)),
      metric('TA ratio', ratio(game).toFixed(3) + '×'),
    );
    detailLink.href = game.url;
    detailNote.textContent = game.image_src ? 'Image stored locally in this archive.' : 'Image pending; statistics remain available.';
    detail.showModal();
  }
  document.addEventListener('click', event => {
    const trigger = event.target.closest('[data-open-id]');
    if (trigger) { openDetails(byId.get(trigger.dataset.openId)); return; }
    if (event.target.closest('#detail-close')) { detail.close(); return; }
    if (event.target === detail) detail.close();
  });
  chooseView('gallery');
  update();
})();
