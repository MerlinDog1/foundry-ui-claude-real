const STYLES=["stippling","cross-hatching","woodcut","copperplate","mezzotint","technical-sketch","minimalist-logo","etched-obsidian"];
const prompts={
 woodcut:["Storm-forged raven over ruined cathedral","Cyborg ronin duel in moonlit bamboo"],
 stippling:["Ancient astronomer and brass orrery","Desert shrine with giant beetle sigils"],
 "cross-hatching":["Victorian airship over frozen sea","Knight facing a mechanical basilisk"]
};

const $=s=>document.querySelector(s);
let state={style:"woodcut",source:"generate",aspectRatio:"1:1",resolution:"1K",traceFormat:"svg"};

function setChip(group,v){group.querySelectorAll('button').forEach(b=>b.classList.toggle('active',b.dataset.v===v));}
function wireChip(id,key){const g=$(id);g.onclick=e=>{if(e.target.tagName!=="BUTTON")return;state[key]=e.target.dataset.v;setChip(g,state[key]);if(id==="#sourceMode")$('#uploadBox').classList.toggle('hidden',state.source!=="upload")};}

function makeStyles(){
  const grid=$('#styleGrid');
  grid.innerHTML=STYLES.map(s=>`<div class="style ${s===state.style?'active':''}" data-style="${s}"><img src="/assets/${s}.png"/><small>${s}</small></div>`).join('');
  grid.onclick=e=>{const card=e.target.closest('.style'); if(!card)return; state.style=card.dataset.style; grid.querySelectorAll('.style').forEach(x=>x.classList.remove('active')); card.classList.add('active');};
}

function progress(p,txt){$('#progress').style.width=`${p}%`; $('#status').textContent=txt;}
function setPreview(stage,url){$(`#prev-${stage}`).src=url+`?t=${Date.now()}`;}

async function post(url,data){const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data||{})});const j=await r.json();if(!j.ok)throw new Error(j.error||'request failed');return j;}

$('#inspire').onclick=()=>{const picks=prompts[state.style]||prompts.woodcut;$('#prompt').value=picks[Math.floor(Math.random()*picks.length)]};

$('#uploadBtn').onclick=async()=>{
  const f=$('#file').files[0]; if(!f) return alert('Pick a file first');
  const dataUrl=await new Promise((res,rej)=>{const fr=new FileReader(); fr.onload=()=>res(fr.result); fr.onerror=rej; fr.readAsDataURL(f);});
  const j=await post('/upload',{dataUrl});
  if(!j.ok) return alert(j.error||'Upload failed');
  setPreview('generated','/preview/generated');
};

$('#run').onclick=async()=>{
  try{
    const prompt=$('#prompt').value.trim();
    const doStyle=$('#doStyle').checked, doUpscale=$('#doUpscale').checked, doTrace=$('#doTrace').checked;
    progress(4,'Starting...');

    if(state.source==='generate'){
      await post('/generate',{prompt,style:state.style,aspectRatio:state.aspectRatio,resolution:state.resolution});
    }
    setPreview('generated','/preview/generated'); progress(25,'Generated');

    if(doStyle){await post('/style',{style:state.style}); setPreview('styled','/preview/styled'); progress(50,'Styled');}
    if(doUpscale){await post('/upscale',{scale:4}); setPreview('upscaled','/preview/upscaled'); progress(75,'Upscaled');}
    if(doTrace){await post('/trace',{speckle:+$('#speckle').value,format:state.traceFormat}); setPreview('traced',state.traceFormat==='svg'?'/preview/traced':'/preview/traced-png'); progress(100,'Traced');}

    saveToLibrary();
  }catch(err){progress(0,'Error: '+err.message);}
};

function saveToLibrary(){
  const item={id:Date.now(),prompt:$('#prompt').value,style:state.style,src:$('#prev-generated').src,traced:$('#prev-traced').src,format:state.traceFormat};
  const arr=JSON.parse(localStorage.getItem('foundryLib')||'[]'); arr.unshift(item); localStorage.setItem('foundryLib',JSON.stringify(arr.slice(0,24))); renderLibrary();
}
function del(id){const arr=JSON.parse(localStorage.getItem('foundryLib')||'[]').filter(x=>x.id!==id); localStorage.setItem('foundryLib',JSON.stringify(arr)); renderLibrary();}
function renderLibrary(){
  const arr=JSON.parse(localStorage.getItem('foundryLib')||'[]');
  $('#library').innerHTML=arr.map(x=>`<div class="lib"><img src="${x.traced||x.src}"><small>${x.style}</small><div class="row"><button data-r='${x.id}'>Rerun</button><button data-d='${x.id}'>Delete</button></div></div>`).join('')||'<small>No items yet.</small>';
  $('#library').onclick=e=>{const r=e.target.dataset.r,d=e.target.dataset.d;if(r){const item=arr.find(x=>x.id==r); $('#prompt').value=item.prompt; state.style=item.style; makeStyles();} if(d)del(+d)};
}

$('#exportZip').onclick=()=>{
  const arr=JSON.parse(localStorage.getItem('foundryLib')||'[]');
  const blob=new Blob([JSON.stringify(arr,null,2)],{type:'application/json'});
  const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download='foundry-library.json'; a.click();
};

wireChip('#sourceMode','source'); wireChip('#aspect','aspectRatio'); wireChip('#resolution','resolution'); wireChip('#traceFormat','traceFormat');
makeStyles(); renderLibrary();