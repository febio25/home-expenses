// A layer over the whole screen (the full-size photo of a Vinted item) that
// Android's back button closes, as in any app, instead of leaving the
// screen underneath. Opening it adds an entry to the history with the same
// address; app.js asks here first on every popstate.

let closeCurrent = null;
let skipNextPop = false;

// `close` must close the layer; it is called when the back button is used.
export function openOverlay(close) {
  history.pushState({ ...(history.state || {}), overlay: true }, '');
  closeCurrent = close;
}

// Called by the layer once it is closed, whatever closed it. Closed by its
// own button (not by back), the extra history entry is removed here.
export function overlayClosed() {
  if (!closeCurrent) return;
  closeCurrent = null;
  skipNextPop = true;
  history.back();
}

// True when the popstate event belonged to a layer: then the screen must
// not be drawn again (the list would lose its scroll position).
export function handleOverlayPop() {
  if (skipNextPop) {
    skipNextPop = false;
    return true;
  }
  if (closeCurrent) {
    const close = closeCurrent;
    closeCurrent = null;
    close();
    return true;
  }
  return false;
}
