const $=id=>document.getElementById(id);

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
  const e=$(id);if(e)e.style.display=on?"":"none";
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
  h.textContent=item.title;card.appendChild(h);
 }
 if(item.message){
  const p=document.createElement("div");
  p.textContent=item.message;card.appendChild(p);
 }
 if(item.image_url){
  const img=document.createElement("img");
  img.src=item.image_url;
  img.style.cssText=`width:${s.imageWidth||"100%"};height:${s.imageHeight||"auto"};object-fit:${s.imageFit||"cover"};border-radius:${s.imageRadius||"8px"}`;
  card.appendChild(img);
 }
 box.appendChild(card);
}

document.addEventListener("DOMContentLoaded",()=>{
 updateEditorFields();
 refreshPreview();
});
