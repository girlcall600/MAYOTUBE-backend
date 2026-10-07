let adminToken="";

const $=id=>document.getElementById(id);

async function api(url,opt={}){
  const headers=opt.body instanceof FormData
    ? {...(opt.headers||{})}
    : {"Content-Type":"application/json",...(opt.headers||{})};

  if(adminToken)headers["X-Admin-Token"]=adminToken;

  const r=await fetch(url,{
    credentials:"same-origin",
    ...opt,
    headers
  });

  const data=await r.json().catch(()=>({}));

  if(!r.ok)throw new Error(data.error||data.message||`HTTP ${r.status}`);
  return data;
}

async function login(){
  const token=$("tokenInput").value.trim();

  if(!token){
    $("loginError").textContent="Admin Token درج کریں۔";
    return;
  }

  adminToken=token;
  $("loginError").textContent="";

  try{
    await api("/api/admin/status");

    if($("rememberToken").checked)
      localStorage.setItem("mayotube_admin_token",token);
    else
      localStorage.removeItem("mayotube_admin_token");

    $("loginScreen").classList.add("hidden");
    $("app").classList.remove("hidden");
    $("connectionText").textContent="Connected";

    updateEditorFields();
    refreshPreview({});
  }catch(e){
    adminToken="";
    $("loginError").textContent="Login failed: "+e.message;
  }
}

function logout(){
  adminToken="";
  sessionStorage.removeItem("mayotube_admin_token");
  $("app").classList.add("hidden");
  $("loginScreen").classList.remove("hidden");
  $("tokenInput").value="";
}

function updateEditorFields(){
  const t=$("itemType")?.value||"message";

  const m={
    fieldMessage:["message","format"].includes(t),
    fieldDescription:["message","format","donation","advertisement"].includes(t),
    fieldImageUrl:["image","gif","gallery","donation","advertisement"].includes(t),
    fieldVideoUrl:["video","youtube","live"].includes(t),
    fieldAudioUrl:t==="audio",
    fieldLinkUrl:["url","youtube","button","link","advertisement"].includes(t),
    fieldButtonText:["button","donation","advertisement"].includes(t),
    fieldFormat:t==="format",
    fieldDonation:t==="donation",
    fieldLive:t==="live"
  };

  Object.entries(m).forEach(([id,on])=>{
    const e=$(id);
    if(e)e.style.display=on?"":"none";
  });
}

function getStyleControls(){
  return {
    background:$("bgColor")?.value||"#181818",
    color:$("textColor")?.value||"#fff",
    accent:$("accentColor")?.value||"#FFD600",
    width:$("boxWidth")?.value||"100%",
    height:$("boxHeight")?.value||"auto",
    padding:$("boxPadding")?.value||"12px",
    radius:$("boxRadius")?.value||"8px",
    borderWidth:$("borderWidth")?.value||"0",
    borderColor:$("borderColor")?.value||"#333",
    shadow:$("boxShadow")?.value||"none",
    imageWidth:$("imageWidth")?.value||"100%",
    imageHeight:$("imageHeight")?.value||"auto",
    imageFit:$("imageFit")?.value||"cover",
    imageRadius:$("imageRadius")?.value||"8px",
    videoWidth:$("videoWidth")?.value||"100%",
    videoHeight:$("videoHeight")?.value||"auto",
    autoplay:$("videoAutoplay")?.checked||false,
    muted:$("videoMuted")?.checked||false,
    loop:$("videoLoop")?.checked||false,
    controls:$("videoControls")?.checked!==false,
    buttonColor:$("buttonColor")?.value||"#FFD600",
    buttonTextColor:$("buttonTextColor")?.value||"#000",
    buttonRadius:$("buttonRadius")?.value||"8px",
    linkTarget:$("linkTarget")?.value||"_self"
  };
}

function getFormItem(){
  return {
    type:$("itemType")?.value||"message",
    title:$("itemTitle")?.value.trim()||"",
    message:$("itemMessage")?.value.trim()||"",
    description:$("itemDescription")?.value.trim()||"",
    image_url:$("imageUrl")?.value.trim()||"",
    video_url:$("videoUrl")?.value.trim()||"",
    audio_url:$("audioUrl")?.value.trim()||"",
    link_url:$("linkUrl")?.value.trim()||"",
    button_text:$("buttonText")?.value.trim()||"",
    order:Number($("itemOrder")?.value||0),
    enabled:$("itemEnabled")?.checked!==false,
    style:getStyleControls()
  };
}

async function saveItem(){
  try{
    const id=$("itemId")?.value.trim();
    const item=getFormItem();
    const url=id
      ?"/api/admin/content/"+encodeURIComponent(id)
      :"/api/admin/content";

    const result=await api(url,{
      method:id?"PUT":"POST",
      body:JSON.stringify(item)
    });

    const saved=result.item||result.content||result;

    if(saved?.id)$("itemId").value=saved.id;

    refreshPreview(saved);
    alert("Content saved successfully.");
  }catch(e){
    alert("Save failed: "+e.message);
  }
}

function newItem(){
  [
    "itemId","itemTitle","itemMessage","itemDescription",
    "imageUrl","videoUrl","audioUrl","linkUrl","buttonText"
  ].forEach(id=>{
    if($(id))$(id).value="";
  });

  if($("itemType"))$("itemType").value="message";
  if($("itemOrder"))$("itemOrder").value="0";
  if($("itemEnabled"))$("itemEnabled").checked=true;

  updateEditorFields();
  refreshPreview({});
}

function refreshPreview(item={}){
  const box=$("livePreview");
  if(!box)return;

  const s=item.style||getStyleControls();

  box.innerHTML="";

  const card=document.createElement("div");

  Object.assign(card.style,{
    width:s.width||"100%",
    minHeight:s.height||"auto",
    padding:s.padding||"12px",
    borderRadius:s.radius||"8px",
    background:s.background||"#181818",
    color:s.color||"#fff",
    border:`${s.borderWidth||0}px solid ${s.borderColor||"#333"}`
  });

  if(item.title){
    const h=document.createElement("b");
    h.textContent=item.title;
    card.appendChild(h);
  }

  if(item.message){
    const p=document.createElement("div");
    p.textContent=item.message;
    card.appendChild(p);
  }

  if(item.image_url){
    const img=document.createElement("img");
    img.src=item.image_url;
    img.style.cssText=
      `width:${s.imageWidth||"100%"};`+
      `height:${s.imageHeight||"auto"};`+
      `object-fit:${s.imageFit||"cover"};`+
      `border-radius:${s.imageRadius||"8px"};`;
    card.appendChild(img);
  }

  box.appendChild(card);
}

async function initialize(){
  updateEditorFields();
  refreshPreview({});
}

document.addEventListener("DOMContentLoaded",()=>{
  const saved=localStorage.getItem("mayotube_admin_token");

  if(saved){
    $("tokenInput").value=saved;
    $("rememberToken").checked=true;
    login();
  }
});
