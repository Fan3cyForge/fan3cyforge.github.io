(function () {
    "use strict";

    function bust(url) {
        return typeof f3fCacheBust === "function" ? f3fCacheBust(url) : url + "?v=" + Date.now();
    }

    function norm(s) {
        return String(s || "").toLowerCase();
    }

    function contains(haystack, needle) {
        if (!needle) return true;
        return norm(haystack).indexOf(norm(needle)) !== -1;
    }

    /** @type {Record<string, { title?: string, path?: string, category?: string, categoryGroup?: string }>} */
    var articleMap = {};

    function pathFromViewerHref(href) {
        try {
            var u = new URL(href, window.location.origin);
            var f = u.searchParams.get("file");
            return f ? decodeURIComponent(f).replace(/^\//, "") : "";
        } catch (e) {
            return "";
        }
    }

    function basename(p) {
        if (!p) return "";
        var s = String(p).replace(/^\//, "");
        var i = s.lastIndexOf("/");
        return i >= 0 ? s.slice(i + 1) : s;
    }

    function pathFromRefHref(href) {
        try {
            return new URL(href, window.location.origin).pathname;
        } catch (e) {
            return String(href || "").replace(/^\//, "");
        }
    }

    function applyFilter(rawQuery) {
        var q = String(rawQuery || "").trim();

        var articleGrid = document.getElementById("f3f-article-grid");
        var articleVisible = 0;
        var articleTotal = 0;
        if (articleGrid) {
            var aLinks = articleGrid.querySelectorAll("a");
            aLinks.forEach(function (a) {
                articleTotal++;
                var path = pathFromViewerHref(a.href);
                var item = articleMap[path];
                var hay = item
                    ? [item.title, item.path, item.category, item.categoryGroup].join(" ")
                    : [path, a.textContent || ""].join(" ");
                var ok = contains(hay, q);
                a.style.display = ok ? "" : "none";
                if (ok) articleVisible++;
            });
        }

        var refHost = document.getElementById("f3f-ref-grid-host");
        var refVisible = 0;
        var refTotal = 0;
        if (refHost) {
            var rLinks = refHost.querySelectorAll("a");
            rLinks.forEach(function (a) {
                refTotal++;
                var pathname = pathFromRefHref(a.getAttribute("href") || a.href);
                var base = basename(pathname);
                var hay = pathname + " " + base;
                var ok = contains(hay, q);
                a.style.display = ok ? "" : "none";
                if (ok) refVisible++;
            });
        }

        var emptyEl = document.getElementById("f3f-search-empty");
        if (!emptyEl) return;

        var hasArticles = articleGrid && articleTotal > 0;
        var hasRefs = refHost && refTotal > 0;
        var showEmpty = false;
        if (q) {
            if (hasArticles && hasRefs) {
                showEmpty = articleVisible === 0 && refVisible === 0;
            } else if (hasArticles) {
                showEmpty = articleVisible === 0;
            } else if (hasRefs) {
                showEmpty = refVisible === 0;
            }
        }
        emptyEl.hidden = !showEmpty;
    }

    function loadJsonMaps() {
        return Promise.all([
            fetch(bust("/articles.json")).then(function (r) {
                return r.ok ? r.json() : null;
            }),
            fetch(bust("/reference-images.json")).then(function (r) {
                return r.ok ? r.json() : null;
            }),
        ]).then(function (pair) {
            var data = pair[0];
            articleMap = {};
            ((data && data.markdownArticles) || []).forEach(function (item) {
                var p = String(item.path || "").replace(/^\//, "");
                articleMap[p] = item;
            });
            return pair;
        });
    }

    function observeChildren(el, onChange) {
        if (!el || typeof MutationObserver === "undefined") return;
        var obs = new MutationObserver(function () {
            onChange();
        });
        obs.observe(el, { childList: true });
    }

    function init() {
        var input = document.getElementById("f3f-search-input");
        var clearBtn = document.getElementById("f3f-search-clear");
        if (!input) return;

        function run() {
            applyFilter(input.value);
        }

        input.addEventListener("input", run);
        input.addEventListener("search", run);
        if (clearBtn) {
            clearBtn.addEventListener("click", function () {
                input.value = "";
                applyFilter("");
                input.focus();
            });
        }

        loadJsonMaps()
            .then(function () {
                run();
            })
            .catch(function () {
                run();
            });

        observeChildren(document.getElementById("f3f-article-grid"), run);
        observeChildren(document.getElementById("f3f-ref-grid-host"), run);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
