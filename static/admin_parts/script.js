let adminToken = "";

const $ = id => document.getElementById(id);


/* ============================================================
   API
   ============================================================ */

async function api(url, opt = {}) {

  const headers =
    opt.body instanceof FormData
      ? {...(opt.headers || {})}
      : {
          "Content-Type":"application/json",
          ...(opt.headers || {})
        };

  if(adminToken){
    headers["X-Admin-Token"] = adminToken;
  }

  const response = await fetch(url,{
    credentials:"same-origin",
    ...opt,
    headers
  });

  const data =
    await response.json().catch(()=>({}));

  if(!response.ok){
    throw new Error(
      data.error ||
      data.message ||
      `HTTP ${response.status}`
    );
  }

  return data;
}


/* ============================================================
   LOGIN
   ============================================================ */

async function login(){

  const token =
    $("tokenInput")?.value.trim();

  if(!token){

    $("loginError").textContent =
      "Admin Token درج کریں۔";

    return;
  }

  adminToken = token;

  $("loginError").textContent = "";

  try{

    await api("/api/admin/status");

    if($("rememberToken")?.checked){

      localStorage.setItem(
        "mayotube_admin_token",
        token
      );

    }else{

      localStorage.removeItem(
        "mayotube_admin_token"
      );
    }

    $("loginScreen")?.classList.add("hidden");
    $("app")?.classList.remove("hidden");

    if($("connectionText")){
      $("connectionText").textContent =
        "Connected";
    }

    initialize();

  }catch(e){

    adminToken = "";

    $("loginError").textContent =
      "Login failed: " + e.message;
  }
}


/* ============================================================
   LOGOUT
   ============================================================ */

function logout(){

  adminToken = "";

  $("app")?.classList.add("hidden");
  $("loginScreen")?.classList.remove("hidden");

  if($("tokenInput")){
    $("tokenInput").value = "";
  }
}


/* ============================================================
   CONTENT TYPE
   ============================================================ */

function updateEditorFields(){

  const type =
    $("itemType")?.value || "message";

  const fields = {

    fieldTitle:[
      "message",
      "image",
      "url",
      "video",
      "youtube",
      "audio",
      "donation",
      "button",
      "link",
      "live",
      "gif",
      "gallery",
      "advertisement",
      "format"
    ].includes(type),

    fieldMessage:[
      "message",
      "format"
    ].includes(type),

    fieldDescription:[
      "message",
      "format",
      "donation",
      "advertisement"
    ].includes(type),

    fieldImageUrl:[
      "image",
      "gif",
      "gallery",
      "donation",
      "advertisement"
    ].includes(type),

    fieldVideoUrl:[
      "video",
      "youtube",
      "live"
    ].includes(type),

    fieldAudioUrl:
      type === "audio",

    fieldLinkUrl:[
      "url",
      "youtube",
      "button",
      "link",
      "advertisement"
    ].includes(type),

    fieldButtonText:[
      "button",
      "donation",
      "advertisement"
    ].includes(type),

    fieldFormat:
      type === "format",

    fieldDonation:
      type === "donation",

    fieldLive:
      type === "live"
  };

  Object.entries(fields).forEach(
    ([id,show])=>{

      const element = $(id);

      if(element){
        element.style.display =
          show ? "" : "none";
      }

    }
  );
}


/* ============================================================
   SCHEDULE
   ============================================================ */

function toggleScheduleFields(){

  const enabled =
    $("scheduleEnabled")?.checked;

  const fields =
    $("scheduleFields");

  if(fields){

    fields.style.display =
      enabled ? "grid" : "none";
  }
}


/* ============================================================
   STYLE CONTROLS
   ============================================================ */

function getStyleControls(){

  return {

    background:
      $("bgColor")?.value || "#181818",

    color:
      $("textColor")?.value || "#ffffff",

    accent:
      $("accentColor")?.value || "#FFD600",

    width:
      $("boxWidth")?.value || "100%",

    height:
      $("boxHeight")?.value || "auto",

    padding:
      $("boxPadding")?.value || "12px",

    radius:
      $("boxRadius")?.value || "8px",

    borderWidth:
      $("borderWidth")?.value || "0",

    borderColor:
      $("borderColor")?.value || "#333333",

    shadow:
      $("boxShadow")?.value || "none",

    imageWidth:
      $("imageWidth")?.value || "100%",

    imageHeight:
      $("imageHeight")?.value || "auto",

    imageFit:
      $("imageFit")?.value || "cover",

    imageRadius:
      $("imageRadius")?.value || "8px",

    videoWidth:
      $("videoWidth")?.value || "100%",

    videoHeight:
      $("videoHeight")?.value || "auto",

    autoplay:
      $("videoAutoplay")?.checked || false,

    muted:
      $("videoMuted")?.checked || false,

    loop:
      $("videoLoop")?.checked || false,

    controls:
      $("videoControls")?.checked !== false,

    buttonColor:
      $("buttonColor")?.value || "#FFD600",

    buttonTextColor:
      $("buttonTextColor")?.value || "#000000",

    buttonRadius:
      $("buttonRadius")?.value || "8px",

    linkTarget:
      $("linkTarget")?.value || "_self"
  };
}


