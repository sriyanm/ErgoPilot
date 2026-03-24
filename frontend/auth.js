/**
 * Shared session helpers: JWT access token in sessionStorage (tab-scoped).
 * Align API base with app.js via optional window.__ERGOPILOT_API_BASE__.
 */
(function (global) {
  var AUTH_TOKEN_KEY = "ergopilot_access_token";
  var DEFAULT_API = "http://localhost:8000";

  function getApiBaseUrl() {
    return global.__ERGOPILOT_API_BASE__ || DEFAULT_API;
  }

  function getAccessToken() {
    try {
      return sessionStorage.getItem(AUTH_TOKEN_KEY);
    } catch (_) {
      return null;
    }
  }

  function setAccessToken(token) {
    try {
      if (token) {
        sessionStorage.setItem(AUTH_TOKEN_KEY, token);
      } else {
        sessionStorage.removeItem(AUTH_TOKEN_KEY);
      }
    } catch (_) {
      /* ignore quota / private mode */
    }
  }

  function clearSession() {
    setAccessToken(null);
  }

  /** Allow only same-origin relative HTML targets after login. */
  function safeNextPath(raw) {
    var allowed = { "dashboard.html": true, "index.html": true };
    if (!raw || typeof raw !== "string") {
      return "./dashboard.html";
    }
    var trimmed = raw.trim();
    try {
      var resolved = new URL(trimmed, global.location.href);
      if (resolved.origin !== global.location.origin) {
        return "./dashboard.html";
      }
      var name = resolved.pathname.split("/").pop() || "";
      return allowed[name] ? "./" + name : "./dashboard.html";
    } catch (_) {
      return "./dashboard.html";
    }
  }

  function redirectToSignIn(nextPath) {
    var q = nextPath ? "?next=" + encodeURIComponent(nextPath) : "";
    global.location.replace("./signin.html" + q);
  }

  function authHeaders() {
    var t = getAccessToken();
    if (!t) {
      return {};
    }
    return { Authorization: "Bearer " + t };
  }

  global.ErgoPilotAuth = {
    getApiBaseUrl: getApiBaseUrl,
    getAccessToken: getAccessToken,
    setAccessToken: setAccessToken,
    clearSession: clearSession,
    safeNextPath: safeNextPath,
    redirectToSignIn: redirectToSignIn,
    authHeaders: authHeaders
  };
})(typeof window !== "undefined" ? window : globalThis);
