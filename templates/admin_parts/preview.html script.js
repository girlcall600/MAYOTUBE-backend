
<section id="previewSection">
  <div class="section-title">
    <span>👁️ Live Home Preview</span>
    <button type="button" onclick="refreshPreview()">↻</button>
  </div>

  <div id="livePreview" class="live-preview">
    <div class="preview-empty">Preview will appear here</div>
  </div>

  <div class="section-title">
    <span>Home Content</span>
    <span id="contentCount">0</span>
  </div>

  <div id="homeContent" class="home-content"></div>
</section>

<style>
#previewSection{margin:10px 0}
.section-title{display:flex;justify-content:space-between;align-items:center;padding:7px 10px}
.live-preview{max-height:260px;overflow:auto;padding:8px;border-radius:8px;background:#121212}
.preview-empty{text-align:center;padding:20px;opacity:.6}
.home-content{max-height:320px;overflow:auto}
</style>
