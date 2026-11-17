(function(){
  var t=document.getElementById('navtoggle'),s=document.getElementById('side');
  if(t&&s){t.addEventListener('click',function(){s.classList.toggle('open')});
    document.addEventListener('click',function(e){if(s.classList.contains('open')&&!s.contains(e.target)&&e.target!==t){s.classList.remove('open')}})}
  document.addEventListener('submit',function(e){var m=e.target.getAttribute('data-confirm');if(m&&!window.confirm(m)){e.preventDefault()}});
  document.addEventListener('click',function(e){var b=e.target.closest('[data-confirm-click]');if(b&&!window.confirm(b.getAttribute('data-confirm-click'))){e.preventDefault()}});
  // add-row buttons (invoice lines)
  document.addEventListener('click',function(e){var b=e.target.closest('[data-addrow]');if(!b)return;
    var tbody=document.getElementById(b.getAttribute('data-addrow'));var first=tbody.querySelector('tr');var c=first.cloneNode(true);
    c.querySelectorAll('input').forEach(function(i){i.value=i.name==='qty'?'1':''});c.querySelectorAll('select').forEach(function(i){i.selectedIndex=0});tbody.appendChild(c);recalc();});
  // invoice service autofill + totals
  function recalc(){var tot=0;document.querySelectorAll('#lines tr').forEach(function(r){var q=parseFloat(r.querySelector('[name=qty]').value)||0,p=parseFloat(r.querySelector('[name=price]').value)||0;tot+=q*p});
    var rate=parseFloat((document.getElementById('tax_rate')||{}).value)||0;var el=document.getElementById('invtotal');if(el){el.textContent=(tot*(1+rate/100)).toFixed(2)}}
  document.addEventListener('change',function(e){
    if(e.target.matches('#lines select[name=service]')){var o=e.target.selectedOptions[0],r=e.target.closest('tr');if(o&&o.dataset.price){r.querySelector('[name=price]').value=o.dataset.price;if(!r.querySelector('[name=desc]').value){r.querySelector('[name=desc]').value=o.dataset.name}}recalc()}});
  document.addEventListener('input',function(e){if(e.target.closest('#lines')||e.target.id==='tax_rate'){recalc()}});
  // lineup row toggling
  document.addEventListener('change',function(e){if(e.target.matches('[data-inc]')){var r=e.target.closest('tr');r.classList.toggle('muted',!e.target.checked)}});
  // report/pair filters
  var pf=document.getElementById('pairfilter');
  if(pf){pf.addEventListener('input',function(){var v=pf.value.toLowerCase();document.querySelectorAll('#pair option').forEach(function(o){o.hidden=o.value&&o.textContent.toLowerCase().indexOf(v)<0})})}
  document.addEventListener('error',function(e){var t=e.target;if(t&&t.tagName==='IMG'&&t.dataset.fallback){t.replaceWith(document.createTextNode(t.dataset.fallback))}},true);
  setTimeout(function(){document.querySelectorAll('.flash.ok').forEach(function(f){f.style.display='none'})},9000);
})();
document.addEventListener('click',function(e){var p=e.target.closest('[data-print]');if(p){e.preventDefault();window.print()}});
