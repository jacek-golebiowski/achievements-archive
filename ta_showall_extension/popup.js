const statusEl=document.getElementById('status');
const countsEl=document.getElementById('counts');
const infoEl=document.getElementById('fileInfo');
const fileEl=document.getElementById('database');
const freshEl=document.getElementById('fresh');
const startEl=document.getElementById('start');
const stopEl=document.getElementById('stop');
const exportEl=document.getElementById('export');
const folderEl=document.getElementById('folder');
const modeEl=document.getElementById('mode');
let sourceValid=false;
function inputReady(){return freshEl.checked||sourceValid;}
function status(text){statusEl.textContent=text;}
async function message(type,extra={}) {
  try{return await chrome.runtime.sendMessage({type,...extra});}
  catch(error){return {ok:false,error:error.message||String(error)};}
}
async function refresh() {
  const saved=await chrome.storage.local.get(['ta_progress','ta_games','ta_failures','ta_last_export']);
  const p=saved.ta_progress||{};
  const stats=summarizeGames(saved.ta_games||[]);
  status(p.message||(stats.total?`${stats.total} saved game records.`:'Ready.'));
  startEl.disabled=!!p.running||!inputReady();
  stopEl.disabled=!p.running;
  exportEl.disabled=!!p.running||!stats.total;
  countsEl.textContent=`Last saved database: ${stats.total} games · ${stats.downloaded} images · ${stats.failed} failed · ${stats.not_attempted} not attempted.`+
    (saved.ta_last_export?`\nLast export: ${saved.ta_last_export.ok?'OK':'FAILED'} (${saved.ta_last_export.at}).`:'');
}
async function readSelectedFile() {
  const file=fileEl.files?.[0];
  if(!file)throw Error('Choose games.json first.');
  let raw;
  try{raw=JSON.parse(await file.text());}
  catch{throw Error('The selected file is not valid JSON.');}
  return readGamesJson(raw);
}
fileEl.addEventListener('change',async()=>{
  if(fileEl.files?.length){freshEl.checked=false;}
  sourceValid=false;startEl.disabled=true;
  if(!fileEl.files?.length){infoEl.textContent='Choose your current games.json.';return;}
  try {
    const games=await readSelectedFile();
    const stats=summarizeGames(games);
    infoEl.textContent=`Selected ${fileEl.files[0].name}: ${stats.total} games, ${stats.downloaded} downloaded images, ${stats.failed} failed.`;
    sourceValid=true;
    await refresh();
  } catch(error) {
    infoEl.textContent='Invalid file: '+error.message;
    status('File error: '+error.message);
  }
});
freshEl.addEventListener('change',async()=>{
  if(freshEl.checked){fileEl.value='';sourceValid=false;infoEl.textContent='Fresh start: the reference database will be empty. The first export creates games.json.';}
  else infoEl.textContent='Select the latest games.json from ta-collector/data/.';
  await refresh();
});
startEl.addEventListener('click',async()=>{
  startEl.disabled=true;
  try {
    const fresh=freshEl.checked;
    const games=fresh?[]:await readSelectedFile(); // Every non-fresh run reads the actual selected JSON.
    const [tab]=await chrome.tabs.query({active:true,currentWindow:true});
    if(!tab?.id || !/^https:\/\/www\.trueachievements\.com\/gamer\/ForensicFlubber\/games(?:[?#]|$)/i.test(tab.url||''))
      throw Error('Open your ForensicFlubber games page and click Show All first.');
    const folder=folderEl.value.trim();
    await chrome.storage.local.set({ta_options:{mode:modeEl.value,folder}});
    const response=await message('START',{tabId:tab.id,mode:modeEl.value,folder,games,fresh});
    if(!response?.ok)throw Error(response?.error||'Unable to start.');
    // Prevent another run from silently reusing the now-stale selected file.
    fileEl.value='';sourceValid=false;freshEl.checked=false;
    infoEl.textContent='Run started. On your next run select the newly exported games.json.';
    await refresh();
  } catch(error) {
    status('Error: '+error.message);
    startEl.disabled=!inputReady();
  }
});
stopEl.addEventListener('click',async()=>{
  await message('STOP');
  await refresh();
});
exportEl.addEventListener('click',async()=>{
  status('Exporting the current saved data…');
  const response=await message('EXPORT',{folder:folderEl.value.trim()});
  await refresh();
  if(!response?.ok)status('Export failed: '+(response.error||JSON.stringify(response)));
  else status('games.json and ta_failures.json exported (overwritten).');
});
chrome.storage.onChanged.addListener((changes,area)=>{
  if(area==='local'&&(changes.ta_progress||changes.ta_last_export))refresh();
});
(async()=>{
  const x=await chrome.storage.local.get('ta_options');
  if(x.ta_options){modeEl.value=VALID_MODES.has(x.ta_options.mode)?x.ta_options.mode:'missing';folderEl.value=x.ta_options.folder||'ta-collector';}
  await refresh();
})();
