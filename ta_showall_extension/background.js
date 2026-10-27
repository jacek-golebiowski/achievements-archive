importScripts('state.js');
// Download transport deliberately retained from working v1.0.
const GAMER_ID=1136202;
const IMAGE_DELAY_MS=10000; // Wait 10 seconds after each attempt before next request.
let active=false, stopped=false;
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
function extractTable(){
 const rows=[...document.querySelectorAll('#oGamerGamesList tbody tr')];
 function numberPair(t){const a=(t||'').replace(/,/g,'').match(/\d+/g)||[];return {earned:a[0]===undefined?null:Number(a[0]),total:a[1]===undefined?null:Number(a[1])};}
 const items=[];
 for(const row of rows){
  const cells=[...row.querySelectorAll(':scope > td')];
  if(cells.length<7)continue;
  const gameLink=cells[1].querySelector('a[href*="/game/"][href*="/achievements"]');
  if(!gameLink)continue;
  const idStr=row.querySelector('select[data-id]')?.dataset.id || row.querySelector('[id^="tdGameRating"]')?.id.replace('tdGameRating','');
  if(!/^\d+$/.test(idStr||''))continue;
  const id=Number(idStr), ach=numberPair(cells[2].textContent), ta=numberPair(cells[3].textContent), gs=numberPair(cells[4].textContent);
  const percent=Number((cells[5].textContent.match(/[\d.]+/)||[])[0]);
  const ratio=Number((cells[6].textContent.match(/[\d.]+/)||[])[0]);
  const ratingValue=row.querySelector('select[data-id] option:checked')?.value;
  const trophy=!!row.querySelector('a[href*="btnRemoveFromTrophyCase"]');
  const imgThumb=cells[0].querySelector('img')?.getAttribute('src');
  items.push({id,title:gameLink.textContent.trim(),url:new URL(gameLink.getAttribute('href'),location.origin).href,
   achievements:ach,ta_score:ta,gamerscore:gs,
   completion_percentage:Number.isFinite(percent)?percent:null,
   ta_ratio:Number.isFinite(ratio)?ratio:null,
   personal_rating:ratingValue && /^\d/.test(ratingValue)?Number(ratingValue):null,
   trophy_case:trophy,thumbnail_url:imgThumb?new URL(imgThumb,location.origin).href:null,
   image_url:`https://img.trueachievements.com/game/${id}/1136202`,
   ta_achievements_complete:ach.earned!==null&&ach.total>0&&ach.earned===ach.total,
   archive_completed:null});
 }
 return {games:items,location:location.href,showAllVisible:!![...document.querySelectorAll('#oGamerGamesListContent a')].find(a=>/show all/i.test(a.textContent||''))};
}
function downloadOne(url,filename){
 return new Promise(resolve=>{
  chrome.downloads.download({url,filename,conflictAction:'overwrite',saveAs:false},id=>{
   const err=chrome.runtime.lastError;
   if(err||!id){resolve({ok:false,error:err?.message||'download failed to start'});return;}
   let finished=false;
   const timer=setTimeout(()=>done({ok:false,error:'download timed out'}),45000);
   function done(out){if(finished)return;finished=true;clearTimeout(timer);chrome.downloads.onChanged.removeListener(onChanged);resolve(out);}
   async function onChanged(change){
    if(change.id!==id||!change.state)return;
    if(change.state.current==='interrupted'){done({ok:false,error:'download interrupted: '+(change.error?.current||'unknown')});return;}
    if(change.state.current==='complete'){
     const matches=await chrome.downloads.search({id});
     const info=matches?.[0];
     if(!info?.mime?.startsWith('image/')){
      try{await chrome.downloads.removeFile(id);}catch{}
      done({ok:false,error:'response was not an image (mime: '+(info?.mime||'unknown')+')'});
     }else done({ok:true,mime:info.mime,bytes:info.fileSize||info.bytesReceived||0,download_id:id,filename:info.filename});
    }
   }
   chrome.downloads.onChanged.addListener(onChanged);
  });
 });
}

