// Applies the saved theme before first paint (no flash). "system" removes the attribute
// so the prefers-color-scheme tokens apply.
const script = `(function(){try{var t=localStorage.getItem("dockline-theme");if(t==="light"||t==="dark"){document.documentElement.setAttribute("data-theme",t);}}catch(e){}})();`;

export function ThemeScript() {
  return <script dangerouslySetInnerHTML={{ __html: script }} />;
}
