/**
 * netbox_branching: REST/API fetch helpers.
 * Reads active branch from cookie `active_branch` and sets X-NetBox-Branch.
 * @see netbox_branching.constants.COOKIE_NAME / BRANCH_HEADER
 */
(function (global) {
  "use strict";

  var BRANCH_COOKIE = "active_branch";
  var BRANCH_HEADER = "X-NetBox-Branch";

  function getActiveBranchSchemaId() {
    var m = document.cookie.match(
      new RegExp("(?:^|;\\s*)" + BRANCH_COOKIE + "=([^;]+)")
    );
    return m ? decodeURIComponent(m[1].trim()) : "";
  }

  function mergeBranchHeaders(headers) {
    var h = headers ? Object.assign({}, headers) : {};
    var branch = getActiveBranchSchemaId();
    if (branch) {
      h[BRANCH_HEADER] = branch;
    }
    return h;
  }

  function nsmApiFetch(url, options) {
    options = options || {};
    options.headers = mergeBranchHeaders(options.headers);
    if (!options.credentials) {
      options.credentials = "same-origin";
    }
    return fetch(url, options);
  }

  global.NSM_BRANCH_API = {
    cookieName: BRANCH_COOKIE,
    headerName: BRANCH_HEADER,
    getActiveBranchSchemaId: getActiveBranchSchemaId,
    mergeBranchHeaders: mergeBranchHeaders,
    fetch: nsmApiFetch,
  };
})(typeof window !== "undefined" ? window : this);