async function exportOne(filename,obj){
 const json=JSON.stringify(obj,null,2);
 const url='data:application/json;charset=utf-8,'+encodeURIComponent(json);
 return new Promise(resolve=>chrome.downloads.download({url,filename,conflictAction:'overwrite',saveAs:false},id=>{
   const err=chrome.runtime.lastError;
   if(err||!id){resolve({ok:false,error:err?.message||'Export could not start'});return;}
   let done=false;
   const timer=setTimeout(()=>finish({ok:false,error:'Export timed out'}),45000);
   function finish(value){if(done)return;done=true;clearTimeout(timer);chrome.downloads.onChanged.removeListener(listener);resolve(value);}
   function listener(change){if(change.id!==id||!change.state)return;
    if(change.state.current==='complete')finish({ok:true});
    else if(change.state.current==='interrupted')finish({ok:false,error:change.error?.current||'Export interrupted'});
   }
   chrome.downloads.onChanged.addListener(listener);
 }));
}
async function exportSnapshot(folder,reason) {
  const x=await chrome.storage.local.get(['ta_games','ta_progress']);
  if(!Array.isArray(x.ta_games))return {ok:false,error:'No saved games'};
  const games=x.ta_games.map(normalizeGame);
  const failures=unresolvedFailures(games);
  const stamp=new Date().toISOString();
  await chrome.storage.local.set({ta_failures:failures});
  const base=folder+'/data/';
  const main={schema_version:3,source:'https://www.trueachievements.com/gamer/ForensicFlubber/games',
    gamer_id:GAMER_ID,exported_at:stamp,export_reason:reason,images_base:'../images/',games};
  const gameResult=await exportOne(base+'games.json',main);
  const failureResult=await exportOne(base+'ta_failures.json',{schema_version:1,exported_at:stamp,failures});
  const report={ok:gameResult.ok&&failureResult.ok,games:gameResult,failures:failureResult};
  await chrome.storage.local.set({ta_last_export:{...report,at:stamp,reason,folder}});
  return report;
}
async function progress(message,running=true,extra={}) {
  await chrome.storage.local.set({ta_progress:{message,running,updated_at:new Date().toISOString(),...extra}});
}
async function startJob(tabId,mode,folder,referenceGames) {
  active=true;stopped=false;
  let savedAtLeastOnce=false;
  try {
    // Important: the reference came from games.json selected for THIS run.
    // Do not hydrate from extension storage, old exports, or downloads history.
    const reference=readGamesJson({games:referenceGames,gamer_id:GAMER_ID});
    await progress(reference.length?`Read ${reference.length} existing game IDs from games.json. Scanning Show All…`:'Fresh start: no existing records. Scanning Show All…');
    const executed=await chrome.scripting.executeScript({target:{tabId},func:extractTable});
    const scraped=executed?.[0]?.result?.games;
    if(!scraped?.length)throw Error('No games found. Open your games list and click Show All.');
    if(scraped.length<150)throw Error(`Only ${scraped.length} visible rows. Click Show All before syncing.`);
    const {games,knownIds}=mergeScrapedGames(reference,scraped);
    const visibleIds=new Set(scraped.map(g=>gameId(g.id)));
    const liveGames=games.filter(g=>visibleIds.has(gameId(g.id)));
    const candidates=liveGames.filter(g=>shouldDownload(mode,g,knownIds.has(gameId(g.id))));
    const initiallySkipped=liveGames.length-candidates.length;
    let attempted=0,ok=0,failed=0,consecutiveServerFailures=0,circuitBroken=false;
    async function persist(){
      await chrome.storage.local.set({ta_games:games,ta_failures:unresolvedFailures(games)});
    }
    await persist();savedAtLeastOnce=true;
    await progress(`${liveGames.length} visible games. ${candidates.length} selected for ${mode}; ${initiallySkipped} skipped.`,true,
      {count:liveGames.length,candidates:candidates.length,attempted,successful:ok,failed,skipped:initiallySkipped,mode});
    for(let i=0;i<candidates.length;i++) {
      if(stopped)break;
      const game=candidates[i];
      const earlierImage=hasImage(game);
      attempted++;
      await progress(`Image ${i+1}/${candidates.length} • successful ${ok} • failed ${failed} • skipped ${initiallySkipped}\n${game.title}`,true,
        {count:liveGames.length,candidates:candidates.length,attempted,successful:ok,failed,skipped:initiallySkipped,mode});
      const result=await downloadOne(game.image_url,`${folder}/images/${game.id}.png`);
      if(result.ok) {
        ok++;consecutiveServerFailures=0;
        game.image_file=`images/${game.id}.png`;
        game.image_folder=folder;
        game.image_download_status='downloaded';
        game.image_error=null;game.image_last_error_at=null;
        game.image_mime=result.mime;game.image_bytes=result.bytes;
        game.image_download_id=result.download_id;
        game.image_last_downloaded_at=new Date().toISOString();
        game.image_completion_refresh_pending=false;
      } else {
        failed++;
        consecutiveServerFailures=/SERVER_FAILED/.test(result.error||'')?consecutiveServerFailures+1:0;
        if(!earlierImage) {
          game.image_download_status='failed';game.image_file=null;
          game.image_download_id=null;game.image_mime=null;
          game.image_last_downloaded_at=null;
          game.image_error=result.error;
          game.image_last_error_at=new Date().toISOString();
        }
        // A failed refresh cannot destroy an earlier successful image record.
      }
      await persist();
      if(consecutiveServerFailures>=5){circuitBroken=true;break;}
      if(i<candidates.length-1&&!stopped)await sleep(IMAGE_DELAY_MS);
    }
    const reason=circuitBroken?'server_failed_pause':stopped?'stopped':'completed';
    await progress('Exporting games.json and ta_failures.json…',true,
      {count:liveGames.length,candidates:candidates.length,attempted,successful:ok,failed,skipped:initiallySkipped,mode});
    const out=await exportSnapshot(folder,reason);
    await progress(`Done: attempted ${attempted}, downloaded ${ok}, failed ${failed}, skipped ${initiallySkipped}.`+
      (circuitBroken?'\nPaused after 5 consecutive SERVER_FAILED errors.':'')+
      `\nJSON export: ${out.ok?'OK':'FAILED (use manual export)'}.`,false,
      {count:liveGames.length,candidates:candidates.length,attempted,successful:ok,failed,skipped:initiallySkipped,mode,exported:out.ok,circuitBroken});
  } catch(e) {
    let msg='Error: '+String(e?.message||e);
    if(savedAtLeastOnce) {
      try{const out=await exportSnapshot(folder,'error');msg+=out.ok?'\nPartial JSON exported.':'\nExport failed; use manual export.';}catch{}
    }
    await progress(msg,false);
  } finally {active=false;}
}
chrome.runtime.onMessage.addListener((msg,sender,reply)=>{
  if(msg.type==='START') {
    if(active){reply({ok:false,error:'A run is already active.'});return;}
    if(!VALID_MODES.has(msg.mode)){reply({ok:false,error:'Choose Missing Only or New + Incomplete.'});return;}
    const folder=String(msg.folder||'ta-collector').trim();
    if(!/^[\w .-]+$/.test(folder)||folder==='.'||folder==='..'){
      reply({ok:false,error:'Folder must be a single simple subfolder name.'});return;
    }
    if(!Array.isArray(msg.games)||(!msg.fresh&&msg.games.length===0)){
      reply({ok:false,error:'Select your existing games.json, or explicitly check Fresh start.'});return;
    }
    try{readGamesJson({games:msg.games,gamer_id:GAMER_ID});}
    catch(e){reply({ok:false,error:String(e.message||e)});return;}
    reply({ok:true});
    startJob(msg.tabId,msg.mode,folder,msg.games);
  } else if(msg.type==='STOP') {
    stopped=true;reply({ok:true});
  } else if(msg.type==='EXPORT') {
    if(active){reply({ok:false,error:'Wait for the current run to finish.'});return;}
    exportSnapshot(String(msg.folder||'ta-collector').trim(),'manual')
      .then(out=>reply(out)).catch(e=>reply({ok:false,error:String(e.message||e)}));
    return true;
  }
});
