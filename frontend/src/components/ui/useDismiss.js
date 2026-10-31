import { useEffect } from "react";

// Open layers, oldest first. Escape only closes the newest, so pressing it in a
// picker inside the filter drawer closes the picker and leaves the drawer open.
const openLayers = [];

/**
 * Calls `onDismiss(reason)` while `open` when the user clicks outside `ref`
 * ("outside") or presses Escape ("escape"). Used by popovers and the drawer.
 * Pass a stable `onDismiss` (useCallback) so the layer order stays correct.
 */
export function useDismiss(ref, open, onDismiss) {
  useEffect(() => {
    if (!open) {
      return undefined;
    }

    const layer = {};
    openLayers.push(layer);

    function handlePointerDown(event) {
      if (ref.current && !ref.current.contains(event.target)) {
        onDismiss("outside");
      }
    }

    function handleKeyDown(event) {
      if (event.key === "Escape" && openLayers[openLayers.length - 1] === layer) {
        onDismiss("escape");
      }
    }

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      openLayers.splice(openLayers.indexOf(layer), 1);
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [ref, open, onDismiss]);
}
