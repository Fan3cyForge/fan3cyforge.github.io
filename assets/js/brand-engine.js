(function () {
    "use strict";

    /**
     * 任何 fetch 到本站 JSON 時使用：?v=<timestamp> 避免 GitHub Pages CDN 舊快取
     */
    window.f3fCacheBust = function f3fCacheBust(url) {
        if (!url || typeof url !== "string") return url;
        if (/^https?:\/\//i.test(url) && url.indexOf(location.origin) !== 0) {
            return url;
        }
        var sep = url.indexOf("?") >= 0 ? "&" : "?";
        return url + sep + "v=" + Date.now();
    };

    /**
     * 掃描常見遺留色（橙／紫系 Tailwind / 舊主題）並以品牌色強制覆寫。
     * 預設延後執行，避免阻塞首屏繪製；教學頁動態載入 Markdown 後可呼叫 f3fBrandSweep(root)。
     */
    function appliesOrangePurple(el, style) {
        var bg = style.backgroundColor;
        var color = style.color;
        var border = style.borderColor;

        function suspicious(rgbStr) {
            if (!rgbStr || rgbStr === "transparent" || rgbStr === "rgba(0, 0, 0, 0)") return false;
            var m = rgbStr.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
            if (!m) return false;
            var r = +m[1],
                g = +m[2],
                b = +m[3];
            var orangeLike = r > 180 && g > 100 && b < 120 && r > g;
            var purpleLike = r > 120 && b > 120 && g < r && g < b;
            return orangeLike || purpleLike;
        }
        return suspicious(bg) || suspicious(color) || suspicious(border);
    }

    function paintOverride(el) {
        var st = window.getComputedStyle(el);
        if (!appliesOrangePurple(el, st)) return;
        el.style.setProperty("color", "#E6EDF3", "important");
        el.style.setProperty("border-color", "rgba(0, 242, 255, 0.35)", "important");
        el.style.setProperty("background-color", "rgba(13, 17, 23, 0.92)", "important");
    }

    function sweep(root) {
        root = root || document.body;
        if (!root || !root.querySelectorAll) return;
        var all = root.querySelectorAll("[class], [style]");
        for (var i = 0; i < all.length; i++) {
            var el = all[i];
            var cls = el.className && el.className.toString();
            if (
                cls &&
                (/orange|amber|purple|violet|fuchsia|stone-\d|warm/i.test(cls) ||
                    /text-\[#|bg-\[#|border-\[#/.test(cls))
            ) {
                paintOverride(el);
            }
        }
        var styled = root.querySelectorAll("[style*='rgb']");
        for (var j = 0; j < styled.length; j++) {
            paintOverride(styled[j]);
        }
    }

    var WA_ORDER_HREF =
        "https://wa.me/85252827144?text=" + encodeURIComponent("我想由參考圖片落單");

    function injectGlobalChrome() {
        if (!document.body || !document.body.classList.contains("f3f-brand")) return;
        if (document.getElementById("f3f-sticky-wa")) return;

        var foot = document.createElement("footer");
        foot.className = "f3f-site-footer";
        foot.setAttribute("role", "contentinfo");
        foot.innerHTML =
            "© 2026 Fan³cy Forge | IG: Fan³cy Forge | " +
            '<a href="https://wa.me/85252827144" target="_blank" rel="noopener noreferrer">WhatsApp: 52827144</a>';

        var sticky = document.createElement("a");
        sticky.id = "f3f-sticky-wa";
        sticky.className = "f3f-sticky-wa";
        sticky.href = WA_ORDER_HREF;
        sticky.target = "_blank";
        sticky.rel = "noopener noreferrer";
        sticky.textContent = "WhatsApp 落單";

        document.body.appendChild(foot);
        document.body.appendChild(sticky);
    }

    function scheduleDeferredSweep(root) {
        root = root || document.body;
        function run() {
            sweep(root);
        }
        if (typeof requestIdleCallback === "function") {
            requestIdleCallback(run, { timeout: 1400 });
        } else {
            setTimeout(run, 0);
        }
    }

    function boot() {
        injectGlobalChrome();
        scheduleDeferredSweep(document.body);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", boot);
    } else {
        boot();
    }

    window.f3fBrandSweep = sweep;
})();
