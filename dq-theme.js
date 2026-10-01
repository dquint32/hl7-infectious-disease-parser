/* dq-theme.js — light/dark switch shared by David Quintana's project demos.
 * Dark is the default (matches davidquintana.dev). The choice is remembered
 * per site when storage is available. A one-line snippet in <head> applies the
 * saved theme before first paint; this file wires up the toggle button(s).
 */
(function () {
  'use strict';
  var KEY = 'dq-theme';
  var root = document.documentElement;

  function save(theme) { try { localStorage.setItem(KEY, theme); } catch (e) { /* storage blocked */ } }

  function apply(theme) {
    root.setAttribute('data-theme', theme);
    var light = theme === 'light';
    document.querySelectorAll('.theme-toggle').forEach(function (btn) {
      btn.setAttribute('aria-pressed', String(light));
      btn.setAttribute('aria-label', light ? 'Switch to dark theme' : 'Switch to light theme');
    });
  }

  function init() {
    apply(root.getAttribute('data-theme') === 'light' ? 'light' : 'dark');
    document.querySelectorAll('.theme-toggle').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var next = root.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
        apply(next);
        save(next);
      });
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
