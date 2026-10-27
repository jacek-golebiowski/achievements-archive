/* Collector data rules.  The selected games.json is the source of truth for
 * existing IDs and image download status on EVERY run.  No migration system. */
const COLLECTOR_GAMER_ID = 1136202;
const VALID_MODES = new Set(['missing','incomplete']);
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
  } else {
    result.image_error=null;
    result.image_last_error_at=null;
  }
  return result;
}
function readGamesJson(document) {
  if(!document || typeof document!=='object' || !Array.isArray(document.games))
    throw Error('Choose a games.json containing a "games" array.');
  if(document.gamer_id!=null && Number(document.gamer_id)!==COLLECTOR_GAMER_ID)
    throw Error('This games.json belongs to another TrueAchievements gamer.');
  const keys=new Set();
  const games=[];
  for(const item of document.games) {
    const id=gameId(item?.id);
    if(!id)throw Error('games.json has a game with a missing/invalid ID.');
    if(keys.has(id))throw Error('games.json has a duplicate game ID: '+id);
    keys.add(id);
    games.push(normalizeGame(item));
  }
  return games;
}
function mergeScrapedGames(reference,live) {
  const ids=new Set(reference.map(g=>gameId(g.id)));
  const byId=new Map(reference.map(g=>[gameId(g.id),normalizeGame(g)]));
  for(const item of live) {
    const id=gameId(item.id);
    if(!id)continue;
    const old=byId.get(id);
    const merged={...(old||{}),...item};
    // The scraper knows achievements but not the archive's private completion flag.
    if(old && old.archive_completed!=null)merged.archive_completed=old.archive_completed;
    // An incomplete -> complete achievement transition needs a FINAL image,
    // even though the current live record is now completed. Carry this intent
    // across unsuccessful downloads so it can be retried on the next run.
    if(old && old.ta_achievements_complete === false && item.ta_achievements_complete === true) {
      merged.image_completion_refresh_pending=true;
    }
    if(!old) {
      merged.image_completion_refresh_pending=false;
      merged.image_download_status='not_attempted';
      merged.image_file=null;
      merged.image_error=null;
    }
    byId.set(id,normalizeGame(merged));
  }
  return {games:[...byId.values()], knownIds:ids};
}
function shouldDownload(mode,game,isKnown) {
  if(mode==='missing')return !hasImage(game);
  if(mode==='incomplete')return !isKnown || game.ta_achievements_complete!==true || game.image_completion_refresh_pending===true;
  throw Error('Unknown synchronization mode.');
}
function unresolvedFailures(games) {
  return games.filter(g=>g.image_download_status==='failed' && !hasImage(g))
    .map(g=>({id:g.id,title:g.title||`Game ${g.id}`,url:g.image_url,
      error:g.image_error||'Unknown download error',time:g.image_last_error_at||null}));
}
function summarizeGames(games) {
  const downloaded=games.filter(hasImage).length;
  const failed=games.filter(g=>g.image_download_status==='failed'&&!hasImage(g)).length;
  return {total:games.length,downloaded,failed,not_attempted:games.length-downloaded-failed};
}
