(function(){
  var cfg=JSON.parse(document.getElementById('cfg').textContent);
  var $=function(id){return document.getElementById(id)};
  if(!$('evform')){bindEdit();return}
  var st={team:null,type:null,player:null,outcome:null,sx:null,sy:null,ex:null,ey:null,editing:null,editStatus:null};
  var memo=JSON.parse(sessionStorage.getItem('fdpa_'+cfg.mid)||'{}');
  if(memo.period)$('period').value=memo.period; if(memo.minute!=null)$('minute').value=memo.minute; if(memo.team)pickTeam(memo.team);
  function toast(msg,kind){var t=document.createElement('div');t.className='toast '+(kind||'ok');t.textContent=msg;document.body.appendChild(t);setTimeout(function(){t.remove()},3200)}
  function typeById(id){return cfg.types.filter(function(t){return t.id===id})[0]}
  function drawTypes(){var box=$('types');box.innerHTML='';
    cfg.types.forEach(function(t){var b=document.createElement('button');b.type='button';b.className='pill'+(st.type===t.id?' on':'');b.textContent=t.name;b.onclick=function(){pickType(t.id)};box.appendChild(b)})}
  function pickTeam(id){st.team=parseInt(id,10);document.querySelectorAll('#teams .pill').forEach(function(b){b.classList.toggle('on',parseInt(b.dataset.team,10)===st.team)});
    if(st.player){var p=cfg.players.filter(function(x){return x.id===st.player})[0];var ty=typeById(st.type)||{};if(p&&p.team!==st.team&&ty.code!=='own_goal')st.player=null}
    drawPlayers();drawRelated()}
  function drawPlayers(){var box=$('players');box.innerHTML='';
    var list=cfg.players.filter(function(p){return p.team===st.team});
    if(!st.team){box.innerHTML='<span class="muted">Choose a team first.</span>';return}
    if(!list.length){box.innerHTML='<span class="muted">No lineup for this team yet.</span>';return}
    list.forEach(function(p){var b=document.createElement('button');b.type='button';b.className='pill'+(st.player===p.id?' sel':'');
      b.textContent=(p.shirt?p.shirt+'  ':'')+p.name+(p.status!=='played'?' (not played)':'');b.onclick=function(){st.player=p.id;drawPlayers();drawRelated()};box.appendChild(b)})}
  function drawRelated(){var t=typeById(st.type);var sel=$('related');
    if(!t||!t.related_label){$('relbox').classList.add('hide');return}
    $('relbox').classList.remove('hide');$('rellabel').textContent=t.related_label+' (optional)';
    var cur=sel.value;sel.innerHTML='<option value="">- none -</option>';
    var sameTeam=t.code==='goal'||t.code==='pass'||t.code==='cross'||t.code==='key_pass'||t.code==='assist'||t.code==='substitution';
    cfg.players.forEach(function(p){if(sameTeam&&p.team!==st.team)return;if(!sameTeam&&p.team===st.team&&t.code!=='foul')return;
      var o=document.createElement('option');o.value=p.id;o.textContent=(p.shirt?p.shirt+' ':'')+p.name;sel.appendChild(o)});sel.value=cur}
  function pickType(id){st.type=id;var t=typeById(id);drawTypes();
    $('playerlabel').textContent=t.needs_player?'Player':'Player (optional)';
    $('outbox').classList.toggle('hide',!t.outcomes.length);var ob=$('outcomes');ob.innerHTML='';st.outcome=null;
    t.outcomes.forEach(function(o){var b=document.createElement('button');b.type='button';b.className='pill';b.textContent=o.replace(/_/g,' ');b.onclick=function(){st.outcome=o;[].forEach.call(ob.children,function(c){c.classList.remove('on')});b.classList.add('on')};ob.appendChild(b)});
    $('spbox').classList.toggle('hide',!t.set_piece);
    $('pitchbox').classList.toggle('hide',t.coords==='none');$('pitchhelp').textContent=t.coords==='start_end'?'(tap start, then tap end)':'(tap where it happened)';
    clearPitch();drawRelated()}
  function clearPitch(){st.sx=st.sy=st.ex=st.ey=null;[].forEach.call(document.querySelectorAll('#pitch .dot'),function(d){d.remove()})}
  $('clearpitch').onclick=clearPitch;
  $('pitch').addEventListener('click',function(e){var r=this.getBoundingClientRect();var x=Math.max(0,Math.min(100,(e.clientX-r.left)/r.width*100)),y=Math.max(0,Math.min(100,(e.clientY-r.top)/r.height*100));
    var t=typeById(st.type)||{};function dot(x,y,end){var d=document.createElement('div');d.className='dot'+(end?' end':'');d.style.left=x+'%';d.style.top=y+'%';$('pitch').appendChild(d)}
    if(st.sx===null||t.coords!=='start_end'||st.ex!==null){clearPitch();st.sx=x;st.sy=y;dot(x,y,false)}else{st.ex=x;st.ey=y;dot(x,y,true)}});
  document.querySelectorAll('#teams .pill').forEach(function(b){b.onclick=function(){pickTeam(b.dataset.team)}});
  drawTypes();drawPlayers();
  function reset(keepEdit){st.type=null;st.player=null;st.outcome=null;clearPitch();$('outbox').classList.add('hide');$('relbox').classList.add('hide');$('spbox').classList.add('hide');$('pitchbox').classList.add('hide');
    $('notes').value='';$('vts').value='';$('second').value='';$('reason').value='';$('related').value='';$('setpiece').value='';st.editing=null;st.editStatus=null;
    $('reasonbox').classList.add('hide');$('cancelEdit').classList.add('hide');$('formtitle').textContent='Record an event';$('save').textContent='Save as draft';drawTypes();drawPlayers()}
  $('cancelEdit').onclick=function(){reset()};
  function val(id){var v=$(id).value;return v===''?null:v}
  function send(confirmDup){
    var t=typeById(st.type);if(!st.team){toast('Choose a team','error');return}if(!t){toast('Choose an event','error');return}
    var body={id:st.editing,team_id:st.team,event_type_id:st.type,player_id:st.player,outcome:st.outcome,related_player_id:val('related'),set_piece_type:val('setpiece'),
      period:$('period').value,minute:val('minute'),second:val('second'),x_start:st.sx,y_start:st.sy,x_end:st.ex,y_end:st.ey,video_timestamp:val('vts'),notes:$('notes').value,reason:$('reason').value,confirm_duplicate:!!confirmDup};
    $('save').disabled=true;
    fetch('/collect/'+cfg.mid+'/event',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':cfg.csrf},body:JSON.stringify(body)})
    .then(function(r){return r.json().then(function(j){return {s:r.status,j:j}})}).then(function(x){$('save').disabled=false;
      if(x.j.ok){sessionStorage.setItem('fdpa_'+cfg.mid,JSON.stringify({team:st.team,period:$('period').value,minute:$('minute').value}));toast(x.j.message);setTimeout(function(){location.reload()},500)}
      else if(x.j.duplicate){if(window.confirm(x.j.errors[0]+'\n\nSave it anyway?'))send(true)}
      else{toast((x.j.errors||['Could not save'])[0],'error');if(x.j.errors&&x.j.errors.length>1)alert(x.j.errors.join('\n'))}})
    .catch(function(){$('save').disabled=false;
      if(!st.editing){var q=getQ();body.queued_at=new Date().toISOString();q.push(body);setQ(q);
        sessionStorage.setItem('fdpa_'+cfg.mid,JSON.stringify({team:st.team,period:$('period').value,minute:$('minute').value}));
        toast('No connection - event kept on this phone ('+q.length+' waiting). It syncs automatically when you are online.','warn');reset()}
      else{toast('No connection. This correction was NOT saved - try again when online.','error')}})}
  // ---- offline queue: new events are kept in the phone's storage until the server confirms them
  var QK='fdpa_q_'+cfg.mid;
  function getQ(){try{return JSON.parse(localStorage.getItem(QK)||'[]')}catch(e){return []}}
  function setQ(q){localStorage.setItem(QK,JSON.stringify(q));drawPending()}
  function drawPending(){var q=getQ(),b=$('pending');if(!b)return;b.classList.toggle('hide',!q.length);$('pendcount').textContent=q.length}
  var syncing=false;
  function syncQ(){if(syncing)return;var q=getQ();if(!q.length)return;syncing=true;
    (function next(){var q=getQ();if(!q.length){syncing=false;toast('All saved events synced.');setTimeout(function(){location.reload()},700);return}
      var item=q[0];
      fetch('/collect/'+cfg.mid+'/event',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':cfg.csrf},body:JSON.stringify(item)})
      .then(function(r){return r.json().then(function(j){return {s:r.status,j:j}})}).then(function(x){
        if(x.s===403&&!x.j.ok&&x.j.errors){syncing=false;alert('Cannot sync: '+x.j.errors[0]);return}
        if(!x.j.ok&&!x.j.duplicate){alert('A queued event was rejected and removed: '+(x.j.errors||[]).join(' '))}
        q.shift();setQ(q);next()})
      .catch(function(){syncing=false;toast('Still offline - events are safe on this phone.','warn')})})()}
  window.addEventListener('online',syncQ);
  var sb=$('syncnow');if(sb)sb.onclick=syncQ;
  drawPending();if(getQ().length&&navigator.onLine)syncQ();
  $('save').onclick=function(){send(false)};
  function bindEditBtns(){document.querySelectorAll('[data-edit]').forEach(function(b){b.onclick=function(){var e=cfg.events[b.dataset.edit];if(!e)return;
    st.editing=e.id;st.editStatus=e.validation_status;pickTeam(e.team_id);pickType(e.event_type_id);st.player=e.player_id;st.outcome=e.outcome;drawPlayers();
    [].forEach.call($('outcomes').children,function(c){c.classList.toggle('on',c.textContent.replace(/ /g,'_')===e.outcome)});
    drawRelated();$('related').value=e.related_player_id||'';$('setpiece').value=e.set_piece_type||'';$('period').value=e.period;$('minute').value=e.minute==null?'':e.minute;$('second').value=e.second==null?'':e.second;
    $('notes').value=e.notes||'';$('vts').value=e.video_timestamp==null?'':e.video_timestamp;
    st.sx=e.x_start;st.sy=e.y_start;st.ex=e.x_end;st.ey=e.y_end;
    if(e.validation_status!=='draft'){$('reasonbox').classList.remove('hide')}$('cancelEdit').classList.remove('hide');$('formtitle').textContent='Editing event #'+e.id;$('save').textContent='Save changes';
    window.scrollTo({top:$('evform').offsetTop-20,behavior:'smooth'})}})}
  bindEditBtns();
  function bindEdit(){}
})();
