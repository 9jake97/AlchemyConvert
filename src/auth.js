// auth.js — Auth bypass (no license server needed)
// The original auth.js contacts home.kaizermc.xyz:3050 for license verification.
// This bypass skips that entirely so the app works without a token.

(function () {
  // Hide the token overlay immediately
  const overlay = document.getElementById('tokenOverlay');
  if (overlay) overlay.style.display = 'none';
})();