/* ============================================================
   FORM DATA
   ============================================================ */

function getFormItem(){

  return {

    type:
      $("itemType")?.value || "message",

    title:
      $("itemTitle")?.value.trim() || "",

    message:
      $("itemMessage")?.value.trim() || "",

    description:
      $("itemDescription")?.value.trim() || "",

    image_url:
      $("imageUrl")?.value.trim() || "",

    video_url:
      $("videoUrl")?.value.trim() || "",

    audio_url:
      $("audioUrl")?.value.trim() || "",

    link_url:
      $("linkUrl")?.value.trim() || "",

    button_text:
      $("buttonText")?.value.trim() || "",

    content_format:
      $("contentFormat")?.value || "plain",

    donation_url:
      $("donationUrl")?.value.trim() || "",

    live_url:
      $("liveUrl")?.value.trim() || "",

    order:
      Number($("itemOrder")?.value || 0),

    enabled:
      $("itemEnabled")?.checked !== false,

    style:
      getStyleControls(),

    schedule:{

      enabled:
        $("scheduleEnabled")?.checked || false,

      start:
        $("scheduleStart")?.value || "",

      end:
        $("scheduleEnd")?.value || ""
    }
  };
}


/* ============================================================
   SAVE CONTENT
   ============================================================ */

async function saveItem(){

  try{

    const id =
      $("itemId")?.value.trim();

    const item =
      getFormItem();

    const url = id
      ? "/api/admin/content/" +
        encodeURIComponent(id)
      : "/api/admin/content";

    const result =
      await api(url,{

        method:
          id ? "PUT" : "POST",

        body:
          JSON.stringify(item)
      });

    const saved =
      result.item ||
      result.content ||
      result;

    if(saved?.id){

      $("itemId").value =
        saved.id;
    }

    refreshPreview(saved);

    alert(
      "Content saved successfully."
    );

  }catch(e){

    alert(
      "Save failed: " +
      e.message
    );
  }
}


/* ============================================================
   NEW CONTENT
   ============================================================ */

function newItem(){

  const fields = [

    "itemId",
    "itemTitle",
    "itemMessage",
    "itemDescription",
    "imageUrl",
    "videoUrl",
    "audioUrl",
    "linkUrl",
    "buttonText",
    "donationUrl",
    "liveUrl",
    "scheduleStart",
    "scheduleEnd"
  ];

  fields.forEach(id=>{

    const element = $(id);

    if(element){
      element.value = "";
    }
  });

  if($("itemType")){
    $("itemType").value =
      "message";
  }

  if($("itemOrder")){
    $("itemOrder").value = "0";
  }

  if($("itemEnabled")){
    $("itemEnabled").checked = true;
  }

  if($("scheduleEnabled")){
    $("scheduleEnabled").checked = false;
  }

  if($("contentFormat")){
    $("contentFormat").value =
      "plain";
  }

  updateEditorFields();
  toggleScheduleFields();
  refreshPreviewFromForm();
}


/* ============================================================
   SHADOW
   ============================================================ */

function getShadow(value){

  if(value === "small"){
    return "0 2px 6px rgba(0,0,0,.35)";
  }

  if(value === "medium"){
    return "0 4px 12px rgba(0,0,0,.45)";
  }

  if(value === "large"){
    return "0 8px 24px rgba(0,0,0,.55)";
  }

  return "none";
}


/* ============================================================
   PREVIEW FROM FORM
   ============================================================ */

function refreshPreviewFromForm(){

  const item =
    getFormItem();

  refreshPreview(item);
}


/* ============================================================
   LIVE PREVIEW
   ============================================================ */

