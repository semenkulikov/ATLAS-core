import { writable } from "svelte/store";

function read(key: string): string {
  try {
    return sessionStorage.getItem(key) ?? "";
  } catch {
    return "";
  }
}

export const selectedApp = writable(read("atlas.app"));

selectedApp.subscribe((id) => {
  try {
    sessionStorage.setItem("atlas.app", id);
  } catch {
    /* private mode */
  }
});
