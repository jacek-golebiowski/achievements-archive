const COLLECTOR_GAMER_ID = 1136202;
function gameId(value) {
  const n=Number(value);
  return Number.isSafeInteger(n)&&n>0?String(n):null;
}
function hasImage(game) {
  return game?.image_download_status==='downloaded' &&
    typeof game.image_file==='string' && !!game.image_file.trim();
}
function normalizeGame(game) {
  const result={...game,id:Number(game.id)};
  if(!hasImage(result)) {
    result.image_file=null;
    result.image_download_status=result.image_download_status==='failed'?'failed':'not_attempted';
  } else if(result.image_update_pending!==true && result.image_refresh_pending!==true) {
    result.image_error=null;
    result.image_last_error_at=null;
  }
  result.image_update_pending = result.image_update_pending===true ||
    result.image_refresh_pending===true || result.image_completion_refresh_pending===true || !hasImage(result);
  delete result.image_refresh_pending;
  delete result.image_completion_refresh_pending;
  return result;
}
function readGamesJson(document) {
  if(!document || typeof document!=='object' || !Array.isArray(document.games))
    throw Error('Choose a games.json containing a "games" array.');
  if(document.gamer_id!=null && Number(document.gamer_id)!==COLLECTOR_GAMER_ID)
    throw Error('This games.json belongs to another TrueAchievements gamer.');
  const keys=new Set(), games=[];
  for(const item of document.games) {
    const id=gameId(item?.id);
    if(!id)throw Error('games.json has a game with a missing/invalid ID.');
    if(keys.has(id))throw Error('games.json has a duplicate game ID: '+id);
    keys.add(id); games.push(normalizeGame(item));
  }
  return games;
}
function mergeScrapedGames(reference,live) {
  const byId=new Map(reference.map(g=>[gameId(g.id),normalizeGame(g)]));
  for(const item of live) {
    const id=gameId(item.id);
    if(!id)continue;
    const old=byId.get(id);
    const changed=!!old && (
      old.achievements?.earned!==item.achievements?.earned ||
      old.achievements?.total!==item.achievements?.total
    );
    const {trophy_case,trophy_case_position,...liveFields}=item;
    const merged={...(old||{}),...liveFields};
    if(old && old.archive_completed!=null)merged.archive_completed=old.archive_completed;
    const snapshotChanged=!!old && old.image_achievements_earned!=null &&
      (Number(old.image_achievements_earned)!==item.achievements?.earned ||
       Number(old.image_achievements_total)!==item.achievements?.total);
    merged.image_update_pending=!old || changed || snapshotChanged ||
      old?.image_update_pending===true || old?.image_refresh_pending===true ||
      old?.image_completion_refresh_pending===true || !hasImage(old);
    if(!old) {
      merged.image_download_status='not_attempted';
      merged.image_file=null;
      merged.image_error=null;
    }
    byId.set(id,normalizeGame(merged));
  }
  return {games:[...byId.values()]};
}
function shouldDownload(game) {
  return game.image_update_pending===true || !hasImage(game);
}
function unresolvedFailures(games) {
  return games.filter(g=>g.image_download_status==='failed' || (g.image_update_pending===true && !!g.image_error))
    .map(g=>({id:g.id,title:g.title||`Game ${g.id}`,url:g.image_url,
      error:g.image_error||'Unknown download error',time:g.image_last_error_at||null}));
}
function summarizeGames(games) {
  const downloaded=games.filter(hasImage).length;
  const failed=games.filter(g=>g.image_download_status==='failed'&&!hasImage(g)).length;
  return {total:games.length,downloaded,failed,not_attempted:games.length-downloaded-failed};
}