function refreshPreview(item = {}){

  const box =
    $("livePreview");

  if(!box){
    return;
  }

  const style =
    item.style || getStyleControls();

  const type =
    item.type ||
    $("itemType")?.value ||
    "message";

  box.innerHTML = "";

  const card =
    document.createElement("div");

  Object.assign(
    card.style,
    {

      width:
        style.width || "100%",

      minHeight:
        style.height || "auto",

      padding:
        style.padding || "12px",

      borderRadius:
        style.radius || "8px",

      background:
        style.background || "#181818",

      color:
        style.color || "#ffffff",

      border:
        `${style.borderWidth || 0}px solid ` +
        `${style.borderColor || "#333333"}`,

      boxShadow:
        getShadow(style.shadow),

      boxSizing:
        "border-box",

      overflow:
        "hidden"
    }
  );


  /* TITLE */

  if(item.title){

    const title =
      document.createElement("div");

    title.textContent =
      item.title;

    title.style.fontWeight =
      "700";

    title.style.marginBottom =
      "6px";

    card.appendChild(title);
  }


  /* MESSAGE */

  if(
    item.message &&
    [
      "message",
      "format"
    ].includes(type)
  ){

    const message =
      document.createElement("div");

    message.textContent =
      item.message;

    if(
      item.content_format ===
      "bold"
    ){

      message.style.fontWeight =
        "700";
    }

    if(
      item.content_format ===
      "center"
    ){

      message.style.textAlign =
        "center";
    }

    card.appendChild(message);
  }


  /* DESCRIPTION */

  if(item.description){

    const description =
      document.createElement("div");

    description.textContent =
      item.description;

    description.style.marginTop =
      "6px";

    description.style.opacity =
      ".8";

    card.appendChild(description);
  }


  /* IMAGE */

  if(item.image_url){

    const image =
      document.createElement("img");

    image.src =
      item.image_url;

    image.style.display =
      "block";

    image.style.width =
      style.imageWidth || "100%";

    image.style.height =
      style.imageHeight || "auto";

    image.style.objectFit =
      style.imageFit || "cover";

    image.style.borderRadius =
      style.imageRadius || "8px";

    image.style.marginTop =
      "7px";

    card.appendChild(image);
  }


  /* VIDEO */

  if(
    item.video_url &&
    [
      "video",
      "youtube",
      "live"
    ].includes(type)
  ){

    const video =
      document.createElement("video");

    video.src =
      item.video_url;

    video.style.width =
      style.videoWidth || "100%";

    video.style.height =
      style.videoHeight || "auto";

    video.style.display =
      "block";

    video.style.marginTop =
      "7px";

    video.controls =
      style.controls !== false;

    video.autoplay =
      style.autoplay === true;

    video.muted =
      style.muted === true;

    video.loop =
      style.loop === true;

    card.appendChild(video);
  }


  /* AUDIO */

  if(
    item.audio_url &&
    type === "audio"
  ){

    const audio =
      document.createElement("audio");

    audio.src =
      item.audio_url;

    audio.controls =
      true;

    audio.style.width =
      "100%";

    card.appendChild(audio);
  }


  /* LINK */

  if(
    item.link_url &&
    [
      "url",
      "youtube",
      "link"
    ].includes(type)
  ){

    const link =
      document.createElement("a");

    link.href =
      item.link_url;

    link.textContent =
      item.link_url;

    link.target =
      style.linkTarget || "_self";

    link.style.color =
      style.accent || "#FFD600";

    link.style.display =
      "inline-block";

    link.style.marginTop =
      "7px";

    card.appendChild(link);
  }


  /* BUTTON */

  if(
    item.button_text &&
    [
      "button",
      "donation",
      "advertisement"
    ].includes(type)
  ){

    const button =
      document.createElement("button");

    button.textContent =
      item.button_text;

    button.style.background =
      style.buttonColor ||
      "#FFD600";

    button.style.color =
      style.buttonTextColor ||
      "#000000";

    button.style.border =
      "0";

    button.style.padding =
      "8px 14px";

    button.style.borderRadius =
      style.buttonRadius ||
      "8px";

    button.style.marginTop =
      "7px";

    card.appendChild(button);
  }


  if(!card.children.length){

    const empty =
      document.createElement("div");

    empty.textContent =
      "Preview will appear here";

    empty.style.opacity =
      ".5";

    card.appendChild(empty);
  }

  box.appendChild(card);
}


/* ============================================================
   INITIALIZE
   ============================================================ */

function initialize(){

  updateEditorFields();

  toggleScheduleFields();

  refreshPreviewFromForm();
}


/* ============================================================
   DOM READY
   ============================================================ */

document.addEventListener(
  "DOMContentLoaded",
  ()=>{

    updateEditorFields();

    toggleScheduleFields();

    const saved =
      localStorage.getItem(
        "mayotube_admin_token"
      );

    if(saved){

      if($("tokenInput")){
        $("tokenInput").value =
          saved;
      }

      if($("rememberToken")){
        $("rememberToken").checked =
          true;
      }

      login();

    }else{

      refreshPreviewFromForm();
    }
  }
);
