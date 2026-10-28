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
  let selectedStatus = 'all';
  let selectedImage = 'all';
  const statusBtns = [...document.querySelectorAll('[data-filter-status]')];
  const imageBtns = [...document.querySelectorAll('[data-filter-image]')];
  const sort = document.getElementById('sort');
  const columnButtons = [...document.querySelectorAll('[data-sort-column]')];
  let activeSort = 'ratio-desc';
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
    'ratio-asc': (a,b) => ratio(a)-ratio(b) || byName(a,b),
    'ta-asc': (a,b) => score(a,'ta_score','earned') - score(b,'ta_score','earned') || byName(a,b),
    'gs-asc': (a,b) => score(a,'gamerscore','earned') - score(b,'gamerscore','earned') || byName(a,b),
    'ach-asc': (a,b) => score(a,'achievements','earned') - score(b,'achievements','earned') || byName(a,b),
    'status-asc': (a,b) => a.completion_status.localeCompare(b.completion_status) || byName(a,b),
    'status-desc': (a,b) => b.completion_status.localeCompare(a.completion_status) || byName(a,b),
    'image-desc': (a,b) => Number(Boolean(b.image_src)) - Number(Boolean(a.image_src)) || byName(a,b),
    'image-asc': (a,b) => Number(Boolean(a.image_src)) - Number(Boolean(b.image_src)) || byName(a,b),
  };
  function update() {
    const query = search.value.trim().toLocaleLowerCase();
    const visible = games.filter(g => {
      return (!query || g.title.toLocaleLowerCase().includes(query))
        && (selectedStatus === 'all' || g.completion_status === selectedStatus)
        && (selectedImage === 'all' || (selectedImage === 'available') === Boolean(g.image_src));
    }).sort(comparators[activeSort] || comparators['ratio-desc']);
    gallery.replaceChildren(...visible.map(g => cardById.get(String(g.id))).filter(Boolean));
    tableBody.replaceChildren(...visible.map(g => rowById.get(String(g.id))).filter(Boolean));
    resultCount.textContent = integer.format(visible.length);
    noResults.hidden = visible.length !== 0;
    clearBtn.hidden = !(query || selectedStatus !== 'all' || selectedImage !== 'all' || activeSort !== 'ratio-desc');
  }
  function reflectColumnSort() {
    const [key, dir] = activeSort.split('-');
    columnButtons.forEach(button => {
      const selected = button.dataset.sortColumn === key;
      button.closest('th').setAttribute('aria-sort', selected ? (dir === 'asc' ? 'ascending' : 'descending') : 'none');
      button.querySelector('.sort-indicator').textContent = selected ? (dir === 'asc' ? '↑' : '↓') : '↕';
    });
  }
  search.addEventListener('input', update);
  sort.addEventListener('change', () => {
    activeSort = sort.value;
    if (!sort.selectedOptions[0]?.dataset.temporarySort) sort.querySelector('option[data-temporary-sort]')?.remove();
    reflectColumnSort(); update();
  });
  const columnDefaults = {title:'asc', status:'asc', completion:'desc', ach:'desc', gs:'desc', ta:'desc', ratio:'desc', image:'desc'};
  columnButtons.forEach(button => button.addEventListener('click', () => {
    const key = button.dataset.sortColumn;
    const current = activeSort.split('-');
    const dir = current[0] === key ? (current[1] === 'asc' ? 'desc' : 'asc') : columnDefaults[key];
    activeSort = `${key}-${dir}`;
    const temporary = sort.querySelector('option[data-temporary-sort]');
    if (temporary) temporary.remove();
    if (![...sort.options].some(option => option.value === activeSort)) {
      const tempOption = document.createElement('option');
      tempOption.value = activeSort;
      tempOption.dataset.temporarySort = 'true';
      tempOption.textContent = `${button.textContent.replace(/[↕↑↓]/g, '').trim()} (${dir === 'asc' ? 'ascending' : 'descending'})`;
      sort.add(tempOption);
    }
    sort.value = activeSort;
    reflectColumnSort(); update();
  }));
  function setFilter(buttons, target) {
    buttons.forEach(btn => { const active = btn === target; btn.classList.toggle('is-active', active); btn.setAttribute('aria-pressed', String(active)); });
  }
  statusBtns.forEach(btn => btn.addEventListener('click', () => { selectedStatus = btn.dataset.filterStatus; setFilter(statusBtns,btn); update(); }));
  imageBtns.forEach(btn => btn.addEventListener('click', () => { selectedImage = btn.dataset.filterImage; setFilter(imageBtns,btn); update(); }));
  clearBtn.addEventListener('click', () => {
    search.value = ''; selectedStatus = 'all'; selectedImage = 'all'; sort.querySelector('option[data-temporary-sort]')?.remove(); sort.value = 'ratio-desc'; activeSort = 'ratio-desc'; reflectColumnSort(); setFilter(statusBtns,statusBtns[0]); setFilter(imageBtns,imageBtns[0]); update(); search.focus();
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
  reflectColumnSort();
  update();
})();
