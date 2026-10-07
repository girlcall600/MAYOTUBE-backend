<section id="previewSection">

  <div class="section-title compact-title">
    <span>👁️ Live Home Preview</span>
    <button type="button" onclick="refreshPreviewFromForm()">↻</button>
  </div>

  <div id="livePreview" class="live-preview">
    <div class="preview-empty">
      Preview will appear here
    </div>
  </div>

  <div class="section-title compact-title">
    <span>Home Content</span>
    <span id="contentCount">0</span>
  </div>

  <div id="homeContent" class="home-content"></div>

</section>

<style>
#previewSection{
  margin:7px 0;
}

.compact-title{
  display:flex;
  justify-content:space-between;
  align-items:center;
  padding:5px 8px;
  font-size:13px;
}

.compact-title button{
  min-width:28px;
  min-height:28px;
}

.live-preview{
  height:170px;
  max-height:170px;
  overflow:auto;
  padding:6px;
  border-radius:7px;
  background:#121212;
  box-sizing:border-box;
}

.preview-empty{
  text-align:center;
  padding:15px;
  opacity:.55;
  font-size:12px;
}

.home-content{
  height:190px;
  max-height:190px;
  overflow:auto;
  padding:4px;
  box-sizing:border-box;
}

.home-content-item{
  padding:7px;
  margin-bottom:5px;
  border:1px solid #303030;
  border-radius:6px;
  background:#181818;
  font-size:12px;
}

.home-content-item-title{
  font-weight:600;
}

.home-content-item-type{
  opacity:.55;
  font-size:11px;
}
</style>
