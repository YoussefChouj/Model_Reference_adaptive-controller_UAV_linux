/* Reusable 1-D Gaussian fusion demo (the heart of the Kalman update).
   Usage: <div id="gfusion"></div> <script src="../assets/gaussian-fusion.js"></script>
          <script>GaussianFusion.mount(document.getElementById('gfusion'));</script>
   Draws prior N(mu1, s1^2), measurement N(mu2, s2^2), and their product (the posterior),
   with live readouts of K = s1^2/(s1^2+s2^2), fused mu, fused sigma. */
var GaussianFusion = (function () {
  function css(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function mount(root) {
    root.innerHTML =
      '<canvas style="width:100%;height:260px;display:block"></canvas>' +
      '<div class="gf-controls" style="display:flex;gap:1.5rem;flex-wrap:wrap;margin-top:0.6rem;font-size:0.85rem">' +
      '<label>&sigma;&#8321; (prediction) <input type="range" min="0.3" max="2.5" step="0.05" value="1.4"></label>' +
      '<label>&sigma;&#8322; (measurement) <input type="range" min="0.3" max="2.5" step="0.05" value="0.7"></label>' +
      '</div>' +
      '<p class="gf-readout mono" style="font-size:0.85rem;margin-top:0.4rem"></p>';

    var canvas = root.querySelector('canvas');
    var sliders = root.querySelectorAll('input');
    var readout = root.querySelector('.gf-readout');
    var mu1 = -1.5, mu2 = 1.0;

    function draw() {
      var dpr = window.devicePixelRatio || 1;
      var w = canvas.clientWidth, h = 260;
      canvas.width = w * dpr; canvas.height = h * dpr;
      var ctx = canvas.getContext('2d');
      ctx.scale(dpr, dpr);

      var s1 = +sliders[0].value, s2 = +sliders[1].value;
      var v1 = s1 * s1, v2 = s2 * s2;
      var K = v1 / (v1 + v2);
      var mu = mu1 + K * (mu2 - mu1);
      var v = (v1 * v2) / (v1 + v2);
      var s = Math.sqrt(v);

      var xmin = -5, xmax = 5;
      function toX(x) { return (x - xmin) / (xmax - xmin) * w; }
      function pdfCurve(m, sd, color, width) {
        ctx.beginPath();
        for (var px = 0; px <= w; px += 2) {
          var x = xmin + px / w * (xmax - xmin);
          var y = Math.exp(-0.5 * Math.pow((x - m) / sd, 2)) / sd; // unnormalised height comparison
          var py = h - 12 - y * (h - 40) * 0.62;
          px === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
        }
        ctx.strokeStyle = color; ctx.lineWidth = width; ctx.stroke();
      }

      ctx.clearRect(0, 0, w, h);
      // baseline
      ctx.strokeStyle = css('--rule'); ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(0, h - 12); ctx.lineTo(w, h - 12); ctx.stroke();

      pdfCurve(mu1, s1, css('--accent'), 1.5);   // prediction
      pdfCurve(mu2, s2, css('--accent2'), 1.5);  // measurement
      pdfCurve(mu, s, css('--ink'), 2.5);        // fused posterior

      // fused mean marker
      ctx.strokeStyle = css('--muted'); ctx.setLineDash([4, 4]);
      ctx.beginPath(); ctx.moveTo(toX(mu), 20); ctx.lineTo(toX(mu), h - 12); ctx.stroke();
      ctx.setLineDash([]);

      ctx.font = '12px ui-monospace, Consolas, monospace';
      ctx.fillStyle = css('--accent');  ctx.fillText('prediction', toX(mu1) - 30, 16);
      ctx.fillStyle = css('--accent2'); ctx.fillText('measurement', toX(mu2) - 35, 16);

      readout.innerHTML =
        'K = &sigma;&#8321;&sup2;/(&sigma;&#8321;&sup2;+&sigma;&#8322;&sup2;) = <strong>' + K.toFixed(2) +
        '</strong> &nbsp;&rarr;&nbsp; fused &mu; = ' + mu.toFixed(2) +
        ', fused &sigma; = <strong>' + s.toFixed(2) + '</strong>' +
        ' (&lt; min(' + s1.toFixed(2) + ', ' + s2.toFixed(2) + ') &mdash; always)';
    }

    sliders.forEach(function (sl) { sl.addEventListener('input', draw); });
    window.addEventListener('resize', draw);
    if (window.matchMedia) window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', draw);
    draw();
  }

  return { mount: mount };
})();
